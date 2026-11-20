"""Browser-free tests for expression_audit.py.

What is pinned here is the arithmetic and the honesty: which numbers the tool
reports, and that nothing it reports can fail a build. Two of these tests
record defects a real page caught first:

- counting first font-family names reported five "families" on a page that had
  three roles, because `Segoe UI Light` is a weight of `Segoe UI` and
  `Cascadia Code`/`Consolas` are one mono stack;
- a page that set tracking to exactly -0.03em measured as "outside -0.03 to
  -0.01" through float error.
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


def sample(**overrides):
    base = {"tag": "p", "size": 16, "weight": 400, "line_height_ratio": 1.6,
            "letter_spacing_em": 0.0, "family": "Segoe UI",
            "family_declaration": "Segoe UI, sans-serif", "text": "sample"}
    base.update(overrides)
    return base


def payload(samples=None, sizes=None, weights=None, body_size=16, **overrides):
    samples = samples if samples is not None else [sample()]
    base = {
        "body_size": body_size,
        "sizes": sizes if sizes is not None else {16: len(samples)},
        "weights": weights if weights is not None else {400: len(samples)},
        "samples": samples,
        "capped": False,
        "viewport_width": 1440,
    }
    base.update(overrides)
    return base


class TypeRatioTests(unittest.TestCase):
    def test_the_ratio_is_display_over_body(self):
        self.assertAlmostEqual(
            expression_audit.type_ratio(payload(sizes={16: 3, 88: 1}, body_size=14)),
            88 / 14)

    def test_no_text_gives_zero(self):
        self.assertEqual(expression_audit.type_ratio(payload(sizes={})), 0.0)

    def test_a_zero_body_size_does_not_divide_by_zero(self):
        self.assertEqual(expression_audit.type_ratio(payload(sizes={16: 1}, body_size=0)), 0.0)

    def test_a_missing_body_falls_back_to_16(self):
        self.assertAlmostEqual(
            expression_audit.type_ratio({"sizes": {32: 1}}), 2.0)

    def test_three_times_body_passes(self):
        status, _severity, message = expression_audit.ratio_verdict(3.0)
        self.assertEqual(status, "pass")
        self.assertIn("3x floor", message)

    def test_below_two_and_a_half_is_called_flat(self):
        status, _severity, message = expression_audit.ratio_verdict(1.25)
        self.assertEqual(status, "FAIL")
        self.assertIn("reads flat", message)

    def test_between_two_and_a_half_and_three_is_also_flat(self):
        status, _severity, message = expression_audit.ratio_verdict(2.7)
        self.assertEqual(status, "FAIL")
        self.assertIn("expression.md asks for 3x", message)


class WeightSpanTests(unittest.TestCase):
    def test_the_span_is_lightest_to_heaviest(self):
        self.assertEqual(
            expression_audit.weight_span(payload(weights={200: 1, 400: 4, 800: 2})),
            (200, 800))

    def test_no_weights_gives_nones(self):
        self.assertEqual(expression_audit.weight_span(payload(weights={})), (None, None))

    def test_both_ends_present_passes(self):
        status, _severity, _message = expression_audit.weight_verdict(300, 700)
        self.assertEqual(status, "pass")

    def test_only_the_middle_is_a_review(self):
        status, severity, message = expression_audit.weight_verdict(400, 600)
        self.assertEqual((status, severity), ("review", "review"))
        self.assertIn("200-300 against 700-800", message)

    def test_a_missing_light_end_is_a_review(self):
        _status, _severity, message = expression_audit.weight_verdict(500, 700)
        self.assertIn("no light end", message)

    def test_a_missing_heavy_end_is_a_review(self):
        _status, _severity, message = expression_audit.weight_verdict(200, 500)
        self.assertIn("no heavy end", message)


class SizeStepTests(unittest.TestCase):
    def test_steps_count_distinct_sizes(self):
        self.assertEqual(expression_audit.size_steps(payload(sizes={14: 1, 16: 4, 24: 1})), 3)

    def test_two_steps_is_too_few(self):
        _status, _severity, message = expression_audit.steps_verdict(2)
        self.assertIn("almost no room", message)

    def test_thirteen_steps_reads_as_drift(self):
        _status, _severity, message = expression_audit.steps_verdict(13)
        self.assertIn("reads as drift", message)

    def test_seven_steps_is_quiet(self):
        status, _severity, _message = expression_audit.steps_verdict(7)
        self.assertEqual(status, "pass")


class DisplayTests(unittest.TestCase):
    def test_only_display_sized_samples_are_read(self):
        mixed = [sample(size=88, letter_spacing_em=-0.02, line_height_ratio=1.0),
                 sample(size=16, letter_spacing_em=0.0, line_height_ratio=1.6)]
        readings = expression_audit.display_readings(payload(samples=mixed))
        self.assertEqual(readings["samples"], 1)
        self.assertAlmostEqual(readings["tracking_em"], -0.02)
        self.assertAlmostEqual(readings["line_height_ratio"], 1.0)

    def test_no_display_text_reports_zero_samples(self):
        readings = expression_audit.display_readings(payload(samples=[sample(size=16)]))
        self.assertEqual(readings["samples"], 0)
        self.assertIsNone(readings["tracking_em"])

    def test_tracking_at_the_boundary_is_inside(self):
        # REGRESSION: -0.03 measured as outside "-0.03 to -0.01" through float
        # error, so a page that had set exactly the file's value was flagged.
        readings = expression_audit.display_readings(
            payload(samples=[sample(size=64, letter_spacing_em=-0.03,
                                    line_height_ratio=1.0)]))
        self.assertTrue(readings["tracking_in_range"])

    def test_a_loose_display_reading_is_outside(self):
        readings = expression_audit.display_readings(
            payload(samples=[sample(size=64, letter_spacing_em=0.05,
                                    line_height_ratio=1.6)]))
        self.assertFalse(readings["tracking_in_range"])
        self.assertFalse(readings["line_height_in_range"])


class FamilyTests(unittest.TestCase):
    def test_declarations_are_counted_with_samples(self):
        families = expression_audit.families(payload(samples=[
            sample(family_declaration="Segoe UI, sans-serif"),
            sample(family_declaration="Segoe UI, sans-serif"),
            sample(family_declaration="Georgia, serif"),
        ]))
        self.assertEqual(families["Segoe UI, sans-serif"], 2)
        self.assertEqual(families["Georgia, serif"], 1)

    def test_weight_variants_of_one_family_count_as_one_declaration_each(self):
        # REGRESSION: the first-name count reported five "families" on a page
        # with three roles, because Segoe UI Light is a weight of Segoe UI.
        families = expression_audit.families(payload(samples=[
            sample(family_declaration="Segoe UI, sans-serif"),
            sample(family_declaration="Segoe UI Light, Segoe UI, sans-serif"),
        ]))
        self.assertEqual(len(families), 2, "two declarations, and the report says so")
        self.assertIn("Segoe UI Light, Segoe UI, sans-serif", families)

    def test_five_declarations_do_not_raise_a_finding(self):
        samples = [sample(family_declaration=decl) for decl in (
            "Segoe UI, sans-serif",
            "Segoe UI Light, Segoe UI, sans-serif",
            "Georgia, serif",
            "Cascadia Code, Consolas, monospace",
            "Noto Sans SC, sans-serif",
        )]
        _measures, reviews = expression_audit.classify(payload(samples=samples))
        self.assertNotIn("FAMILIES", [review["check"] for review in reviews])


class ClassifyTests(unittest.TestCase):
    def test_nothing_here_is_a_failure(self):
        # The whole point: taste never gates a build.
        flat = payload(sizes={16: 4, 20: 1}, weights={400: 5},
                       samples=[sample(size=16), sample(size=20)])
        measures, reviews = expression_audit.classify(flat)
        self.assertEqual(measures, [])
        self.assertTrue(reviews)

    def test_a_flat_page_produces_three_reviews(self):
        flat = payload(sizes={16: 4, 20: 1}, weights={400: 5},
                       samples=[sample(size=16), sample(size=20)])
        _measures, reviews = expression_audit.classify(flat)
        checks = [review["check"] for review in reviews]
        self.assertIn("TYPE-RATIO", checks)
        self.assertIn("WEIGHT-SPAN", checks)
        self.assertIn("SIZE-STEPS", checks)

    def test_every_review_names_the_expression_item(self):
        _measures, reviews = expression_audit.classify(payload())
        for review in reviews:
            self.assertIn("expression.md", review["clause"])


class ReportTests(unittest.TestCase):
    def test_has_measurable_fail_is_always_false(self):
        flat = payload(sizes={16: 4, 20: 1}, weights={400: 5},
                       samples=[sample(size=16)])
        report = expression_audit.build_report("http://x/", flat)
        self.assertFalse(expression_audit.has_measurable_fail(report))

    def test_the_manual_items_are_named(self):
        report = expression_audit.build_report("http://x/", payload())
        self.assertEqual(len(report["manual"]), 5)
        self.assertTrue(any("focal point" in item for item in report["manual"]))
        self.assertTrue(any("signature" in item for item in report["manual"]))

    def test_the_text_report_lists_the_manual_items(self):
        report = expression_audit.build_report("http://x/", payload())
        text = expression_audit.render_text(report)
        self.assertIn("Left to the polish pass", text)
        self.assertIn("no exit status", text)

    def test_json_output_is_parseable(self):
        with mock.patch.object(expression_audit, "audit_url", return_value=payload()):
            code, output = run(expression_audit.main, ["http://127.0.0.1:1/", "--json"])
        report = json.loads(output)
        self.assertTrue(report["verified"])
        self.assertIn("type_ratio", report["metrics"])

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


if __name__ == "__main__":
    unittest.main()
