"""Generate skills/polishkit/data/palettes-corrected.csv from the vendored colors.csv.

The external review put the problem plainly: 173 of the 192 vendored palettes
have a Border below 3:1 against their Background, 30 have a Primary below 3:1,
and the lookup's answer was "here are suggested adjusted values, not applied" —
leaving every user of every release to redo the same arithmetic forever. This
tool eats that cost once: it applies the same minimal blend the lookup suggests
(toward black or white, the least amount that reaches the ratio), verifies
every pair, and writes the derived dataset beside the original, which stays
untouched and attributed in data/PROVENANCE.md.

The repair is deliberately conservative. A color moves only as far as the
ratio demands, along the axis the lookup already recommends, so hue and weight
survive and what changes is mostly lightness. When no foreground blend can
reach the ratio (a mid-grey pair that both extremes fail against), the
background moves instead; when neither can, the row is reported and the run
fails rather than shipping a dataset that still has failing pairs.

Usage:
  python tools/palette_correct.py            # (re)generate the corrected CSV
  python tools/palette_correct.py --check    # verify the file matches a fresh regeneration
"""

import argparse
import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "skills" / "polishkit" / "scripts"))

import design_lookup  # noqa: E402  (for PAIRS and the shared repair algorithm)
import wcag  # noqa: E402

ORIGINAL = ROOT / "skills" / "polishkit" / "data" / "colors.csv"
CORRECTED = ROOT / "skills" / "polishkit" / "data" / "palettes-corrected.csv"
MAX_PASSES = 8


def _read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, [{k: (v or "").strip() for k, v in row.items()}
                                   for row in reader]


def _repair_background(fg, bg, required):
    """Blend the background toward black or white until the pair passes.

    The mirror image of design_lookup._repair_suggestion, used only when no
    foreground blend can reach the ratio (both extremes fail, which happens
    when foreground and background sit near the same mid luminance). The
    direction needing the smaller factor wins; (None, None) when neither
    extreme reaches the ratio.
    """
    best = None
    for direction, label in (((0.0, 0.0, 0.0), "black"), ((1.0, 1.0, 1.0), "white")):
        bg_rgb = wcag.parse_color(bg)

        def blended(factor, bg_rgb=bg_rgb, direction=direction):
            rgb = tuple(b + (d - b) * factor for b, d in zip(bg_rgb, direction))
            return "#%02x%02x%02x" % tuple(round(channel * 255) for channel in rgb)

        if wcag.contrast_ratio(fg, blended(1.0)) < required:
            continue
        lo, hi = 0.0, 1.0
        for _ in range(20):
            mid = (lo + hi) / 2
            if wcag.contrast_ratio(fg, blended(mid)) >= required:
                hi = mid
            else:
                lo = mid
        if best is None or hi < best[0]:
            best = (hi, blended(hi), label)
    return (best[1], best[2]) if best else (None, None)


def _failing_pairs(row):
    failures = []
    for fg_field, bg_field, kind, required in design_lookup.PAIRS:
        fg, bg = row.get(fg_field, ""), row.get(bg_field, "")
        try:
            ratio = wcag.contrast_ratio(fg, bg)
        except ValueError:
            continue  # a non-colour cell: the lookup reports it, this keeps it
        if ratio < required:
            failures.append((fg_field, bg_field, required, ratio))
    return failures


def _correct_row(row):
    """Repair every failing pair in one palette row, in place.

    Passes repeat because a Background change (allowed only when no foreground
    blend reaches the ratio) re-weights the other pairs that share that
    background. Returns (sorted changed fields, remaining failure strings).
    """
    changed = set()
    for _ in range(MAX_PASSES):
        progressed = False
        for fg_field, bg_field, required, _ratio in _failing_pairs(row):
            fg, bg = row[fg_field], row[bg_field]
            suggestion, _label = design_lookup._repair_suggestion(fg, bg, required)
            if suggestion:
                row[fg_field] = suggestion
                changed.add(fg_field)
            else:
                repaired, _label = _repair_background(fg, bg, required)
                if not repaired:
                    continue
                row[bg_field] = repaired
                changed.add(bg_field)
            progressed = True
        if not progressed:
            break
    remaining = [f"{fg} on {bg}: {wcag.contrast_ratio(row[fg], row[bg]):.2f}:1 "
                 f"(need {need:g})"
                 for fg, bg, need, _r in _failing_pairs(row)]
    return sorted(changed), remaining


def regenerate():
    """Return (fieldnames, corrected rows, summary lines) without writing."""
    fieldnames, rows = _read_rows(ORIGINAL)
    if not rows:
        raise SystemExit(f"palette_correct: no rows in {ORIGINAL}")
    tally, remaining_rows, touched = {}, [], 0
    for row in rows:
        changed, remaining = _correct_row(row)
        if remaining:
            remaining_rows.append((row["No"], row["Product Type"], remaining))
            continue
        if changed:
            touched += 1
            for field in changed:
                tally[field] = tally.get(field, 0) + 1
            row["Notes"] = " ".join(
                part for part in (row.get("Notes", ""),
                                  f"[contrast-corrected: {', '.join(changed)}]") if part)
    summary = []
    if touched:
        summary.append(f"corrected {touched} of {len(rows)} rows: "
                       + ", ".join(f"{field} x{count}" for field, count in sorted(tally.items())))
    else:
        summary.append(f"no row needed correction ({len(rows)} rows)")
    if remaining_rows:
        for no, product, failures in remaining_rows:
            summary.append(f"row {no} ({product}) still fails: {'; '.join(failures)}")
    return fieldnames, rows, summary


def _serialize(fieldnames, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate or verify data/palettes-corrected.csv.")
    parser.add_argument("--check", action="store_true",
                        help="verify the corrected CSV matches a fresh regeneration; exit 1 on drift")
    args = parser.parse_args(argv)

    fieldnames, rows, summary = regenerate()
    for line in summary:
        print(f"  {line}")
    if any("still fails" in line for line in summary):
        return 1

    payload = _serialize(fieldnames, rows)
    if args.check:
        if not CORRECTED.is_file():
            print(f"  - {CORRECTED.name} does not exist; run without --check first", file=sys.stderr)
            return 1
        if CORRECTED.read_text(encoding="utf-8") != payload:
            print(f"  - {CORRECTED.name} differs from a fresh regeneration; "
                  f"run tools/palette_correct.py to rewrite it", file=sys.stderr)
            return 1
        print(f"{CORRECTED.name} matches the vendored colors.csv after correction")
        return 0

    with CORRECTED.open("w", encoding="utf-8", newline="") as handle:
        handle.write(payload)
    print(f"wrote {CORRECTED.relative_to(ROOT)} "
          f"(original {ORIGINAL.name} left untouched)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
