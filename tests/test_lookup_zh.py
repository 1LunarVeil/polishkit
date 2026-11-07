"""Tests for Chinese keyword expansion and palette repair in design_lookup.py.

data/zh-keywords.csv is original content of this plugin (the vendored CSVs
stay untouched); every en_tokens value was chosen against the real vocabulary
of products.csv / styles.csv / charts.csv, and the longest-match pair
金融 vs 金融科技 proves the greedy matcher.
"""

import io
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "skills" / "polishkit" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import design_lookup  # noqa: E402
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


class ChineseQueryTests(unittest.TestCase):
    def test_portfolio_query_resolves_with_trace(self):
        code, out = run(design_lookup.main, ["作品集"])
        self.assertEqual(code, 0)
        self.assertIn("# Detail: Portfolio/Personal", out)
        self.assertIn("# zh mappings: 作品集 → portfolio", out)

    def test_longest_match_wins_for_fintech(self):
        code, out = run(design_lookup.main, ["金融科技"])
        self.assertEqual(code, 0)
        self.assertIn("# Detail: Fintech/Crypto", out)
        self.assertIn("金融科技 → fintech crypto blockchain", out)

    def test_shorter_term_maps_to_banking(self):
        code, out = run(design_lookup.main, ["金融"])
        self.assertEqual(code, 0)
        self.assertIn("# Detail: Banking/Traditional Finance", out)

    def test_mixed_chinese_and_english_query(self):
        code, out = run(design_lookup.main, ["暗色 dashboard"])
        self.assertEqual(code, 0)
        self.assertIn("暗色 → dark", out)
        self.assertIn("dashboard", out.lower())

    def test_full_width_input_normalizes(self):
        code, out = run(design_lookup.main, ["天气　ａｐｐ"])
        self.assertEqual(code, 0)
        self.assertIn("# Detail: Weather App", out)

    def test_unknown_cjk_chars_are_dropped(self):
        code, out = run(design_lookup.main, ["暗色龘餮 dashboard"])
        self.assertEqual(code, 0)
        self.assertIn("暗色 → dark", out)
        self.assertNotIn("龘", out)

    def test_only_unknown_chars_exit_one_and_list_types(self):
        code, out = run(design_lookup.main, ["龘餮"])
        self.assertEqual(code, 1)
        self.assertIn("Product types in the data", out)


class PaletteRepairTests(unittest.TestCase):
    def test_repair_moves_toward_black_on_light_background(self):
        suggestion, direction = design_lookup._repair_suggestion("#949494", "#ffffff", 4.5)
        self.assertEqual(direction, "black")
        self.assertGreaterEqual(wcag.contrast_ratio(suggestion, "#ffffff"), 4.5)

    def test_repair_moves_toward_white_on_dark_background(self):
        suggestion, direction = design_lookup._repair_suggestion("#3a3f4a", "#101418", 4.5)
        self.assertEqual(direction, "white")
        self.assertGreaterEqual(wcag.contrast_ratio(suggestion, "#101418"), 4.5)

    def test_hopeless_pair_reports_no_suggestion(self):
        # #808080 has ~0.19 relative luminance, so the repair moves the
        # foreground toward white — and even pure white tops out below 4.5:1,
        # which is exactly the "move the background instead" case.
        suggestion, direction = design_lookup._repair_suggestion("#7a7a7a", "#808080", 4.5)
        self.assertIsNone(suggestion)
        self.assertEqual(direction, "white")

    def test_every_fail_prints_a_suggestion_line(self):
        code, out = run(design_lookup.main, ["saas dashboard"])
        self.assertEqual(code, 0)
        if "FAIL" in out:
            self.assertIn("suggested:", out)
            self.assertIn("not applied", out)

    def test_typography_caveat_names_the_csp_conflict(self):
        code, out = run(design_lookup.main, ["saas dashboard"])
        self.assertEqual(code, 0)
        self.assertIn("self-host", out)


if __name__ == "__main__":
    unittest.main()
