"""Capture UI screenshots with a Chromium-family browser, headless.

Usage:
  python visual_capture.py URL --out DIR [--width 1440] [--height 900]
                               [--theme dark] [--scale 1] [--name default]
  python visual_capture.py URL --out DIR --matrix [--allow-private]
  python visual_capture.py URL --out DIR --dark --full-page
  python visual_capture.py URL --out DIR --hover "button.primary" --focus "#email"

Engine: when a browser exists, capture runs over CDP (via the sibling cdp.py,
stdlib only) with one persistent browser for the whole plan; --dark then really
emulates prefers-color-scheme instead of only naming the file, and --full-page,
--element, --hover and --focus become possible. Any CDP failure falls back to
the legacy per-view --screenshot path and the JSON says so ("engine":
"screenshot", "cdp_error": ...). With no browser at all, exit 2 as before.
Interaction views run last: a hover state left behind would pollute the
remaining captures.

Prints one JSON object with the captures, console lines and the browser path.
Exit status 2 when no browser is available, 3 when the URL is rejected.

Design notes (learned from a real capture run):
- Wait for a readiness signal, never a fixed sleep. A 4s virtual-time budget
  captured a blank frame of a real app; 8s captured the same view correctly.
- Never resolve the browser by bare name. On Windows the executable search
  order favours the current directory and the application folder, which turns
  a capture into arbitrary code execution. Only absolute paths under Program
  Files or /usr/bin are accepted; a miss disables the feature.
- The URL is untrusted input to argv. Validate the scheme and refuse a leading
  "-" so it cannot be parsed as a browser switch, and require an explicit flag
  before navigating to a private (non-public) address.
- Read-only: writes PNGs only into --out.
"""

import argparse
import base64
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

sys.dont_write_bytecode = True
import cdp  # noqa: E402  (sibling module; no third-party dependencies)
import image_diff  # noqa: E402  (sibling module; no third-party dependencies)

WINDOWS_CANDIDATES = (
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
)
POSIX_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/microsoft-edge",
)
MIN_READY_TEXT = 200
MAX_WAIT_SECONDS = 20
# Two consecutive identical frames are considered settled; this many rounds max.
STABLE_ATTEMPTS = 4
# A rendered page has many anti-aliased shades; a bare shell has very few.
# Dark themes legitimately produce fewer shades, so the blank test is looser
# there; both thresholds were calibrated against real light and dark pages.
MIN_RENDERED_COLORS = 400
MIN_RENDERED_COLORS_DARK = 250


class UrlRejected(ValueError):
    pass


def find_browser():
    """Return an absolute path to a Chromium-family browser, or None."""
    if os.name == "nt":
        for path in WINDOWS_CANDIDATES:
            expanded = os.path.expandvars(path)
            if Path(expanded).is_file():
                return str(Path(expanded).resolve())
        return None
    for path in POSIX_CANDIDATES:
        if Path(path).is_file():
            return path
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found and Path(found).is_absolute():
            return found
    return None


def _addresses(host):
    try:
        return {ipaddress.ip_address(host)}
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise UrlRejected(f"cannot resolve host {host!r}: {exc}") from exc
    return {ipaddress.ip_address(info[4][0]) for info in infos}


def validate_url(url, allow_private=False):
    """Reject non-http(s) schemes, option-like strings and private targets."""
    if url.startswith("-"):
        raise UrlRejected("URL must not start with '-' (it would be parsed as a browser switch)")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UrlRejected(f"only http and https are allowed, got {parsed.scheme or 'no scheme'!r}")
    host = parsed.hostname
    if not host:
        raise UrlRejected("URL has no host")
    for address in _addresses(host):
        if address.is_loopback:
            continue  # the tool's purpose: a local preview server
        if address.is_private or address.is_link_local or address.is_reserved or address.is_multicast:
            if not allow_private:
                raise UrlRejected(
                    f"{host} resolves to the non-public address {address}; "
                    "pass --allow-private to capture it"
                )
    return url


