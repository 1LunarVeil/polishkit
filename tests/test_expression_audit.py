"""Browser-free tests for expression_audit.py.

The tool reads how a page allocates attention on its first screen. What is
pinned here is the arithmetic and the restraint:

- a skipped size rung is only raised when the band is thin *and* not painted,
  because a photography hero legitimately has a void under its title;
- a page-painted background or a large image in the band downgrades the
  emptiness reading to uncertain rather than reporting it as a defect;
- nothing the tool reports can fail a build.

The rewrite this file covers replaced a single "type ratio" score. Two tests
record why: the ratio measured the largest text on the *whole page*, so a
decorative numeral 2000px down decided the score, and it said nothing about
whether the loud thing deserved to be loud.
"""

import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "skills" / "polishkit" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import expression_audit  # noqa: E402


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


def page(**overrides):
    """One first-screen payload: a dense panel with a display figure."""
    base = {
        "viewport": {"w": 1440, "h": 900},
        "body_size": 14,
        "loud": {"tag": "span#fig", "text": "12.9", "size": 88, "weight": 300,
                 "top": 90, "bottom": 207},
        "band": {"lo": 90, "hi": 380, "other_items": 39, "visual_items": []},
        "gap_below": -1,
        "column": {"height": 376, "covered": 376, "items": 34},
        "ladder": [88, 30, 20, 15, 14, 13, 12],
        "size_counts": {"88": 1, "30": 1, "20": 1, "15": 20, "14": 40, "13": 20, "12": 15},
        "competitors": [],
        "hero_items": 98,
        "h1": {"text": "ZhuLong", "size": 15, "above_fold": True},
        "page_fill": None,
        "capped": False,
    }
    base.update(overrides)
    return base


def sparse_page(**overrides):
    """B3's shape: a big figure over a thin, unpainted band."""
    base = page(
        loud={"tag": "div#big-fig", "text": "£1,847", "size": 70, "weight": 300,
              "top": 174, "bottom": 244},
        band={"lo": 139, "hi": 349, "other_items": 11, "visual_items": []},
        gap_below=78,
        column={"height": 305, "covered": 128, "items": 19},
        ladder=[70, 22, 21, 15, 14, 13, 12],
        competitors=[],
        hero_items=51,
        h1={"text": "Mill & Crumb", "size": 21, "above_fold": True},
        page_fill=None,
    )
    base.update(overrides)
    return base


def photo_page(**overrides):
    """B4's shape: same geometry as the sparse page, painted by a photograph."""
    base = sparse_page(
        loud={"tag": "span.l2", "text": "above the water", "size": 92,
              "weight": 400, "top": 633, "bottom": 725},
        gap_below=64,
        column={"height": 267, "covered": 141, "items": 15},
        ladder=[92, 25, 18, 15, 14, 13],
        hero_items=15,
        page_fill="linear-gradient(rgba(0,0,0,0), rgb(20,30,26))",
    )
    base.update(overrides)
    return base


class ColumnFillTests(unittest.TestCase):
    def test_fill_is_covered_over_height(self):
        self.assertAlmostEqual(expression_audit.column_fill(page()), 100.0)

    def test_a_thin_column_reports_its_share(self):
        self.assertAlmostEqual(
            expression_audit.column_fill(page(column={"height": 305, "covered": 128,
                                                     "items": 19})),
            42.0)

    def test_zero_height_is_zero_not_a_crash(self):
        self.assertEqual(
            expression_audit.column_fill(page(column={"height": 0, "covered": 0})), 0.0)

    def test_fill_never_exceeds_one_hundred(self):
        self.assertEqual(
            expression_audit.column_fill(page(column={"height": 100,
                                                     "covered": 250})), 100.0)


class DensityTests(unittest.TestCase):
    def test_density_is_items_per_100k_px(self):
        # 98 items over 1440x900 = 1296000 px² → 98 * 1e5 / 1296000 ≈ 7.56
        self.assertAlmostEqual(expression_audit.density(page()), 7.6, places=1)

    def test_a_missing_viewport_is_zero(self):
        self.assertEqual(expression_audit.density(page(viewport={})), 0.0)


