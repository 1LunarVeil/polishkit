"""Record the measurement environment a benchmark run was taken in.

Usage:
  python tools/benchmark_env.py            # print the fingerprint
  python tools/benchmark_env.py --write    # write it next to the benchmark

Why this exists: the 2.0 benchmark recorded 101 contrast failures on the
baseline condition. Re-measuring the same, never-edited pages with the 2.2.10
tooling gives 105 — stably, twice in a row. Nothing in the pages or the audit
changed to explain it, so the difference is environmental: a different browser
build, font set, or rendering path. Without recording the environment, a
benchmark number cannot be re-derived, and a reader has no way to tell a real
regression from a machine change.

The fingerprint covers what actually moves these numbers:

- the browser build (contrast and layout are measured through it),
- the Python version (the colour math and the report logic run in it),
- the platform and its device pixel ratio class (font rasterisation differs),
- the audit tools' own version, so a tool change is visible in the record.

It is written as JSON so a later run can diff it field by field.
"""

import argparse
import datetime
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "polishkit" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import visual_capture  # noqa: E402

ENV_FILE = ROOT / "benchmark" / "ENVIRONMENT.json"


def manifest_version():
    path = ROOT / ".zcode-plugin" / "plugin.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("version")
    except ValueError:
        return None


def browser_version(browser):
    """Ask the browser for its version string; None when it will not answer.

    Both Chromium flags are tried: `--version` prints and exits on some builds,
    while others need `--product-version`. A browser that answers neither is
    recorded as present-but-unidentified rather than silently omitted, because
    "the browser changed" is the thing this file exists to catch.
    """
    if not browser:
        return None
    for flag in ("--version", "--product-version"):
        try:
            result = subprocess.run(  # noqa: S603 - absolute path, list form
                [browser, flag], shell=False, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=20, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        text = (result.stdout or "").strip().splitlines()
        if not text:
            continue
        first = text[0].strip()
        # Either a product name ("Google Chrome 157…") or a bare version
        # ("157.0.8103.79"). Anything else is not a version answer.
        if "Chrome" in first or first[:1].isdigit():
            return first
    return None


def tool_digests():
    """A hash per audit script, so a tool edit is visible in the record."""
    digests = {}
    for path in sorted(SCRIPTS.glob("*.py")):
        digests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return digests


def fingerprint():
    browser = visual_capture.find_browser()
    return {
        "recorded_at": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plugin_version": manifest_version(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor_note": platform.processor() or None,
        "browser_path": browser,
        "browser_version": browser_version(browser),
        "tool_digests": tool_digests(),
    }


def diff_against(path):
    """Field-by-field differences between this run and a recorded fingerprint.

    Only the fields that can change a measurement are compared: the timestamp
    and the digests are reported separately, because a digest change means the
    tool itself moved and that is worth its own line.
    """
    if not path.is_file():
        return None
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    current = fingerprint()
    changed, same = {}, {}
    for key in ("plugin_version", "python", "platform", "machine",
                "browser_path", "browser_version"):
        before, after = previous.get(key), current.get(key)
        if before != after:
            changed[key] = {"before": before, "after": after}
        else:
            same[key] = before
    tools_before = previous.get("tool_digests") or {}
    tools_after = current.get("tool_digests") or {}
    changed_tools = sorted(
        name for name in set(tools_before) | set(tools_after)
        if tools_before.get(name) != tools_after.get(name))
    return {"changed": changed, "same": same, "changed_tools": changed_tools,
            "previous_recorded_at": previous.get("recorded_at")}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Record or verify the environment a benchmark was measured in.")
    parser.add_argument("--write", action="store_true",
                        help=f"write the fingerprint to {ENV_FILE}")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument("--diff", action="store_true",
                        help="compare this environment against the recorded one")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.diff:
        result = diff_against(ENV_FILE)
        if result is None:
            print(json.dumps({"verified": False,
                              "reason": f"no readable fingerprint at {ENV_FILE}"},
                             ensure_ascii=False))
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["changed"] or result["changed_tools"] else 0

    data = fingerprint()
    if args.write:
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print(f"wrote {ENV_FILE}")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif not args.write:
        for key in ("plugin_version", "python", "platform", "machine",
                    "browser_version"):
            print(f"{key}: {data.get(key)}")
        print(f"tool digests: {len(data['tool_digests'])} script(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
