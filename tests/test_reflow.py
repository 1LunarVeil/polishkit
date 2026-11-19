"""Browser-free tests for reflow.py.

The tool changes viewports, so what is pinned here is what it decides from the
measurements: which element is the criterion's failure, which is excepted, and
how findings collapse when one broken container produces a dozen descendants.

Three of these tests record defects that a real page caught first:

- the viewport was read from `documentElement.clientWidth`, which excludes the
  vertical scrollbar, so a 320px request measured as 305px and every element
  reaching past the scrollbar became a false WIDER (112 of them on one page);
- `classify` wrote the viewport into the element's `width` field and dropped
  `right`, so every finding read "320px wide" and the de-duplication had no
  geometry to group on;
- the Reflow exception was applied to ancestors but not to the element itself,
  so a wide `<table>` failed while its cells were listed as excepted.
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

import reflow  # noqa: E402


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


def payload(**overrides):
    """One viewport's collector payload: nothing overflows."""
    base = {
        "viewport_width": 320,
        "doc_scroll_width": 320,
        "doc_client_width": 320,
        "horizontal_overflow": False,
        "findings": [],
        "uncertain": [],
        "capped": False,
    }
    base.update(overrides)
    return base


def wider(tag="div.panel", width=400, right=500, viewport=320):
    return {"check": "WIDER", "tag": tag, "width": width, "right": right,
            "viewport_width": viewport, "element_width_css": f"{width}px",
            "position": "static", "snippet": ""}


def fixed(tag="section.plate", css="900px", viewport=320):
    return {"check": "FIXED-W", "tag": tag, "width": 900, "right": 900,
            "viewport_width": viewport, "element_width_css": css,
            "position": "static", "snippet": ""}


class OverflowTests(unittest.TestCase):
    def test_a_document_that_fits_is_not_a_failure(self):
        measures, uncertain = reflow.classify(payload(), 320)
        self.assertEqual(measures, [])
        self.assertEqual(uncertain, [])

    def test_horizontal_overflow_is_the_criterion_failure(self):
        measures, _ = reflow.classify(
            payload(doc_scroll_width=441, doc_client_width=320), 320)
        self.assertEqual([m["check"] for m in measures], ["OVERFLOW"])
        self.assertEqual(measures[0]["clause"], "WCAG 1.4.10")
        self.assertIn("121px", measures[0]["message"])

    def test_a_one_pixel_rounding_difference_is_not_overflow(self):
        measures, _ = reflow.classify(
            payload(doc_scroll_width=321, doc_client_width=320), 320)
        self.assertEqual(measures, [])

    def test_overflow_px_reports_the_gap(self):
        self.assertEqual(reflow.overflow_px({"doc_scroll_width": 441,
                                             "doc_client_width": 320}), 121)
        self.assertEqual(reflow.overflow_px({}), 0)


class ElementGeometryTests(unittest.TestCase):
    def test_element_width_and_right_survive_classification(self):
        # REGRESSION: classify wrote the viewport into `width` and dropped
        # `right`, so every finding read "320px wide" and grouping had nothing
        # to work with.
        measures, _ = reflow.classify(payload(findings=[wider()]), 320)
        self.assertEqual(len(measures), 1)
        entry = measures[0]
        self.assertEqual(entry["width"], 400, "element width, not the viewport")
        self.assertEqual(entry["right"], 500)
        self.assertEqual(entry["viewport"], 320)

    def test_a_fixed_width_panel_is_its_own_check(self):
        measures, _ = reflow.classify(payload(findings=[fixed()]), 320)
        self.assertEqual([m["check"] for m in measures], ["FIXED-W"])
        self.assertIn("900px", measures[0]["message"])

    def test_exceptions_are_reported_as_uncertain_not_failed(self):
        measures, uncertain = reflow.classify(payload(uncertain=[
            {"method": "uncertain:2d-exception", "tag": "table.wide",
             "ancestor": "table.wide", "width": 700}]), 320)
        self.assertEqual(measures, [])
        self.assertEqual(len(uncertain), 1)
        self.assertEqual(uncertain[0]["status"], "uncertain")
        self.assertEqual(uncertain[0]["viewport"], 320)

    def test_uncertain_keeps_the_element_width_apart_from_the_viewport(self):
        # REGRESSION: the viewport number overwrote the element width, and the
        # report said "td at 114px" as though 114 were the viewport.
        _, uncertain = reflow.classify(payload(uncertain=[
            {"method": "uncertain:2d-exception", "tag": "td", "ancestor": "table",
             "width": 114}]), 320)
        self.assertEqual(uncertain[0]["width"], 114)
        self.assertEqual(uncertain[0]["viewport"], 320)