class LadderGapTests(unittest.TestCase):
    def test_a_ladder_with_no_skipped_rung_yields_nothing(self):
        # 88 → 30 is 2.9x, under the 1.8 factor threshold? No: 2.9 > 1.8, so this
        # ladder does skip. Use a genuinely continuous ladder to test the empty case.
        self.assertEqual(
            expression_audit.ladder_gaps([48, 32, 24, 16], 16), [])

    def test_the_display_jump_is_reported(self):
        self.assertEqual(
            expression_audit.ladder_gaps([70, 22, 15], 14), [(70, 22)])

    def test_body_size_is_appended_when_missing(self):
        gaps = expression_audit.ladder_gaps([70, 22], 14)
        self.assertEqual(gaps, [(70, 22)])

    def test_an_empty_ladder_yields_nothing(self):
        self.assertEqual(expression_audit.ladder_gaps([], 16), [])
        self.assertEqual(expression_audit.ladder_gaps(None, 16), [])

    def test_a_single_step_still_compares_against_body(self):
        # One display size over body is one jump, and 40/16 = 2.5x is past the
        # factor, so it is reported: a lone 40px heading over 16px text has no
        # intermediate step, which is exactly what the check is for.
        self.assertEqual(expression_audit.ladder_gaps([40], 16), [(40, 16)])


class PaintedBandTests(unittest.TestCase):
    def test_a_visual_element_in_the_band_counts_as_painted(self):
        painted = page(band={"lo": 0, "hi": 300, "other_items": 4,
                             "visual_items": [{"tag": "img.plate", "width": 1200,
                                               "height": 600}]})
        self.assertTrue(expression_audit.band_is_painted(painted))

    def test_a_page_painted_background_counts_as_painted(self):
        self.assertTrue(expression_audit.band_is_painted(photo_page()))

    def test_a_text_only_band_is_not_painted(self):
        self.assertFalse(expression_audit.band_is_painted(sparse_page()))

    def test_visual_fill_reports_the_count_and_the_background(self):
        count, fill = expression_audit.visual_fill(photo_page())
        self.assertEqual(count, 0)
        self.assertIn("linear-gradient", fill)


class QuestionTests(unittest.TestCase):
    def test_the_loud_element_question_names_size_and_text(self):
        questions = expression_audit.attention_questions(page())
        self.assertTrue(questions)
        self.assertIn("span#fig", questions[0])
        self.assertIn("88px", questions[0])
        self.assertIn("12.9", questions[0])
        self.assertIn("Is that the thing this screen exists to show?", questions[0])

    def test_a_small_h1_under_a_large_figure_is_questioned(self):
        # B3: the product heading is 21px while one measurement is 70px.
        questions = expression_audit.attention_questions(sparse_page())
        joined = " ".join(questions)
        self.assertIn("Mill & Crumb", joined)
        self.assertIn("21px", joined)
        self.assertIn("confirm the figure is the more important", joined)

    def test_a_heading_close_to_display_size_is_not_questioned(self):
        # B1: h1 at 15px vs a figure at 88px would trigger, so this test uses a
        # page whose h1 is large enough not to.
        lively = page(h1={"text": "ZhuLong", "size": 60, "above_fold": True})
        joined = " ".join(expression_audit.attention_questions(lively))
        self.assertNotIn("confirm the figure is the more important", joined)

    def test_the_sparse_unpainted_band_raises_the_ladder_question(self):
        joined = " ".join(expression_audit.attention_questions(sparse_page()))
        self.assertIn("the size ladder skips", joined)
        self.assertIn("70px → 22px", joined)
        self.assertIn("reads as decorative", joined)

    def test_the_same_geometry_painted_does_not_raise_it(self):
        # REGRESSION: B4 has B3's exact geometry — a skipped rung over a 53%
        # column with 64px of blank — and the blank is a horizon photograph.
        joined = " ".join(expression_audit.attention_questions(photo_page()))
        self.assertNotIn("reads as decorative", joined)
        self.assertIn("the page paints its own background", joined)

    def test_a_well_filled_column_does_not_raise_the_ladder_question(self):
        # B2: skips 102→22 but fills 77% of its column, which is the design of a
        # photography hero.
        filled = page(ladder=[102, 22, 17, 15], column={"height": 100,
                                                        "covered": 77, "items": 5},
                      page_fill=None)
        joined = " ".join(expression_audit.attention_questions(filled))
        self.assertNotIn("reads as decorative", joined)

    def test_competing_foci_are_reported(self):
        competing = page(competitors=[{"tag": "h2#a", "size": 80, "text": "One"},
                                      {"tag": "h2#b", "size": 76, "text": "Two"}])
        joined = " ".join(expression_audit.attention_questions(competing))
        self.assertIn("2 elements compete", joined)
        self.assertIn("cancel each other", joined)

    def test_a_page_with_no_text_asks_nothing(self):
        self.assertEqual(
            expression_audit.attention_questions(page(loud={}, band={})), [])