def _base_command(browser, profile_dir, width, height, scale):
    return [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-proxy-server",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        f"--user-data-dir={profile_dir}",
        f"--window-size={width},{height}",
        f"--force-device-scale-factor={scale}",
    ]


def _run(command):
    return subprocess.run(  # noqa: S603 - fixed absolute browser path, list form, no shell
        command,
        shell=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )


def _dom_and_console(browser, profile_dir, url, budget_ms):
    command = _base_command(browser, profile_dir, 1280, 800, 1) + [
        "--enable-logging=stderr",
        "--v=0",
        "--dump-dom",
        f"--virtual-time-budget={budget_ms}",
        url,
    ]
    result = _run(command)
    console = []
    for line in result.stderr.splitlines():
        if "CONSOLE" in line:
            message = line.split("CONSOLE", 1)[-1].lstrip(":)d ")
            console.append(message.strip())
    errors = [line for line in console if "error" in line.lower() or "uncaught" in line.lower()]
    return result.stdout, console, errors


def wait_for_render(browser, profile_dir, url, budget_ms):
    """Grow the virtual-time budget until the DOM has real content."""
    budget = budget_ms
    while True:
        dom, console, errors = _dom_and_console(browser, profile_dir, url, budget)
        if len(" ".join(dom.split())) >= MIN_READY_TEXT or budget >= MAX_WAIT_SECONDS * 1000:
            return dom, errors, budget
        budget = min(budget * 2, MAX_WAIT_SECONDS * 1000)


def _shoot(browser, profile, url, width, height, scale, budget, target):
    command = _base_command(browser, profile, width, height, scale) + [
        f"--virtual-time-budget={budget}",
        f"--screenshot={target}",
        url,
    ]
    _run(command)
    return Path(target).exists()