class GroupingTests(unittest.TestCase):
    def test_siblings_at_one_edge_collapse_to_a_single_finding(self):
        # Ten descendants of one unresponsive grid all ended at x=386.
        findings = [wider(tag=f"div.child{i}", width=166, right=386)
                    for i in range(10)]
        measures, _ = reflow.classify(payload(findings=findings), 320)
        grouped = reflow.group_by_origin(measures)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["siblings"], 10)
        self.assertIn("9 more element", grouped[0]["message"])

    def test_the_widest_member_represents_the_group(self):
        findings = [wider(tag="div.small", width=100, right=386),
                    wider(tag="div.wide", width=166, right=386)]
        measures, _ = reflow.classify(payload(findings=findings), 320)
        grouped = reflow.group_by_origin(measures)
        self.assertEqual(grouped[0]["tag"], "div.wide")

    def test_different_edges_stay_separate(self):
        findings = [wider(tag="div.a", right=386), wider(tag="div.b", right=500)]
        measures, _ = reflow.classify(payload(findings=findings), 320)
        self.assertEqual(len(reflow.group_by_origin(measures)), 2)

    def test_the_same_edge_at_two_viewports_stays_separate(self):
        at_320, _ = reflow.classify(payload(findings=[wider(right=386)]), 320)
        at_400, _ = reflow.classify(payload(findings=[wider(right=386)]), 400)
        grouped = reflow.group_by_origin(at_320 + at_400)
        self.assertEqual(len(grouped), 2, "one finding per viewport")

    def test_overflow_findings_are_never_grouped(self):
        payload_data = payload(doc_scroll_width=441, doc_client_width=320,
                               findings=[wider()])
        measures, _ = reflow.classify(payload_data, 320)
        grouped = reflow.group_by_origin(measures)
        self.assertEqual([item["check"] for item in grouped], ["OVERFLOW", "WIDER"])


class ReportTests(unittest.TestCase):
    def test_a_clean_page_yields_no_failure(self):
        report = reflow.build_report("http://x/", [(320, payload())])
        self.assertFalse(reflow.has_measurable_fail(report))
        self.assertEqual(report["summary"]["overflow"], 0)

    def test_per_width_geometry_is_recorded(self):
        report = reflow.build_report("http://x/", [
            (320, payload(doc_scroll_width=441, doc_client_width=320)),
            (768, payload(doc_scroll_width=768, doc_client_width=768,
                          viewport_width=768)),
        ])
        self.assertEqual(report["summary"]["per_width"]["320"]["overflow_px"], 121)
        self.assertEqual(report["summary"]["per_width"]["768"]["overflow_px"], 0)

    def test_reaching_320_is_stated(self):
        report = reflow.build_report("http://x/", [
            (320, payload(viewport_width=320)), (768, payload(viewport_width=768))])
        self.assertTrue(report["summary"]["reached_320"])

    def test_text_report_names_the_viewports(self):
        report = reflow.build_report("http://x/", [(320, payload())])
        text = reflow.render_text(report)
        self.assertIn("320px", text)
        self.assertIn("0 FAIL", text)

    def test_json_output_is_parseable(self):
        with mock.patch.object(reflow, "audit_url",
                               return_value=([(320, payload())], None)):
            code, output = run(reflow.main, ["http://127.0.0.1:1/", "--json"])
        report = json.loads(output)
        self.assertTrue(report["verified"])
        self.assertEqual(report["summary"]["fail"], 0)

    def test_a_failed_audit_claims_nothing(self):
        def boom(url, **kwargs):
            raise RuntimeError("no browser")

        with mock.patch.object(reflow, "audit_url", side_effect=boom):
            code, output = run(reflow.main, ["http://127.0.0.1:1/"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output)["verified"])

    def test_url_rejection_exits_three(self):
        code, output = run(reflow.main, ["file:///etc/passwd"])
        self.assertEqual(code, 3)


class ExceptionSelectorTests(unittest.TestCase):
    def test_tables_and_media_are_excepted(self):
        for selector in ("table", "svg", "video", "canvas", "pre", "[role=img]"):
            self.assertIn(selector, reflow.EXCEPTION_SELECTOR)

    def test_inline_code_is_not_excepted(self):
        # A <code> with white-space:nowrap was the only real overflow on the
        # probe page, and treating every <code> as a two-dimensional surface
        # hid it.
        selectors = [part.strip() for part in reflow.EXCEPTION_SELECTOR.split(",")]
        self.assertNotIn("code", selectors)


if __name__ == "__main__":
    unittest.main()