class ClassifyTests(unittest.TestCase):
    def test_nothing_is_ever_a_failure(self):
        for payload in (page(), sparse_page(), photo_page()):
            _measures, reviews = expression_audit.classify(payload)
            self.assertEqual(_measures, [])
            self.assertTrue(reviews)

    def test_a_dense_first_screen_raises_no_ladder_finding(self):
        _measures, reviews = expression_audit.classify(page())
        self.assertNotIn("LADDER", [item["check"] for item in reviews])

    def test_a_thin_unpainted_screen_raises_the_ladder_finding(self):
        _measures, reviews = expression_audit.classify(sparse_page())
        self.assertIn("LADDER", [item["check"] for item in reviews])

    def test_a_painted_screen_raises_uncertain_instead(self):
        _measures, reviews = expression_audit.classify(photo_page())
        checks = [(item["check"], item["status"]) for item in reviews]
        self.assertIn(("VISUAL-FILL", "uncertain"), checks)
        self.assertNotIn("LADDER", [item["check"] for item in reviews])

    def test_density_is_always_reported(self):
        for payload in (page(), sparse_page()):
            _measures, reviews = expression_audit.classify(payload)
            self.assertIn("DENSITY", [item["check"] for item in reviews])


class ReportTests(unittest.TestCase):
    def test_has_measurable_fail_is_always_false(self):
        report = expression_audit.build_report("http://x/", sparse_page())
        self.assertFalse(expression_audit.has_measurable_fail(report))

    def test_summary_separates_review_from_uncertain(self):
        report = expression_audit.build_report("http://x/", photo_page())
        self.assertEqual(report["summary"]["fail"], 0)
        self.assertGreaterEqual(report["summary"]["uncertain"], 1)

    def test_the_manual_items_are_named(self):
        report = expression_audit.build_report("http://x/", page())
        self.assertEqual(len(report["manual"]), 5)
        self.assertTrue(any("signature" in item for item in report["manual"]))

    def test_the_text_report_lists_questions_and_manual_items(self):
        report = expression_audit.build_report("http://x/", sparse_page())
        text = expression_audit.render_text(report)
        self.assertIn("Questions to answer", text)
        self.assertIn("Left to the polish pass", text)
        self.assertIn("no exit status", text)
        self.assertIn("reported, not judged", text)

    def test_a_page_without_text_says_so(self):
        report = expression_audit.build_report("http://x/", page(loud={}, band={}))
        self.assertIn("No text found", expression_audit.render_text(report))

    def test_json_output_is_parseable(self):
        with mock.patch.object(expression_audit, "audit_url",
                               return_value=page()):
            code, output = run(expression_audit.main, ["http://127.0.0.1:1/", "--json"])
        report = json.loads(output)
        self.assertTrue(report["verified"])
        self.assertIn("column_fill", report["metrics"])

    def test_a_failed_audit_claims_nothing(self):
        def boom(url, **kwargs):
            raise RuntimeError("no browser")

        with mock.patch.object(expression_audit, "audit_url", side_effect=boom):
            code, output = run(expression_audit.main, ["http://127.0.0.1:1/"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output)["verified"])

    def test_url_rejection_exits_three(self):
        code, _output = run(expression_audit.main, ["file:///etc/passwd"])
        self.assertEqual(code, 3)


class RatioTests(unittest.TestCase):
    def test_the_ratio_is_kept_as_a_reference_number(self):
        self.assertAlmostEqual(expression_audit.ratio_to_body(page()), 6.29, places=2)

    def test_a_zero_body_gives_zero(self):
        self.assertEqual(
            expression_audit.ratio_to_body(page(body_size=0)), 0.0)

    def test_it_never_appears_as_a_finding(self):
        # The rewrite's whole point: the ratio is reported, not judged.
        _measures, reviews = expression_audit.classify(page())
        self.assertNotIn("TYPE-RATIO", [item["check"] for item in reviews])


if __name__ == "__main__":
    unittest.main()