def capture(browser, url, out_dir, name, width, height, scale, theme, budget_ms):
    """Capture one view, retrying until two consecutive frames agree.

    A single shot is not trustworthy: on a real app a slower first paint
    produced a half-rendered shell at one window size while the same page was
    complete at another. Two identical frames mean the view has settled.
    """
    profile = Path(tempfile.mkdtemp(prefix="fa-profile-"))
    target = Path(out_dir) / f"{name}-{width}x{height}-{theme}@{scale:g}.png"
    first = target.with_suffix(".a.png")
    second = target.with_suffix(".b.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    settled = False
    budget = budget_ms
    attempts = 0
    try:
        dom, errors, budget = wait_for_render(browser, profile, url, budget)
        while attempts < STABLE_ATTEMPTS:
            attempts += 1
            if not (_shoot(browser, profile, url, width, height, scale, budget, first)
                    and _shoot(browser, profile, url, width, height, scale, budget, second)):
                budget = min(int(budget * 1.5), MAX_WAIT_SECONDS * 1000)
                continue
            comparison = image_diff.diff(first, second)
            if comparison.get("comparable") and comparison["identical"]:
                settled = True
                break
            budget = min(int(budget * 1.5), MAX_WAIT_SECONDS * 1000)

        source = second if second.exists() else first
        if source.exists():
            source.replace(target)
        if target.exists():
            summary = image_diff.stats(target)
            blank = summary["distinct_colors_sampled"] < MIN_RENDERED_COLORS
        else:
            summary, blank = {"distinct_colors_sampled": 0}, True
        return {
            "file": str(target),
            "bytes": target.stat().st_size if target.exists() else 0,
            "dom_chars": len(" ".join(dom.split())),
            "distinct_colors": summary["distinct_colors_sampled"],
            "settled": settled,
            "attempts": attempts,
            "virtual_time_budget_ms": budget,
            "console_errors": errors,
            "blank": blank,
        }
    finally:
        for leftover in (first, second):
            leftover.unlink(missing_ok=True)
        shutil.rmtree(profile, ignore_errors=True)


def _start_cdp_browser(browser):
    """Launch one persistent headless browser with a loopback CDP endpoint."""
    profile = Path(tempfile.mkdtemp(prefix="fa-cdp-"))
    command = [
        browser, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--disable-extensions",
        f"--user-data-dir={profile}", "--remote-debugging-port=0", "about:blank",
    ]
    process = subprocess.Popen(  # noqa: S603 - absolute browser path, list form, no shell
        command, shell=False, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        port, _ = cdp.read_devtools_port(profile, process, timeout=10)
        endpoint = cdp.discover_endpoint(port, timeout=10)
    except Exception:
        process.terminate()
        shutil.rmtree(profile, ignore_errors=True)
        raise
    return process, profile, endpoint["webSocketDebuggerUrl"]


def _console_text(entry):
    parts = [entry.get("text"), entry.get("description"),
             (entry.get("exception") or {}).get("description")]
    return " ".join(part for part in parts if part).strip()


def _console_collectors(messages):
    def exception_thrown(message):
        text = _console_text(message["params"].get("exceptionDetails", {}))
        if text:
            messages.append(text)

    def entry_added(message):
        entry = message["params"].get("entry", {})
        if entry.get("level") == "error":
            text = _console_text(entry)
            if text:
                messages.append(text)

    return exception_thrown, entry_added


def _console_errors(messages):
    return [line for line in messages if "error" in line.lower() or "uncaught" in line.lower()]


def _evaluate(session, session_id, expression):
    result = session.send(
        "Runtime.evaluate", {"expression": expression, "returnByValue": True},
        session=session_id,
    )
    return result["result"].get("value")


def _wait_ready(session, session_id, timeout=MAX_WAIT_SECONDS):
    """Poll readyState and body text length; mirrors the legacy readiness gate."""
    deadline = time.monotonic() + timeout
    length = 0
    while time.monotonic() < deadline:
        value = _evaluate(
            session, session_id,
            "document.readyState + '|' + (document.body ? document.body.innerText.length : -1)",
        )
        if isinstance(value, str):
            state, _, raw = value.partition("|")
            try:
                length = int(raw)
            except ValueError:
                length = 0
            if state == "complete" and length >= MIN_READY_TEXT:
                return length
        time.sleep(0.25)
    return length


def _settled_capture(session, session_id, target_path, clip=None):
    """Shoot until two consecutive frames agree; identical PNG bytes mean settled."""
    previous = None
    for attempt in range(1, STABLE_ATTEMPTS + 1):
        params = {"format": "png"}
        if clip is not None:
            params["clip"] = clip
            params["captureBeyondViewport"] = True
        data = session.send("Page.captureScreenshot", params, session=session_id)["data"]
        current = base64.b64decode(data)
        if previous is not None and current == previous:
            target_path.write_bytes(current)
            return True, attempt
        previous = current
        time.sleep(0.4)
    target_path.write_bytes(previous if previous is not None else b"")
    return False, STABLE_ATTEMPTS


_BOX_JS = (
    "(function(){{"
    "var el = document.querySelector({selector});"
    "if (!el) return null;"
    "el.scrollIntoView({{block: 'center'}});"
    "var r = el.getBoundingClientRect();"
    "return JSON.stringify({{x: r.x + window.scrollX, y: r.y + window.scrollY,"
    " width: r.width, height: r.height,"
    " cx: r.x + r.width / 2, cy: r.y + r.height / 2}});"
    "}})()"
)


def _element_box(session, session_id, selector):
    value = _evaluate(session, session_id, _BOX_JS.format(selector=json.dumps(selector)))
    if not value:
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


def _capture_with_cdp(browser, url, out_dir, views, theme_dark, full_page,
                      element_selector, hover_selector, focus_selector):
    """One persistent browser, one session, every view of the plan.

    Raises on any CDP failure; main() catches and falls back to the legacy
    per-view --screenshot path.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    theme = "dark" if theme_dark else "light"
    process = profile = None
    results = []
    console_messages = []
    target_id = None
    try:
        process, profile, ws_url = _start_cdp_browser(browser)
        connection = cdp.Connection(ws_url)
        session = cdp.Session(connection)
        on_exception, on_entry = _console_collectors(console_messages)
        session.on("Runtime.exceptionThrown", on_exception)
        session.on("Log.entryAdded", on_entry)

        target_id = session.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        session_id = session.send(
            "Target.attachToTarget", {"targetId": target_id, "flatten": True}
        )["sessionId"]
        for domain in ("Page", "Runtime", "Log"):
            session.send(domain + ".enable", session=session_id)
        session.send("Page.navigate", {"url": url}, session=session_id)
        cdp.wait_for_event(session, "Page.loadEventFired", 10.0,
                           match=lambda message: message.get("sessionId") == session_id)
        dom_chars = _wait_ready(session, session_id)

        if theme_dark:
            session.send(
                "Emulation.setEmulatedMedia",
                {"features": [{"name": "prefers-color-scheme", "value": "dark"}]},
                session=session_id,
            )
        errors = _console_errors(console_messages)

        def metrics_override(width, height, scale):
            session.send("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": scale,
                "mobile": False,
            }, session=session_id)

        def record(name, width, height, scale, clip=None):
            path = out / f"{name}-{width}x{height}-{theme}@{scale:g}.png"
            settled, attempts = _settled_capture(session, session_id, path, clip=clip)
            summary = image_diff.stats(path) if path.exists() else {"distinct_colors_sampled": 0}
            results.append({
                "file": str(path),
                "bytes": path.stat().st_size if path.exists() else 0,
                "dom_chars": dom_chars,
                "distinct_colors": summary["distinct_colors_sampled"],
                "settled": settled,
                "attempts": attempts,
                "virtual_time_budget_ms": None,
                "console_errors": _console_errors(console_messages),
                "blank": False if clip is not None else summary["distinct_colors_sampled"] < (
                    MIN_RENDERED_COLORS_DARK if theme_dark else MIN_RENDERED_COLORS),
                "theme_emulated": bool(theme_dark),
            })

        for name, width, height, scale in views:
            metrics_override(width, height, scale)
            record(name, width, height, scale)

        base_name, base_width, base_height, base_scale = views[0]
        if full_page:
            metrics_override(base_width, base_height, base_scale)
            content = session.send("Page.getLayoutMetrics", session=session_id)
            size = content.get("contentSize", {})
            clip = {"x": 0, "y": 0, "width": size.get("width", base_width),
                    "height": size.get("height", base_height), "scale": 1}
            record("fullpage", int(clip["width"]), int(clip["height"]), 1, clip=clip)
        if element_selector:
            metrics_override(base_width, base_height, base_scale)
            box = _element_box(session, session_id, element_selector)
            if box:
                clip = {"x": box["x"], "y": box["y"], "width": box["width"],
                        "height": box["height"], "scale": 1}
                record("element", int(box["width"]), int(box["height"]), 1, clip=clip)
            else:
                results.append({"file": None, "settled": False, "blank": False,
                                "console_errors": [], "note": f"no element matched {element_selector!r}"})
        for selector, label in ((hover_selector, "hover"), (focus_selector, "focus")):
            if not selector:
                continue
            metrics_override(base_width, base_height, base_scale)
            box = _element_box(session, session_id, selector)
            if not box:
                results.append({"file": None, "settled": False, "blank": False,
                                "console_errors": [], "note": f"no element matched {selector!r}"})
                continue
            if label == "hover":
                session.send("Input.dispatchMouseEvent", {
                    "type": "mouseMoved", "x": box["cx"], "y": box["cy"],
                }, session=session_id)
            else:
                _evaluate(session, session_id,
                          f"document.querySelector({json.dumps(selector)}).focus()")
            time.sleep(0.3)
            record(label, base_width, base_height, base_scale)
        return {
            "engine": "cdp",
            "captures": results,
            "blank_frames": any(item["blank"] for item in results),
            "console_errors": any(item["console_errors"] for item in results),
            "theme_emulated": bool(theme_dark),
        }
    finally:
        if process is not None:
            if target_id is not None:
                try:
                    session.send("Target.closeTarget", {"targetId": target_id}, timeout=3)
                except Exception:
                    pass
            try:
                session.send("Browser.close", timeout=3)
            except Exception:
                pass
            process.terminate()
            if profile is not None:
                shutil.rmtree(profile, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Headless UI screenshots for design review.")
    parser.add_argument("url")
    parser.add_argument("--out", required=True)
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--scale", type=float, default=1)
    parser.add_argument("--theme", default="light", help="recorded in the filename; 'dark' also emulates the theme over CDP")
    parser.add_argument("--name", default="view")
    parser.add_argument("--budget", type=int, default=4000, help="initial virtual time in ms (legacy engine)")
    parser.add_argument("--matrix", action="store_true", help="capture the standard set of sizes")
    parser.add_argument("--dark", action="store_true", help="emulate prefers-color-scheme: dark (CDP engine)")
    parser.add_argument("--full-page", action="store_true", help="add a full-page view at the base size (CDP engine)")
    parser.add_argument("--element", metavar="SELECTOR", help="add a clipped view of one element (CDP engine)")
    parser.add_argument("--hover", metavar="SELECTOR", help="add a view with the pointer over one element (CDP engine)")
    parser.add_argument("--focus", metavar="SELECTOR", help="add a view with one element focused (CDP engine)")
    parser.add_argument("--allow-private", action="store_true",
                        help="allow non-public, non-loopback addresses")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        url = validate_url(args.url, allow_private=args.allow_private)
    except UrlRejected as exc:
        print(json.dumps({"ok": False, "reason": f"URL rejected: {exc}"}, ensure_ascii=False))
        return 3

    browser = find_browser()
    if not browser:
        print(json.dumps({
            "ok": False,
            "reason": "no Chromium-family browser found at an absolute path; visual capture disabled",
        }, ensure_ascii=False))
        return 2

    if args.matrix:
        plan = [
            ("wide", 1440, 900, 1),
            ("wide-scaled", 1440, 900, 1.5),
            ("narrow", 1100, 720, 1),
            ("phone", 390, 844, 1),
        ]
    else:
        plan = [(args.name, args.width, args.height, args.scale)]

    theme_dark = args.dark or args.theme == "dark"
    if args.dark and args.theme == "light":
        args.theme = "dark"

    cdp_error = None
    summary = None
    try:
        summary = _capture_with_cdp(
            browser, url, args.out, plan, theme_dark,
            args.full_page, args.element, args.hover, args.focus,
        )
        engine = "cdp"
    except Exception as exc:  # noqa: BLE001 - documented fallback contract
        cdp_error = f"{type(exc).__name__}: {exc}"
        summary = None

    if summary is None:
        if any((args.full_page, args.element, args.hover, args.focus, args.dark)):
            print(json.dumps({
                "ok": False,
                "engine": "screenshot",
                "reason": "CDP capture failed and the requested feature needs it",
                "cdp_error": cdp_error,
            }, ensure_ascii=False))
            return 2
        results = [
            capture(browser, url, args.out, name, width, height, scale, args.theme, args.budget)
            for name, width, height, scale in plan
        ]
        summary = {
            "captures": results,
            "blank_frames": any(item["blank"] for item in results),
            "console_errors": any(item["console_errors"] for item in results),
            "theme_emulated": False,
        }
        engine = "screenshot"

    print(json.dumps({
        "ok": True,
        "engine": engine,
        "browser": browser,
        "cdp_error": cdp_error,
        "theme_emulated": summary.get("theme_emulated", False),
        "captures": summary["captures"],
        "blank_frames": summary["blank_frames"],
        "console_errors": summary["console_errors"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
