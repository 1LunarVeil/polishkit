"""Browser-free tests for text_spacing.py.

The two collector runs need a browser, so what is pinned here is the deciding
logic between them: which change counts as lost content, which is a
pre-existing defect under a different clause, and which is noise from nested
elements sharing pixels.

Two of these tests exist because a real page caught the bug first:

- the pairing key was a document coordinate, so the override moved everything
  and nothing matched — the audit reported every page clean;
- the clipping box is usually an ancestor, not the element holding the text, so
  the first version missed every truncated card.
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

import text_spacing  # noqa: E402


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


def row(**overrides):
    """A paragraph in a normal box: nothing clipped, nothing fixed."""
    base = {
        "key": "1.0",
        "tag": "p",
        "text": "sample text",
        "font_size": 16,
        "line_height": 24,
        "letter_spacing": 0,
        "word_spacing": 0,
        "scroll_width": 700,
        "scroll_height": 48,
        "client_width": 700,
        "client_height": 48,
        "rect": {"x": 24, "y": 100, "width": 700, "height": 48,
                 "top": 100, "left": 24},
        "clips": False,
        "overflow_x": "visible",
        "overflow_y": "visible",
        "text_overflow": "clip",
        "white_space": "normal",
        "fixed_height": False,
        "max_height": "none",
        "clipping_ancestor": None,
        "ancestors": ["1"],
        "nested_depth": 2,
    }
    base.update(overrides)
    return base


def payload(rows, **overrides):
    base = {"rows": rows, "capped": False, "uncertain": [],
            "viewport": {"width": 1280, "height": 800},
            "doc": {"scroll_width": 1280, "scroll_height": 800}}
    base.update(overrides)
    return base


def clipping_ancestor(**overrides):
    base = {"tag": "div.card", "scroll_width": 718, "scroll_height": 96,
            "client_width": 718, "client_height": 64}
    base.update(overrides)
    return base


class OverrideCssTests(unittest.TestCase):
    def test_the_four_multipliers_follow_the_criterion(self):
        css = text_spacing.override_css()
        self.assertIn("line-height:1.5 !important", css)
        self.assertIn("letter-spacing:0.12em !important", css)
        self.assertIn("word-spacing:0.16em !important", css)
        self.assertIn("margin-bottom:2em !important", css)

    def test_nothing_but_spacing_is_overridden(self):
        # 1.4.12 says "changing no other style property"; a stray width or
        # display in this stylesheet would invalidate the whole test.
        css = text_spacing.override_css()
        properties = set()
        for block in css.split("}"):
            if "{" not in block:
                continue
            for declaration in block.split("{")[-1].split(";"):
                if ":" in declaration:
                    properties.add(declaration.split(":")[0].strip().lower())
        self.assertEqual(
            properties,
            {"line-height", "letter-spacing", "word-spacing", "margin-bottom"},
            f"unexpected properties in the override: {sorted(properties)}")

    def test_every_declaration_uses_important(self):
        css = text_spacing.override_css()
        declarations = [part for block in css.split("}") for part in block.split("{")[-1].split(";")]
        declared = [decl for decl in declarations if ":" in decl]
        self.assertTrue(declared)
        self.assertTrue(all("!important" in decl for decl in declared), declarations)

    def test_paragraph_selector_covers_the_semantic_blocks(self):
        css = text_spacing.override_css()
        # The second rule is the paragraph-gap one; take its selector list.
        paragraph_rule = css.split("}")[1]
        selector = paragraph_rule.split("{")[0]
        for name in ("p", "li", "dd", "blockquote", "figcaption"):
            self.assertIn(name, selector)

    def test_multipliers_scale_with_the_element_font(self):
        # em-relative values are the whole point: a 32px heading must get a
        # 48px line box, not a page-wide constant.
        css = text_spacing.override_css(line=1.5)
        self.assertIn("line-height:1.5 !important", css)
        self.assertNotIn("px", css)


class ClippingTests(unittest.TestCase):
    def test_clean_element_is_not_clipped(self):
        self.assertFalse(text_spacing.clipped(row()))

    def test_element_that_clips_itself_is_caught(self):
        entry = row(clips=True, overflow_y="hidden",
                    scroll_height=96, client_height=64)
        self.assertTrue(text_spacing.clipped(entry))

    def test_ancestor_clipping_is_caught(self):
        # REGRESSION: a paragraph inside a 48px overflow:hidden card reports a
        # comfortable client box of its own. Only the card knows it is clipping.
        entry = row(clipping_ancestor=clipping_ancestor())
        self.assertTrue(text_spacing.clipped(entry))

    def test_ancestor_with_room_to_spare_is_not_clipping(self):
        entry = row(clipping_ancestor=clipping_ancestor(
            scroll_height=48, client_height=64))
        self.assertFalse(text_spacing.clipped(entry))

    def test_a_two_pixel_brush_is_not_clipping(self):
        entry = row(clips=True, overflow_y="hidden",
                    scroll_height=49, client_height=48)
        self.assertFalse(text_spacing.clipped(entry))

    def test_evidence_names_the_ancestor_that_clips(self):
        entry = row(clipping_ancestor=clipping_ancestor(tag="div.card"))
        evidence = text_spacing.clip_evidence(entry)
        self.assertEqual(evidence["box"], "div.card")
        self.assertEqual(evidence["scroll"], (718, 96))
        self.assertEqual(evidence["client"], (718, 64))

    def test_evidence_names_the_element_when_it_clips_itself(self):
        entry = row(tag="div.scroller", clips=True, overflow_y="hidden",
                    scroll_height=96, client_height=64,
                    scroll_width=200, client_width=200)
        self.assertEqual(text_spacing.clip_evidence(entry)["box"], "div.scroller")


class OverlapTests(unittest.TestCase):
    def test_same_rect_overlaps(self):
        first = row(key="1.0", rect={"left": 0, "top": 0, "width": 100, "height": 20})
        second = row(key="1.1", rect={"left": 0, "top": 0, "width": 100, "height": 20})
        self.assertGreater(text_spacing.overlap_area(first, second), 0)
        self.assertTrue(text_spacing.overlaps(first, second))

    def test_disjoint_rects_do_not_overlap(self):
        first = row(key="1.0", rect={"left": 0, "top": 0, "width": 100, "height": 20})
        second = row(key="1.1", rect={"left": 0, "top": 40, "width": 100, "height": 20})
        self.assertEqual(text_spacing.overlap_area(first, second), 0)
        self.assertFalse(text_spacing.overlaps(first, second))

    def test_a_parent_never_overlaps_its_child(self):
        # A <b> inside a <span> shares pixels by construction.
        parent = row(key="1.0", rect={"left": 0, "top": 0, "width": 200, "height": 40},
                     ancestors=["1"])
        child = row(key="1.0.0", tag="b",
                    rect={"left": 5, "top": 5, "width": 40, "height": 20},
                    ancestors=["1.0", "1"])
        self.assertFalse(text_spacing.overlaps(parent, child))

    def test_a_thin_brush_is_not_an_overlap(self):
        # 100px wide, 1px of vertical contact = 100 px². Under the 24 px² floor
        # only when the boxes are narrow; the floor is about area, so a wide
        # 1px brush is still an overlap. This pins the area semantics.
        first = row(key="1.0", rect={"left": 0, "top": 0, "width": 20, "height": 20})
        second = row(key="1.1", rect={"left": 0, "top": 19, "width": 20, "height": 20})
        self.assertLess(text_spacing.overlap_area(first, second), 24)
        self.assertFalse(text_spacing.overlaps(first, second))

    def test_a_wide_one_pixel_brush_still_counts(self):
        first = row(key="1.0", rect={"left": 0, "top": 0, "width": 100, "height": 20})
        second = row(key="1.1", rect={"left": 0, "top": 19, "width": 100, "height": 20})
        self.assertGreaterEqual(text_spacing.overlap_area(first, second), 24)
        self.assertTrue(text_spacing.overlaps(first, second))

    def test_siblings_that_collide_do_overlap(self):
        first = row(key="1.0", rect={"left": 0, "top": 0, "width": 100, "height": 40})
        second = row(key="1.1", rect={"left": 10, "top": 10, "width": 100, "height": 40})
        self.assertTrue(text_spacing.overlaps(first, second))


class GrowthTests(unittest.TestCase):
    def test_height_growth_is_reported_in_lines(self):
        before = row(rect={"left": 0, "top": 0, "width": 100, "height": 48})
        after = row(rect={"left": 0, "top": 0, "width": 100, "height": 96})
        self.assertAlmostEqual(text_spacing.grew(after, before), 3.0)

    def test_fixed_height_box_that_now_needs_more_room(self):
        entry = row(max_height="52px", scroll_height=92, font_size=16)
        self.assertTrue(text_spacing.fixed_height_overflow(entry, row()))

    def test_fixed_height_box_with_room_is_fine(self):
        entry = row(max_height="200px", scroll_height=92, font_size=16)
        self.assertFalse(text_spacing.fixed_height_overflow(entry, row()))

    def test_no_max_height_is_never_a_fixed_height_failure(self):
        entry = row(max_height="none", scroll_height=999)
        self.assertFalse(text_spacing.fixed_height_overflow(entry, row()))


class ClassifyTests(unittest.TestCase):
    def test_a_clean_page_yields_nothing(self):
        authored = payload([row()])
        overridden = payload([row(scroll_height=72, client_height=72,
                                  rect={"left": 24, "top": 100, "width": 700,
                                        "height": 72})])
        measures, uncertain, reviews = text_spacing.classify(authored, overridden)
        self.assertEqual(measures, [])
        self.assertEqual(uncertain, [])
        self.assertEqual(reviews, [])

    def test_new_clipping_is_a_failure(self):
        authored = payload([row()])
        overridden = payload([row(clipping_ancestor=clipping_ancestor())])
        measures, _, _ = text_spacing.classify(authored, overridden)
        self.assertEqual(len(measures), 1)
        self.assertEqual(measures[0]["check"], "CLIP")
        self.assertEqual(measures[0]["status"], "FAIL")
        self.assertIn("div.card", measures[0]["message"])

    def test_pre_existing_clipping_is_not_this_clause(self):
        authored = payload([row(clipping_ancestor=clipping_ancestor())])
        overridden = payload([row(clipping_ancestor=clipping_ancestor())])
        measures, _, _ = text_spacing.classify(authored, overridden)
        self.assertEqual(measures, [])

    def test_truncation_needs_a_whole_em_of_extra_width(self):
        # REGRESSION: a 4px threshold counted cells that already squeezed their
        # text before the override (192px box, 195px content), which is a
        # pre-existing defect and buried the cells this clause is about.
        authored = payload([row(tag="td.items", white_space="nowrap",
                                text_overflow="ellipsis", client_width=230,
                                scroll_width=243)])
        overridden = payload([row(tag="td.items", white_space="nowrap",
                                  text_overflow="ellipsis", client_width=230,
                                  scroll_width=252)])
        measures, _, _ = text_spacing.classify(authored, overridden)
        self.assertEqual(measures, [])

    def test_truncation_with_meaningful_growth_is_a_failure(self):
        authored = payload([row(tag="div.nowrap", white_space="nowrap",
                                text_overflow="ellipsis", client_width=192,
                                scroll_width=423, font_size=16)])
        overridden = payload([row(tag="div.nowrap", white_space="nowrap",
                                  text_overflow="ellipsis", client_width=192,
                                  scroll_width=556, font_size=16)])
        measures, _, _ = text_spacing.classify(authored, overridden)
        self.assertEqual(len(measures), 1)
        self.assertEqual(measures[0]["check"], "TRUNCATION")
        self.assertIn("+133px", measures[0]["message"])

    def test_truncation_is_not_swallowed_by_the_already_clipped_guard(self):
        # REGRESSION: the CLIP branch ran first and skipped every nowrap box as
        # "already clipped", so a single-line label could never be reported.
        authored = payload([row(tag="div.nowrap", white_space="nowrap",
                                text_overflow="ellipsis", clips=True,
                                client_width=192, scroll_width=400,
                                font_size=14)])
        overridden = payload([row(tag="div.nowrap", white_space="nowrap",
                                  text_overflow="ellipsis", clips=True,
                                  client_width=192, scroll_width=500,
                                  font_size=14)])
        measures, _, _ = text_spacing.classify(authored, overridden)
        self.assertEqual([item["check"] for item in measures], ["TRUNCATION"])

    def test_overlap_only_after_the_override_is_reported(self):
        before_a = row(key="1.0", rect={"left": 0, "top": 0, "width": 100, "height": 20},
                       ancestors=["1"])
        before_b = row(key="1.1", rect={"left": 0, "top": 40, "width": 100, "height": 20},
                       ancestors=["1"])
        after_a = row(key="1.0", rect={"left": 0, "top": 0, "width": 100, "height": 70},
                      ancestors=["1"])
        after_b = row(key="1.1", rect={"left": 0, "top": 40, "width": 100, "height": 70},
                      ancestors=["1"])
        measures, _, _ = text_spacing.classify(payload([before_a, before_b]),
                                               payload([after_a, after_b]))
        self.assertEqual([item["check"] for item in measures], ["OVERLAP"])

    def test_unchanged_overlap_is_not_reported(self):
        a = row(key="1.0", rect={"left": 0, "top": 0, "width": 100, "height": 40},
                ancestors=["1"])
        b = row(key="1.1", rect={"left": 10, "top": 10, "width": 100, "height": 40},
                ancestors=["1"])
        measures, _, _ = text_spacing.classify(payload([a, b]), payload([a, b]))
        self.assertEqual(measures, [])

    def test_elements_absent_before_the_override_are_skipped(self):
        # A page that appends content in response to the override must not be
        # compared against a row that never existed.
        measures, _, _ = text_spacing.classify(payload([]), payload([row(key="9.9")]))
        self.assertEqual(measures, [])

    def test_masked_content_is_listed_as_uncertain_not_passed(self):
        authored = payload([row()])
        overridden = payload([row()], uncertain=[
            {"tag": "div.hero", "evidence": "clip-path on the element"}])
        _, uncertain, _ = text_spacing.classify(authored, overridden)
        self.assertEqual(len(uncertain), 1)
        self.assertEqual(uncertain[0]["status"], "uncertain:not-measured")

    def test_a_capped_collection_is_stated(self):
        authored = payload([row()])
        overridden = payload([row()], capped=True)
        _, _, reviews = text_spacing.classify(authored, overridden)
        self.assertEqual([item["check"] for item in reviews], ["CAPPED"])


class SpacingReportTests(unittest.TestCase):
    def test_authored_values_are_reported_not_gated(self):
        # 1.4.12 does not require the page to ship these values; the counts are
        # informative, so a page using tighter spacing still passes.
        report = text_spacing.spacing_report(
            payload([row(line_height=24, font_size=16),
                     row(key="1.1", line_height=16, font_size=16)]), None)
        self.assertEqual(report["rows"], 2)
        self.assertEqual(report["line_height"], 1)
        self.assertAlmostEqual(report["already_meets_line"], 0.5)

    def test_empty_page_reports_zero_rows(self):
        self.assertEqual(text_spacing.spacing_report(payload([]), None)["rows"], 0)


class ReportTests(unittest.TestCase):
    def test_failure_drives_the_exit_rule(self):
        authored = payload([row()])
        overridden = payload([row(clipping_ancestor=clipping_ancestor())])
        report = text_spacing.build_report("http://x/", authored, overridden)
        self.assertTrue(text_spacing.has_measurable_fail(report))
        self.assertEqual(report["summary"]["clip"], 1)

    def test_text_report_names_the_override_values(self):
        authored = payload([row()])
        overridden = payload([row()])
        report = text_spacing.build_report("http://x/", authored, overridden)
        text = text_spacing.render_text(report)
        self.assertIn("line-height 1.5x", text)
        self.assertIn("letter-spacing 0.12x", text)
        self.assertIn("0 FAIL", text)

    def test_json_output_is_parseable(self):
        authored = payload([row()])
        overridden = payload([row()])
        with mock.patch.object(text_spacing, "audit_url",
                               return_value=(authored, overridden)):
            code, output = run(text_spacing.main, ["http://127.0.0.1:1/", "--json"])
        report = json.loads(output)
        self.assertTrue(report["verified"])
        self.assertEqual(report["override"]["line_height"], 1.5)

    def test_a_failed_audit_claims_nothing(self):
        def boom(url, **kwargs):
            raise RuntimeError("no browser")

        with mock.patch.object(text_spacing, "audit_url", side_effect=boom):
            code, output = run(text_spacing.main, ["http://127.0.0.1:1/"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output)["verified"])

    def test_url_rejection_exits_three(self):
        code, output = run(text_spacing.main, ["file:///etc/passwd"])
        self.assertEqual(code, 3)
        self.assertIn("URL rejected", json.loads(output)["reason"])


if __name__ == "__main__":
    unittest.main()
