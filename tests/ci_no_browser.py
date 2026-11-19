"""CI check: with no browser, the rendered-page audits claim nothing.

Both audits promise the same contract: when they cannot measure, they report
{"verified": false} and exit 2 rather than printing a clean-looking result. CI
runners may or may not have Chromium, so the "no browser" condition is stubbed
instead of assumed — a check that passes for the wrong reason proves nothing.

Run from the repository root: python -B tests/ci_no_browser.py
"""

import io
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "polishkit" / "scripts"))

import keyboard_audit  # noqa: E402
import page_audit  # noqa: E402


def run_quietly(main, argv):
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", write_through=True)
    original = sys.stdout
    sys.stdout = stream
    try:
        code = main(argv)
    finally:
        sys.stdout = original
    return code, stream.buffer.getvalue().decode("utf-8")


def main():
    # One stub covers both modules: they share the sibling visual_capture module.
    keyboard_audit.visual_capture.find_browser = lambda: None
    page_audit.visual_capture.find_browser = lambda: None

    failures = []
    for tool in (page_audit, keyboard_audit):
        code, output = run_quietly(tool.main, ["http://127.0.0.1:9/"])
        try:
            payload = json.loads(output)
        except ValueError:
            failures.append(f"{tool.__name__}: output was not JSON: {output!r}")
            continue
        if code != 2:
            failures.append(f"{tool.__name__}: expected exit 2, got {code}")
        if payload.get("verified") is not False:
            failures.append(f"{tool.__name__}: claimed {payload.get('verified')!r} without a browser")
        print(f"{tool.__name__}: exit {code}, verified {payload.get('verified')}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print("both audits claim nothing without a browser")
    return 0


if __name__ == "__main__":
    sys.exit(main())
