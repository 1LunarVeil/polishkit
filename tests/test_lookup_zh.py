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


class PlatformTests(unittest.TestCase):
    """The --platform dimension indexes references/native-feel.md.

    The vendored ux-guidelines.csv has no desktop rows (its Platform column is
    All/Web/Mobile/VisionOS), so the macOS and Windows checklists live in the
    lookup itself and point back at the reference. These tests pin the mapping
    and the backward compatibility: with no --platform, output is the All/Web
    set it always was.
    """

    def test_default_platform_keeps_the_all_and_web_rows(self):
        allowed, desktop = design_lookup._platform_rows("all")
        self.assertEqual(allowed, ("All", "Web"))
        self.assertIsNone(desktop)

    def test_web_platform_is_the_default_set(self):
        self.assertEqual(design_lookup._platform_rows("web"), (("All", "Web"), None))

    def test_mobile_narrows_to_all_and_mobile(self):
        allowed, desktop = design_lookup._platform_rows("mobile")
        self.assertEqual(allowed, ("All", "Mobile"))
        self.assertIsNone(desktop)

    def test_visionos_narrows_to_all_and_visionos(self):
        allowed, _ = design_lookup._platform_rows("visionos")
        self.assertEqual(allowed, ("All", "VisionOS"))

    def test_macos_adds_the_desktop_checklist_to_web_rows(self):
        allowed, desktop = design_lookup._platform_rows("macos")
        self.assertEqual(allowed, ("All", "Web"))
        self.assertEqual(desktop, "macos")

    def test_windows_adds_the_desktop_checklist(self):
        _allowed, desktop = design_lookup._platform_rows("windows")
        self.assertEqual(desktop, "windows")

    def test_desktop_covers_both_platforms(self):
        _allowed, desktop = design_lookup._platform_rows("desktop")
        self.assertEqual(desktop, "desktop")

    def test_every_platform_choice_is_handled(self):
        for choice in design_lookup.PLATFORM_CHOICES:
            with self.subTest(choice=choice):
                design_lookup._platform_rows(choice)  # must not raise

    def test_macos_checklist_carries_the_reference_numbers(self):
        rules = " ".join(design_lookup.DESKTOP_PLATFORMS["macos"]["rules"])
        self.assertIn("13pt", rules)
        self.assertIn("44x44pt", rules)
        self.assertIn("28x28pt", rules)
        # The HIG has no Light weights at UI sizes; native-feel.md says so.
        self.assertIn("no Light weights", rules)

    def test_windows_checklist_carries_the_reference_numbers(self):
        rules = " ".join(design_lookup.DESKTOP_PLATFORMS["windows"]["rules"])
        self.assertIn("Mica", rules)
        self.assertIn("8", rules)
        self.assertIn("32/40", rules)

    def test_macos_platform_prints_the_checklist(self):
        code, out = run(design_lookup.main,
                        ["dashboard", "--ux", "--platform", "macos"])
        self.assertEqual(code, 0)
        self.assertIn("macOS platform checklist", out)
        self.assertIn("trailing ellipsis", out)

    def test_desktop_platform_prints_both_checklists(self):
        code, out = run(design_lookup.main,
                        ["dashboard", "--ux", "--platform", "desktop"])
        self.assertEqual(code, 0)
        self.assertIn("### macOS", out)
        self.assertIn("### Windows", out)
        self.assertIn("never mix", out)

    def test_a_platform_without_ux_still_prints_the_checklist(self):
        code, out = run(design_lookup.main,
                        ["dashboard", "--platform", "windows"])
        self.assertEqual(code, 0)
        self.assertIn("Windows platform checklist", out)

    def test_web_platform_prints_no_desktop_checklist(self):
        code, out = run(design_lookup.main,
                        ["dashboard", "--ux", "--platform", "web"])
        self.assertEqual(code, 0)
        self.assertNotIn("platform checklist", out)

    def test_mobile_platform_reports_its_row_set(self):
        code, out = run(design_lookup.main,
                        ["dashboard", "--ux", "--platform", "mobile"])
        self.assertEqual(code, 0)
        self.assertIn("All/Mobile rows", out)


if __name__ == "__main__":
    unittest.main()
