"""Tests for the color tools: APCA in wcag.py and the Machado simulation.

APCA anchors were derived from the verified 0.0.98G-4g algorithm (constants
quoted verbatim from Myndex/apca-w3 src/apca-w3.js) and cross-checked against
published example values; WCAG ratios stay the normative gate. The Machado
matrices are the published severity-10 values; greys must survive them (row
sums are 1), and pure red under deuteranopia lands in the olive range.
"""

import io
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "skills" / "polishkit" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import color_sim  # noqa: E402
import wcag  # noqa: E402


def run(main, argv):
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="utf-8", write_through=True)
    original_out, original_err = sys.stdout, sys.stderr
    sys.stdout = stream
    sys.stderr = io.StringIO()
    try:
        code = main(argv)
    except SystemExit as exc:
        code = exc.code
    finally:
        sys.stdout, sys.stderr = original_out, original_err
    stream.flush()
    return code, raw.getvalue().decode("utf-8")


class ApcTests(unittest.TestCase):
    def test_published_anchor_values(self):
        # Black on white is the strongest BoW pair; white on black the WoB one.
        self.assertAlmostEqual(wcag.apca_contrast("#000000", "#ffffff"), 106.0, places=1)
        self.assertAlmostEqual(wcag.apca_contrast("#ffffff", "#000000"), -107.9, places=1)
        # Mid grey on white, hand-derived from the verified constants.
        self.assertAlmostEqual(wcag.apca_contrast("#767676", "#ffffff"), 71.6, places=1)

    def test_sign_convention_follows_polarity(self):
        self.assertGreater(wcag.apca_contrast("#111111", "#eeeeee"), 0)
        self.assertLess(wcag.apca_contrast("#eeeeee", "#111111"), 0)

    def test_no_difference_reports_zero(self):
        self.assertEqual(wcag.apca_contrast("#808080", "#808080"), 0.0)

    def test_level_labels_are_monotonic(self):
        labels = (wcag._apca_level(v) for v in (92, 76, 61, 46, 31, 16, 5))
        self.assertEqual(list(labels), [
            "fluent body preferred", "body minimum", "large/bold minimum",
            "headline minimum", "very large or disabled minimum",
            "non-text/spot minimum", "fails even spot text",
        ])

    def test_cli_apca_flag(self):
        code, out = run(wcag.main, ["#111111", "#eeeeee", "--apca"])
        self.assertEqual(code, 0)
        self.assertIn("APCA Lc +", out)
        self.assertIn("draft", out)

    def test_cli_without_apca_is_unchanged(self):
        code, out = run(wcag.main, ["#111111", "#eeeeee"])
        self.assertEqual(code, 0)
        self.assertNotIn("APCA", out)


class SimulateTests(unittest.TestCase):
    def test_greys_are_invariant_under_all_three_matrices(self):
        for value in ("#808080", "#1a1a1a", "#f2f2f2"):
            rgb = wcag.parse_color(value)
            for kind in color_sim.ORDER:
                out = color_sim.simulate(rgb, kind)
                for channel, original in zip(out, rgb):
                    self.assertAlmostEqual(channel, original, delta=0.01, msg=f"{value} {kind}")

    def test_red_under_deuteranopia_lands_in_the_olive_range(self):
        out = color_sim.simulate((1.0, 0.0, 0.0), "deuteranopia")
        eight_bit = tuple(round(channel * 255) for channel in out)
        for simulated, expected in zip(eight_bit, (163, 144, 0)):
            self.assertLess(abs(simulated - expected), 4)

    def test_red_and_green_pair_collapses_under_deuteranopia(self):
        original, rows = color_sim.pair_report("#ff0000", "#00ff00")
        self.assertAlmostEqual(original, 2.91, places=1)
        deuteranopia = dict((kind, remaining) for kind, _, _, remaining in rows)
        self.assertLess(deuteranopia["deuteranopia"], original)

    def test_hex_output_is_parseable(self):
        rgb = wcag.parse_color("#2563eb")
        for kind in color_sim.ORDER:
            self.assertEqual(len(color_sim._hex(color_sim.simulate(rgb, kind))), 7)

    def test_cli_check_reports_the_collapse(self):
        code, out = run(color_sim.main, ["#ff0000", "#00ff00", "--check"])
        self.assertEqual(code, 0)
        self.assertIn("2.91", out)
        self.assertIn("COLLAPSES", out)

    def test_cli_table_prints_all_three_kinds(self):
        code, out = run(color_sim.main, ["#2563eb"])
        self.assertEqual(code, 0)
        for kind in color_sim.ORDER:
            self.assertIn(kind, out)

    def test_check_requires_exactly_two_colors(self):
        code, _ = run(color_sim.main, ["#ff0000", "--check"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
