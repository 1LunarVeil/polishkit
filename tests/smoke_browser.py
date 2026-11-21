"""Real-browser smoke test: the CDP path, measured end to end.

Every unit test runs without a browser — by design, and stated in both
READMEs. That left the integration path (Chrome launched, WebSocket
negotiated, pages driven, screenshots decoded) with zero automated coverage,
which an external review flagged: the plugin's headline features — dark
theme, hover/focus capture, rendered audits — all live on exactly that path.
The CI runners ship Chrome, so this file closes the gap there and on any
machine that has a browser:

- a defect fixture must FAIL where defects were planted: a low-contrast text
  pair (WCAG 1.4.3), a control removed from the tab order (2.1.1), and a link
  with no focus indicator (2.4.7);
- a clean fixture must come back 0 FAIL on both audits — the paired-direction
  check that proves the audits did not merely learn to shout;
- both reports say verified: true, which only happens when the whole capture
  stack actually ran.

Run from the repository root: python -B tests/smoke_browser.py
Exit 0 = both directions behaved; 1 = a finding mismatched; 2 = no browser
(the no-browser contract is covered separately by tests/ci_no_browser.py).
"""

import io
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "polishkit" / "scripts"))

import cdp  # noqa: E402
import keyboard_audit  # noqa: E402
import page_audit  # noqa: E402
import visual_capture  # noqa: E402

DEFECT_PAGE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>smoke defect</title>
<style>
  a:focus { outline: none; }
  button { padding: 12px 16px; font-size: 16px; }
</style></head>
<body>
  <p style="color:#a0a0a0;background:#ffffff;font-size:14px">low contrast copy</p>
  <p><button type="button" tabindex="-1">ghost button</button></p>
  <p><a href="#nowhere">focusless link</a></p>
</body></html>
"""

CLEAN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>smoke clean</title>
<style>
  button:focus { outline: 3px solid #0000ff; outline-offset: 2px; }
  button { padding: 12px 16px; font-size: 16px; }
</style></head>
<body>
  <p style="color:#1a1a1a;background:#ffffff;font-size:14px">strong contrast copy</p>
  <p><button type="button">real button</button></p>
</body></html>
"""


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802  (http.server API name)
        page = {"/defect": DEFECT_PAGE, "/clean": CLEAN_PAGE}.get(self.path)
        if page is None:
            self.send_error(404)
            return
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # request logging would drown the assertions


def _run(main, argv):
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", write_through=True)
    original = sys.stdout
    sys.stdout = stream
    try:
        code = main(argv)
    finally:
        sys.stdout = original
    raw = stream.buffer.getvalue().decode("utf-8")
    try:
        return code, json.loads(raw)
    except ValueError:
        return code, {"verified": False,
                      "reason": f"output was not JSON: {raw[:800]!r}"}


def _why(payload):
    reason = payload.get("reason")
    return f" reason={reason}" if reason else ""


def _run_with_retry(main, argv, attempts=2):
    """Exit 2 ("no audit performed") is the launch-failure class — a runner's
    Chrome can fail to start under transient resource pressure, and two CI
    runs proved it flaky on exactly that path. One retry absorbs it. A wrong
    verdict (exit 0 or 1) is an assertion about the page, never retried: a
    smoke test that retries its own failures proves nothing."""
    code = payload = None
    for _ in range(attempts):
        code, payload = _run(main, argv)
        if code != 2:
            return code, payload
        time.sleep(3)
    return code, payload


