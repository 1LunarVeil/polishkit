"""Tests for the derived, contrast-corrected palette set and its generator.

The external review's third headline: 173 of 192 vendored palettes ship a
border below 3:1 and the lookup's answer was "here are suggested values, not
applied" — a per-user tax collected forever. data/palettes-corrected.csv pays
it once. What is pinned here:

- every shipped row passes every pair the lookup checks (measured afresh
  here, not trusted from the generator's own run);
- identity columns match the vendored file row for row;
- exactly the fields the Notes annotation names differ from the vendored
  values — minimal intervention, provable;
- the alpha compositing in wcag.py, which the rgba() rows depend on.
"""

import csv
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "skills" / "polishkit" / "scripts"))

import design_lookup  # noqa: E402
import palette_correct  # noqa: E402
import wcag  # noqa: E402

DATA = ROOT / "skills" / "polishkit" / "data"


def _rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


CORRECTED = _rows(DATA / "palettes-corrected.csv")
ORIGINAL = _rows(DATA / "colors.csv")


class CorrectedDatasetTests(unittest.TestCase):
    def test_every_row_passes_every_pair(self):
        # Measured here with the same formulas, independently of the
        # generator's own verification — a dataset that ships as "the pairs
        # pass" must survive a second reading.
        failures = []
        for row in CORRECTED:
            for fg_field, bg_field, kind, required in design_lookup.PAIRS:
                fg, bg = row.get(fg_field, ""), row.get(bg_field, "")
                try:
                    ratio = wcag.contrast_ratio(fg, bg)
                except ValueError:
                    failures.append(f"row {row['No']}: unparsable {fg_field}={fg!r}")
                    continue
                if ratio < required:
                    failures.append(f"row {row['No']} ({row['Product Type']}): "
                                    f"{fg_field} on {bg_field} = {ratio:.2f}:1 < {required:g}")
        self.assertEqual(failures, [])

    def test_identity_columns_match_the_vendored_file(self):
        self.assertEqual(len(CORRECTED), len(ORIGINAL), "row count changed")
        for corrected, original in zip(CORRECTED, ORIGINAL):
            self.assertEqual(corrected["No"], original["No"])
            self.assertEqual(corrected["Product Type"], original["Product Type"],
                             "rows desynchronised — a correction landed on the wrong product")

    def test_exactly_the_annotated_fields_differ(self):
        for corrected, original in zip(CORRECTED, ORIGINAL):
            note = corrected.get("Notes", "")
            marker = "contrast-corrected: "
            if marker not in note:
                changed = [field for field in design_lookup.PALETTE_FIELDS
                           if corrected.get(field) != original.get(field)]
                self.assertEqual(changed, [],
                                 f"row {corrected['No']} changed {changed} without an annotation")
                continue
            annotated = note.split(marker)[1].split("]")[0].replace(" ", "").split(",")
            changed = [field for field in design_lookup.PALETTE_FIELDS
                       if corrected.get(field) != original.get(field)]
            self.assertEqual(sorted(changed), sorted(annotated),
                             f"row {corrected['No']}: changed {changed}, "
                             f"annotated {annotated}")

    def test_regenerating_reproduces_the_shipped_file(self):
        fieldnames, rows, summary = palette_correct.regenerate()
        self.assertFalse(any("still fails" in line for line in summary))
        self.assertEqual(palette_correct._serialize(fieldnames, rows),
                         (DATA / "palettes-corrected.csv").read_text(encoding="utf-8"))


class AlphaCompositingTests(unittest.TestCase):
    """The rgba() rows were measured as opaque before: an 8%-alpha white over
    a dark background read 17.85:1. The composite is the honest number."""

    def test_known_composite_values(self):
        self.assertEqual(wcag.composite("rgba(255,0,0,0.5)", "#ffffff"), "#ff8080")
        self.assertEqual(wcag.composite("rgba(255,255,255,50%)", "#000000"), "#808080")

    def test_opaque_input_passes_through(self):
        self.assertEqual(wcag.composite("#ff0000", "#ffffff"), "#ff0000")

    def test_near_invisible_alpha_is_not_read_as_opaque(self):
        opaque = wcag.contrast_ratio("rgba(255,255,255,1)", "#0f172a")
        ghost = wcag.contrast_ratio("rgba(255,255,255,0.08)", "#0f172a")
        self.assertGreater(opaque, 10.0)
        self.assertLess(ghost, 2.0, "an 8%-alpha white must not measure as pure white")

    def test_parse_color_still_returns_three_channels(self):
        self.assertEqual(len(wcag.parse_color("rgba(255,0,0,0.5)")), 3)
        self.assertEqual(len(wcag.parse_color("#ff0000")), 3)


class RepairAlgorithmTests(unittest.TestCase):
    def test_suggestion_starts_from_the_composited_color(self):
        # Blending raw white channels would have "suggested" no change for an
        # rgba foreground; from the effective colour a suggestion exists.
        suggestion, _label = design_lookup._repair_suggestion(
            "rgba(255,255,255,0.08)", "#0f172a", 3.0)
        self.assertIsNotNone(suggestion)
        self.assertGreaterEqual(wcag.contrast_ratio(suggestion, "#0f172a"), 3.0)

    def test_background_moves_when_no_foreground_blend_reaches(self):
        # A mid-grey pair against a mid-grey background: toward black the
        # foreground stalls under 4.5, so the background must move instead.
        fg, bg = "#737373", "#6b6b6b"
        suggestion, _label = design_lookup._repair_suggestion(fg, bg, 4.5)
        if suggestion is not None:
            self.skipTest("this pair reached the ratio from the foreground; "
                          "the fallback is exercised elsewhere")
        repaired, _label = palette_correct._repair_background(fg, bg, 4.5)
        self.assertIsNotNone(repaired)
        self.assertGreaterEqual(wcag.contrast_ratio(fg, repaired), 4.5)

    def test_row_correction_converges(self):
        _fieldnames, rows = palette_correct._read_rows(palette_correct.ORIGINAL)
        row = rows[0]
        changed, remaining = palette_correct._correct_row(row)
        self.assertEqual(remaining, [])
        self.assertIn("Border", changed)


if __name__ == "__main__":
    unittest.main()
