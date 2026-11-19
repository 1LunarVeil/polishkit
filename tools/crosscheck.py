"""Run every rendered audit against a set of pages and report one table.

Usage:
  python tools/crosscheck.py URL [URL ...] [--json]

Why this exists: the plugin now ships three rendered audits that answer
different questions about the same page — contrast and names (page_audit),
keyboard and focus (keyboard_audit), text-spacing survival (text_spacing). When
they are run one at a time the results are read one at a time, and nobody
notices that a page scoring "0 failures everywhere" still has, say, thirteen
uncertain text pairs that no tool will ever settle.

A cross-check makes the gaps visible:

- a page with 0 FAIL and 0 UNCERTAIN across all three is genuinely clean;
- a page with 0 FAIL and many UNCERTAIN has unmeasured regions, and the count
  says how much of the page nobody has looked at;
- a page where one audit fails and the others pass tells you which clause is
  the weak one, which is the shape a real fix has.

It runs each audit in its own browser (they each launch one), so the wall time
is additive. Exit status is 1 when any audit reports a measurable failure, 2
when any audit could not verify itself.

Read-only: prints a table or JSON and writes nothing.
"""

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "polishkit" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import keyboard_audit  # noqa: E402
import page_audit  # noqa: E402
import reflow  # noqa: E402
import text_spacing  # noqa: E402
import visual_capture  # noqa: E402

AUDITS = (
    ("page", page_audit, "1.4.3 contrast, 2.5.8 targets, 4.1.2 names"),
    ("keyboard", keyboard_audit, "2.1.1/2.1.2 reach and traps, 2.4.7/1.4.11 focus"),
    ("spacing", text_spacing, "1.4.12 text-spacing survival"),
    ("reflow", reflow, "1.4.10 reflow at 320px, 1.4.4 text scale"),
)


def run_audit(module, url):
    """Call one audit's audit_url and summarise its report.

    Each module keeps its own report shape, which is deliberate — they answer
    different questions. This reads the handful of fields they share and keeps
    the rest available under `detail` for a JSON consumer.
    """
    try:
        if module is page_audit:
            payload = module.audit_url(url)
            report = module.build_report(url, payload)
        elif module is keyboard_audit:
            payload = module.audit_url(url)
            report = module.build_report(url, payload)
        elif module is reflow:
            measurements, scale_probe = module.audit_url(url)
            report = module.build_report(url, measurements, scale_probe)
        else:
            authored, overridden = module.audit_url(url)
            report = module.build_report(url, authored, overridden)
    except Exception as exc:  # noqa: BLE001 - an unverified audit claims nothing
        return {"verified": False, "reason": f"{type(exc).__name__}: {exc}",
                "fail": 0, "uncertain": 0, "review": 0}
    summary = report.get("summary") or {}
    fail = summary.get("fail")
    uncertain = summary.get("uncertain")
    review = summary.get("review")
    extra = {}
    # page_audit keeps contrast pairs, pointer targets and accessible names in
    # separate counters because they are separate clauses with separate fixes.
    # Folding them into one "fail" number was the first version's mistake: a
    # page with 0 contrast failures and 8 collapsed panels looked like it had 8
    # contrast failures, and the reading contradicted the stored benchmark for
    # no reason. They stay separate in the detail; the headline keeps the
    # contrast count, which is the one the benchmark tracks.
    if module is page_audit:
        extra = {
            "contrast_fail": summary.get("fail") or 0,
            "target_size_fail": summary.get("target_size") or 0,
            "aria_name_fail": summary.get("aria_name") or 0,
        }
        fail = extra["contrast_fail"]
        review = (summary.get("review") or 0) + (summary.get("heading_order") or 0)
    return {
        "verified": True,
        "fail": fail or 0,
        "uncertain": uncertain or 0,
        "review": review or 0,
        "detail": report,
        "extra": extra,
    }


def crosscheck(urls, verbose=False):
    rows = []
    for url in urls:
        row = {"url": url, "audits": {}}
        for name, module, _covers in AUDITS:
            if verbose:
                print(f"  {url} :: {name}", file=sys.stderr)
            row["audits"][name] = run_audit(module, url)
        rows.append(row)
    return rows


def summarise(rows):
    """One line per page: totals and the audit that carries the most weight."""
    lines = []
    unverified = 0
    for row in rows:
        cells = []
        for name, _module, _covers in AUDITS:
            result = row["audits"][name]
            if not result.get("verified"):
                cells.append(f"{name}=UNVERIFIED")
                unverified += 1
                continue
            cells.append(f"{name} {result['fail']}F/{result['uncertain']}U")
        lines.append(f"{row['url']}: " + ", ".join(cells))
    return lines, unverified


def render(rows):
    width = max((len(row["url"]) for row in rows), default=10)
    header = (f"{'page'.ljust(width)}  " +
              "  ".join(f"{name:>16}" for name, _m, _c in AUDITS))
    lines = [header, "-" * len(header)]
    for row in rows:
        cells = []
        for name, _module, _covers in AUDITS:
            result = row["audits"][name]
            if not result.get("verified"):
                cells.append(f"{'UNVERIFIED':>16}")
            else:
                cells.append(f"{str(result['fail']) + 'F ' + str(result['uncertain']) + 'U':>16}")
        lines.append(row["url"].ljust(width) + "  " + "  ".join(cells))
    lines.append("")
    lines.append("F = measurable failures, U = uncertain (unmeasured regions)")
    for name, _module, covers in AUDITS:
        lines.append(f"  {name}: {covers}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run page_audit, keyboard_audit and text_spacing against each "
                    "URL and report one table.")
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--verbose", action="store_true", help="progress on stderr")
    parser.add_argument("--allow-private", action="store_true",
                        help="allow non-public, non-loopback addresses")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    urls = []
    for raw in args.urls:
        try:
            urls.append(visual_capture.validate_url(raw, allow_private=args.allow_private))
        except visual_capture.UrlRejected as exc:
            print(json.dumps({"verified": False, "reason": f"URL rejected: {exc}"},
                             ensure_ascii=False))
            return 3

    rows = crosscheck(urls, verbose=args.verbose)
    if args.json:
        print(json.dumps({"verified": True, "pages": rows,
                          "audits": [name for name, _m, _c in AUDITS]},
                         ensure_ascii=False, indent=2))
    else:
        print(render(rows))
        lines, unverified = summarise(rows)
        if unverified:
            print(f"\n{unverified} audit run(s) could not verify anything; "
                  f"those cells claim nothing")

    if any(not result.get("verified")
           for row in rows for result in row["audits"].values()):
        return 2
    if any(result.get("fail") for row in rows for result in row["audits"].values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