def main():
    browser = visual_capture.find_browser()
    if browser is None:
        print("smoke_browser: no Chromium-family browser found; nothing to prove", file=sys.stderr)
        return 2
    print(f"smoke_browser: using browser {browser}")
    try:
        reported = subprocess.run([browser, "--version"], capture_output=True,
                                  text=True, timeout=60).stdout.strip()
        print(f"smoke_browser: {reported}")
    except (OSError, subprocess.TimeoutExpired):
        pass  # the audits will say what is wrong with a browser that won't even talk

    server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    failures = []
    try:
        # One throwaway roundtrip before anything is asserted. A CI VM's
        # first Chrome launch pays for antivirus scanning of the binary and
        # its DLLs, and the audits' 10-second budgets are sized for a warm
        # machine — a Windows runner timed out waiting for load on its first
        # invocation and passed the next with nothing changed. The warmup
        # pays that cost once, with a 30-second budget.
        warm_started = time.monotonic()
        state = None
        last = "no BrowserError; the roundtrip itself succeeded"
        for attempt in (1, 2, 3):
            # Launch-class failures (a runner VM's antivirus scanning the
            # freshly unpacked browser, a transient navigation abort) are the
            # flaky class; the audits' 10-second budgets are sized for a warm
            # machine. Three fresh roundtrips absorb them. A warmup that
            # cannot load the page after three tries is worth dying on: the
            # four audits below would repeat it, slower, twice each.
            try:
                with cdp.PageSession(f"{base}/clean", load_timeout=30.0) as page:
                    state = page.session.send(
                        "Runtime.evaluate",
                        {"expression": "document.readyState", "returnByValue": True},
                        session=page.session_id)["result"].get("value")
                break
            except cdp.BrowserError as exc:
                last = str(exc)
                print(f"smoke_browser: warmup attempt {attempt} failed: {exc}",
                      file=sys.stderr)
        if state != "complete":
            print(f"FAIL warmup did not load the fixture page after three "
                  f"attempts: {last}", file=sys.stderr)
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            return 1
        print(f"smoke_browser: warmup readyState={state} in "
              f"{time.monotonic() - warm_started:.1f}s")
        code, page = _run_with_retry(page_audit.main, [f"{base}/defect", "--json"])
        summary = page.get("summary", {})
        if code != 1 or not page.get("verified"):
            failures.append(f"page_audit defect page: exit {code}, "
                            f"verified {page.get('verified')}{_why(page)}")
        if summary.get("fail", 0) < 1:
            failures.append(f"page_audit defect page: planted contrast pair did not fail "
                            f"(summary: {summary})")
        print(f"page_audit /defect: exit {code}, contrast fail {summary.get('fail')}")

        code, keys = _run_with_retry(keyboard_audit.main, [f"{base}/defect", "--json"])
        summary = keys.get("summary", {})
        if code != 1 or not keys.get("verified"):
            failures.append(f"keyboard_audit defect page: exit {code}, "
                            f"verified {keys.get('verified')}{_why(keys)}")
        if summary.get("unreachable", 0) < 1:
            failures.append(f"keyboard_audit defect page: the tabindex=-1 control was not "
                            f"reported unreachable (summary: {summary})")
        if summary.get("no_indicator", 0) < 1:
            failures.append(f"keyboard_audit defect page: the outline:none link was not "
                            f"reported without a focus indicator (summary: {summary})")
        print(f"keyboard_audit /defect: exit {code}, fail {summary.get('fail')}, "
              f"unreachable {summary.get('unreachable')}, no_indicator {summary.get('no_indicator')}")

        code, page = _run_with_retry(page_audit.main, [f"{base}/clean", "--json"])
        summary = page.get("summary", {})
        if code != 0 or not page.get("verified"):
            failures.append(f"page_audit clean page: exit {code}, "
                            f"verified {page.get('verified')}{_why(page)}")
        if summary.get("fail", 0) != 0:
            failures.append(f"page_audit clean page: {summary.get('fail')} failure(s) on a clean page "
                            f"(summary: {summary})")
        print(f"page_audit /clean: exit {code}, contrast fail {summary.get('fail')}")

        code, keys = _run_with_retry(keyboard_audit.main, [f"{base}/clean", "--json"])
        summary = keys.get("summary", {})
        if code != 0 or not keys.get("verified"):
            failures.append(f"keyboard_audit clean page: exit {code}, "
                            f"verified {keys.get('verified')}{_why(keys)}")
        if summary.get("fail", 0) != 0:
            failures.append(f"keyboard_audit clean page: {summary.get('fail')} failure(s) on a clean page "
                            f"(summary: {summary})")
        print(f"keyboard_audit /clean: exit {code}, fail {summary.get('fail')}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print("smoke_browser: the CDP path measured both directions correctly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
