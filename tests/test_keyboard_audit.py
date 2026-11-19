"""Browser-free tests for keyboard_audit.py.

The walk and the screenshots need a browser, so what is pinned here is the
deciding logic: which bucket a finding lands in, what verdict a measurement
becomes, and the geometry the pixel comparison depends on. Shaped exactly like
the payload audit_url emits.

Several tests exist because a real smoke page caught the defect first — the
trap cascade, the hover read-timing bug, the tabindex="-1" blind spot. Those
are labelled REGRESSION so the reason survives the person who fixed them.
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

import image_diff  # noqa: E402
import keyboard_audit  # noqa: E402

WIDTH, HEIGHT = 40, 30


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


def stop(**overrides):
    """One walk stop: a neutral button near the top-left, nothing suspicious."""
    base = {
        "id": 1,
        "tag": "button#ok",
        "role": "",
        "text": "ok",
        "tabindex": None,
        "disabled": False,
        "in_dialog": False,
        "rect": {"x": 20, "y": 20, "left": 20, "top": 20,
                 "width": 120, "height": 40, "right": 140, "bottom": 60},
        "page_rect": {"x": 20, "y": 20, "width": 120, "height": 40},
        "focus_visible": True,
    }
    base.update(overrides)
    return base


def walk(stops, **overrides):
    base = {"tabbable_count": len(stops), "stop_reason": "end",
            "stops": stops, "order": {"jumps": [], "backwards": 0}}
    base.update(overrides)
    return base


def payload(stops=None, **overrides):
    stops = stops if stops is not None else []
    base = {"walk": walk(stops), "unreachable": [], "removed_from_order": [],
            "stops": stops, "activation": []}
    base.update(overrides)
    return base


def png(rows):
    """Encode RGB rows into a PNG in memory (same layout as make_fixtures)."""
    import struct
    import zlib

    height = len(rows)
    width = len(rows[0]) // 3

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    raw = bytearray()
    for row in rows:
        raw += b"\x00" + row
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def canvas(pixel, width=WIDTH, height=HEIGHT):
    """A mutable RGB canvas: list of bytearrays, one per row."""
    return [bytearray(bytes(pixel) * width) for _ in range(height)]


def paint(rows, box, pixel):
    """Fill a rectangle (x, y, w, h) in place."""
    x, y, w, h = box
    for row_index in range(max(0, y), min(len(rows), y + h)):
        for column in range(max(0, x), min(len(rows[row_index]) // 3, x + w)):
            offset = column * 3
            rows[row_index][offset:offset + 3] = bytes(pixel)
    return rows


def encode(rows):
    return png(rows)


def flat(pixel, width=WIDTH, height=HEIGHT):
    return encode(canvas(pixel, width, height))


def ringed(background, ring, box, thickness=3):
    """A crop with a rectangular ring around `box` = (x, y, w, h)."""
    x, y, w, h = box
    rows = canvas(background)
    paint(rows, (x - thickness, y - thickness, w + 2 * thickness, thickness), ring)
    paint(rows, (x - thickness, y + h, w + 2 * thickness, thickness), ring)
    paint(rows, (x - thickness, y, thickness, h), ring)
    paint(rows, (x + w, y, thickness, h), ring)
    return encode(rows)


BOX = {"x": 8, "y": 6, "width": 20, "height": 14}


class WalkEndingTests(unittest.TestCase):
    def test_a_root_stop_ends_the_walk_instead_of_cycling(self):
        # REGRESSION: Chrome parks focus on <body> after the last control. The
        # label builder gave body a text label, so a `tag == "body"` test never
        # matched, the walk kept going into browser chrome, and a clean page
        # came back with a false trap FAIL and a body "no indicator" FAIL.
        # `is_root` is set in the browser and is what the walk must trust.
        self.assertTrue(keyboard_audit._is_walk_end({"is_root": True}))
        self.assertFalse(keyboard_audit._is_walk_end({"id": 7, "tag": "button#ok"}))
        self.assertTrue(keyboard_audit._is_walk_end({}))

    def test_a_walk_ending_at_root_is_reported_as_end(self):
        data = payload([stop()])
        data["walk"]["stop_reason"] = "end"
        self.assertIsNone(keyboard_audit.trap_verdict(data["walk"]))


class PositiveTabindexTests(unittest.TestCase):
    def test_positive_value_is_flagged(self):
        self.assertTrue(keyboard_audit.positive_tabindex("1"))
        self.assertTrue(keyboard_audit.positive_tabindex(" 3 "))
        self.assertTrue(keyboard_audit.positive_tabindex(2))

    def test_zero_negative_and_absent_are_not_flagged(self):
        for value in ("0", "-1", None, "", "abc"):
            self.assertFalse(keyboard_audit.positive_tabindex(value), value)

    def test_review_names_the_value(self):
        found = keyboard_audit.tabindex_reviews(
            [stop(tabindex="2"), stop(tag="button#b", tabindex=None)])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["check"], "TABINDEX")
        self.assertEqual(found[0]["status"], "review")
        self.assertIn("2", found[0]["message"])


class PerimeterTests(unittest.TestCase):
    def test_two_pixel_perimeter_is_four_h_plus_four_w(self):
        # 100x40: 4*40 + 4*100 = 560 — the value WCAG 2.4.13's understanding
        # spells out for a solid 2px outline.
        self.assertEqual(keyboard_audit.perimeter_area(100, 40), 560)

    def test_square_scales_with_size(self):
        self.assertEqual(keyboard_audit.perimeter_area(50, 50), 400)

    def test_zero_size_box_needs_no_area(self):
        self.assertEqual(keyboard_audit.perimeter_area(0, 0), 0)


class MedianTests(unittest.TestCase):
    def test_odd_count_is_the_middle_value(self):
        self.assertEqual(keyboard_audit.median([3, 1, 2]), 2)

    def test_even_count_averages_the_middle_pair(self):
        self.assertEqual(keyboard_audit.median([1, 2, 3, 4]), 2.5)

    def test_empty_is_none(self):
        self.assertIsNone(keyboard_audit.median([]))


class OrderTests(unittest.TestCase):
    def test_top_to_bottom_is_clean(self):
        stops = [stop(tag=f"button#b{i}", rect={"top": 40 * i, "left": 0})
                 for i in range(4)]
        deviation = keyboard_audit.order_deviation(stops)
        self.assertEqual(deviation["backwards"], 0)
        self.assertEqual(keyboard_audit.order_reviews({"order": deviation}), [])

    def test_small_offset_inside_one_row_is_not_backwards(self):
        stops = [stop(rect={"top": 100, "left": 200}), stop(rect={"top": 108, "left": 0})]
        self.assertEqual(keyboard_audit.order_deviation(stops)["backwards"], 0)

    def test_two_climbs_raise_a_review(self):
        stops = [stop(tag="button#a", rect={"top": 0, "left": 0}),
                 stop(tag="button#b", rect={"top": 400, "left": 0}),
                 stop(tag="button#c", rect={"top": 0, "left": 0}),
                 stop(tag="button#d", rect={"top": 500, "left": 0}),
                 stop(tag="button#e", rect={"top": 0, "left": 0})]
        walk_data = {"order": keyboard_audit.order_deviation(stops)}
        reviews = keyboard_audit.order_reviews(walk_data)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["check"], "ORDER")
        self.assertEqual(reviews[0]["status"], "review")

    def test_one_climb_is_tolerated(self):
        stops = [stop(rect={"top": 0, "left": 0}), stop(rect={"top": 400, "left": 0}),
                 stop(rect={"top": 0, "left": 0})]
        walk_data = {"order": keyboard_audit.order_deviation(stops)}
        self.assertEqual(keyboard_audit.order_reviews(walk_data), [])


class TrapTests(unittest.TestCase):
    def test_a_walk_that_reaches_the_end_is_not_a_trap(self):
        self.assertIsNone(keyboard_audit.trap_verdict(walk([stop()], stop_reason="end")))

    def test_cycle_outside_a_dialog_fails(self):
        stops = [stop(tag="button#a"), stop(tag="button#b")]
        finding = keyboard_audit.trap_verdict(
            walk(stops, stop_reason="cycle", tabbable_count=10))
        self.assertEqual(finding["status"], "FAIL")
        self.assertIn("cannot be reached", finding["message"])

    def test_cycle_inside_a_dialog_is_a_review(self):
        stops = [stop(tag="button#a", in_dialog=True), stop(tag="button#b", in_dialog=True)]
        finding = keyboard_audit.trap_verdict(
            walk(stops, stop_reason="cycle", tabbable_count=10))
        self.assertEqual(finding["status"], "review")
        self.assertIn("dialog", finding["message"])

    def test_reaching_every_element_but_never_leaving_still_fails(self):
        # REGRESSION: a page can cover all of its own tabbables and still pin
        # Tab forever. Coverage is not the test — leaving the document is.
        stops = [stop(tag="button#a"), stop(tag="button#b")]
        finding = keyboard_audit.trap_verdict(
            walk(stops, stop_reason="cycle", tabbable_count=2))
        self.assertEqual(finding["status"], "FAIL")
        self.assertIn("never leave the document", finding["message"])

    def test_truncated_walk_is_uncertain_not_a_failure(self):
        finding = keyboard_audit.trap_verdict(
            walk([stop()], stop_reason="budget", tabbable_count=99))
        self.assertTrue(finding["status"].startswith("uncertain"))
        self.assertIn("--max-steps", finding["message"])


class UnreachableTests(unittest.TestCase):
    def test_removed_from_order_always_fails(self):
        # REGRESSION: the smoke page's tabindex="-1" button never entered the
        # walk, so walking-only logic missed the classic 2.1.1 violation.
        found = keyboard_audit.unreachable_finding(payload(
            removed_from_order=[{"tag": "button#skip", "role": ""}]))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["status"], "FAIL")
        self.assertIn("tabindex", found[0]["message"])

    def test_stranded_elements_count_when_the_walk_ended(self):
        found = keyboard_audit.unreachable_finding(payload(
            unreachable=[{"tag": "button#x", "reason": "interactive but not reachable by Tab"}]))
        self.assertEqual(found[0]["status"], "FAIL")

    def test_stranded_elements_are_silent_after_a_trap(self):
        # REGRESSION: a trap blocked the walk, and every later control was then
        # reported unreachable — one root cause counted nine times.
        data = payload(unreachable=[{"tag": "button#x", "reason": "why"}])
        data["walk"]["stop_reason"] = "cycle"
        self.assertEqual(keyboard_audit.unreachable_finding(data), [])

    def test_stranded_elements_are_silent_after_a_truncated_walk(self):
        data = payload(unreachable=[{"tag": "button#x", "reason": "why"}])
        data["walk"]["stop_reason"] = "budget"
        self.assertEqual(keyboard_audit.unreachable_finding(data), [])


class ObscuredTests(unittest.TestCase):
    def test_every_sample_foreign_is_a_failure(self):
        obscured = {"visible_in_viewport": True,
                    "samples": [{"related": False, "hit": "div.veil"}] * 5}
        result = keyboard_audit.obscured_verdict(obscured)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("div.veil", result["message"])

    def test_one_related_sample_passes(self):
        # 2.4.11 says "entirely hidden"; a partly visible control is not a fail.
        obscured = {"visible_in_viewport": True,
                    "samples": [{"related": False, "hit": "div.veil"},
                                {"related": True, "hit": "button"}]}
        self.assertEqual(keyboard_audit.obscured_verdict(obscured)["status"], "pass")

    def test_off_screen_is_uncertain(self):
        result = keyboard_audit.obscured_verdict(
            {"visible_in_viewport": False, "samples": [{"related": False}] * 5})
        self.assertTrue(result["status"].startswith("uncertain"))


class IndicatorVerdictTests(unittest.TestCase):
    def test_zero_change_means_no_indicator(self):
        result = keyboard_audit.indicator_verdict(
            {"changed_pixels": 0, "qualifying_pixels": 0, "area_minimum": 560,
             "same_pixel_median": 0.0})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["clause"], "WCAG 2.4.7")

    def test_change_below_the_floor_is_not_perceivable(self):
        result = keyboard_audit.indicator_verdict(
            {"changed_pixels": 846, "qualifying_pixels": 0, "area_minimum": 560,
             "same_pixel_median": 1.11, "same_pixel_min": 1.02})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["clause"], "WCAG 1.4.11")
        self.assertIn("1.11", result["message"])

    def test_ring_unreadable_on_most_sides_fails(self):
        # REGRESSION (B3): the chart's ring was the same colour as the bar it
        # marked. Three of four sides sat at ~1.0:1 — the ring was invisible.
        result = keyboard_audit.indicator_verdict(
            {"changed_pixels": 900, "qualifying_pixels": 900, "area_minimum": 560,
             "same_pixel_median": 6.0, "adjacent_worst": 1.01,
             "adjacent_sides": 4, "adjacent_readable": 1})
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("1.01", result["message"])
        self.assertIn("3 of 4 sides", result["message"])

    def test_one_blind_edge_still_passes_with_a_caveat(self):
        # REGRESSION (B5): a 3px black ring on a button with a black hard
        # shadow. The right edge merged into the shadow at 1.02:1, the other
        # three sat at ~17.7:1. The state was plainly visible; failing it
        # would have reported a well-built control as broken.
        result = keyboard_audit.indicator_verdict(
            {"changed_pixels": 688, "qualifying_pixels": 688, "area_minimum": 613,
             "same_pixel_median": 17.97, "adjacent_worst": 1.02,
             "adjacent_sides": 4, "adjacent_readable": 3})
        self.assertEqual(result["status"], "pass")
        self.assertIn("caveat", result["note"])
        self.assertIn("1 of 4", result["note"])

    def test_a_measured_ring_with_no_comparable_side_fails(self):
        # Defensive: adjacency could not be sampled at all. With no readable
        # side, the indicator is not shown to be perceivable.
        result = keyboard_audit.indicator_verdict(
            {"changed_pixels": 900, "qualifying_pixels": 900, "area_minimum": 560,
             "same_pixel_median": 6.0, "adjacent_worst": 1.4,
             "adjacent_sides": 4, "adjacent_readable": 0})
        self.assertEqual(result["status"], "FAIL")

    def test_clean_ring_passes_and_records_the_aaa_reading(self):
        result = keyboard_audit.indicator_verdict(
            {"changed_pixels": 1266, "qualifying_pixels": 1266, "area_minimum": 560,
             "same_pixel_median": 6.02, "adjacent_worst": 6.02})
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["aaa"]["area_pass"])

    def test_small_ring_passes_the_gate_and_fails_only_the_aaa_area(self):
        # 40 px of change at 6:1: visible, so 2.4.7/1.4.11 pass; the AAA area
        # reading is short. AAA must never change the exit code.
        result = keyboard_audit.indicator_verdict(
            {"changed_pixels": 40, "qualifying_pixels": 40, "area_minimum": 560,
             "same_pixel_median": 6.0, "adjacent_worst": 6.0})
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["aaa"]["area_pass"])

    def test_uncertain_status_is_never_verdicted(self):
        result = keyboard_audit.indicator_verdict(
            {"status": "uncertain:refocused-by-page", "measured": False})
        self.assertTrue(result["status"].startswith("uncertain"))
        self.assertEqual(result["severity"], "review")


class StateContrastTests(unittest.TestCase):
    def test_white_on_dark_passes(self):
        result = keyboard_audit.state_contrast_verdict({
            "method": "resolved", "fg": "rgb(255, 255, 255)",
            "bg": "rgb(13, 59, 102)", "font_size": 16, "font_weight": 400})
        self.assertEqual(result["status"], "pass")

    def test_hover_regression_fails_with_a_message(self):
        # The smoke page: 11.45:1 at rest, near-white on white once hovered.
        result = keyboard_audit.state_contrast_verdict({
            "method": "resolved", "fg": "rgb(242, 242, 242)",
            "bg": "rgb(255, 255, 255)", "font_size": 16, "font_weight": 400,
            "state": "hover"})
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("hover", result["message"])
        self.assertIn("4.5", result["message"])

    def test_large_text_uses_the_large_threshold(self):
        result = keyboard_audit.state_contrast_verdict({
            "method": "resolved", "fg": "rgb(148, 148, 148)",
            "bg": "rgb(255, 255, 255)", "font_size": 24, "font_weight": 400})
        self.assertEqual(result["threshold"], 3.0)
        self.assertEqual(result["status"], "pass")

    def test_uncertain_methods_are_listed_not_verdicted(self):
        result = keyboard_audit.state_contrast_verdict(
            {"method": "uncertain:background-image", "evidence": "div.hero"})
        self.assertEqual(result["status"], "uncertain")

    def test_unparseable_color_is_uncertain(self):
        result = keyboard_audit.state_contrast_verdict({
            "method": "resolved", "fg": "color-mix(in oklch, red, blue)",
            "bg": "rgb(255, 255, 255)", "font_size": 16, "font_weight": 400})
        self.assertEqual(result["status"], "uncertain")


class HoverSameTests(unittest.TestCase):
    def test_hover_equals_focus_is_a_review(self):
        stops = [stop(indicator={"hover_identical": True, "qualifying_pixels": 900})]
        reviews = keyboard_audit.hover_same_reviews(stops)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["check"], "HOVER-SAME")

    def test_no_indicator_suppresses_the_hover_review(self):
        # REGRESSION: with no ring at all, HOVER-SAME restated NO-FOCUS and
        # counted the same defect twice.
        stops = [stop(indicator={"hover_identical": True, "qualifying_pixels": 0})]
        self.assertEqual(keyboard_audit.hover_same_reviews(stops), [])


class ClassifyTests(unittest.TestCase):
    def test_obscured_control_does_not_also_report_no_indicator(self):
        # REGRESSION: a covered control cannot show a ring, so NO-FOCUS there
        # blamed the wrong cause. The 2.4.11 finding owns it.
        covered = stop(obscured={"visible_in_viewport": True,
                                 "samples": [{"related": False, "hit": "div.veil"}] * 5},
                       indicator={"changed_pixels": 0, "qualifying_pixels": 0,
                                  "area_minimum": 560, "same_pixel_median": 0.0,
                                  "measured": True})
        measures, uncertain, _ = keyboard_audit.classify(payload([covered]))
        clauses = [item.get("clause") for item in measures]
        self.assertIn("WCAG 2.4.11", clauses)
        self.assertNotIn("WCAG 2.4.7", clauses)
        self.assertTrue(any(item.get("status", "").startswith("uncertain")
                            for item in uncertain))

    def test_buckets_keep_reviews_out_of_the_exit_code(self):
        reviews_only = payload([stop(tabindex="1", indicator={"changed_pixels": 900,
                                                             "qualifying_pixels": 900,
                                                             "area_minimum": 560,
                                                             "same_pixel_median": 6.0,
                                                             "adjacent_worst": 6.0,
                                                             "measured": True})])
        measures, _, reviews = keyboard_audit.classify(reviews_only)
        self.assertFalse([item for item in measures if item.get("status") == "FAIL"])
        self.assertTrue(reviews)
        self.assertFalse(keyboard_audit.has_measurable_fail(
            keyboard_audit.build_report("http://x/", reviews_only)))

    def test_activation_silence_is_a_review(self):
        data = payload([stop()])
        data["activation"] = [{"tag": "span#fake", "reacted": False}]
        _, _, reviews = keyboard_audit.classify(data)
        self.assertEqual([item["check"] for item in reviews], ["ACTIVATION"])


class ReportTests(unittest.TestCase):
    def test_fail_drives_the_exit_rule(self):
        data = payload([stop(indicator={"changed_pixels": 0, "qualifying_pixels": 0,
                                        "area_minimum": 560,
                                        "same_pixel_median": 0.0, "measured": True})])
        report = keyboard_audit.build_report("http://x/", data)
        self.assertTrue(keyboard_audit.has_measurable_fail(report))
        self.assertEqual(report["summary"]["no_indicator"], 1)

    def test_measure_skipped_is_stated_in_the_report(self):
        data = payload([stop()], measure_skipped="3 stops were not measured")
        report = keyboard_audit.build_report("http://x/", data)
        self.assertIn("not measured", report["summary"]["measure_skipped"])

    def test_text_report_names_every_bucket(self):
        data = payload([stop(indicator={"changed_pixels": 0, "qualifying_pixels": 0,
                                        "area_minimum": 560,
                                        "same_pixel_median": 0.0, "measured": True},
                             tabindex="1")])
        report = keyboard_audit.build_report("http://x/", data)
        text = keyboard_audit.render_text(report)
        self.assertIn("FAIL [WCAG 2.4.7]", text)
        self.assertIn("REVIEW [WCAG 2.4.3", text)
        self.assertIn("Summary:", text)

    def test_json_output_is_parseable(self):
        data = payload([stop()])
        with mock.patch.object(keyboard_audit, "audit_url", return_value=data):
            code, output = run(keyboard_audit.main, ["http://127.0.0.1:1/", "--json"])
        report = json.loads(output)
        self.assertEqual(report["url"], "http://127.0.0.1:1/")
        self.assertTrue(report["verified"])

    def test_a_failed_audit_claims_nothing(self):
        def boom(url, **kwargs):
            raise RuntimeError("no browser")

        with mock.patch.object(keyboard_audit, "audit_url", side_effect=boom):
            code, output = run(keyboard_audit.main, ["http://127.0.0.1:1/"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output)["verified"])

    def test_url_rejection_exits_three(self):
        code, output = run(keyboard_audit.main, ["file:///etc/passwd"])
        self.assertEqual(code, 3)
        self.assertIn("URL rejected", json.loads(output)["reason"])


class SettleTests(unittest.TestCase):
    """The frame-settling path: the bug it prevents, and the bug it had.

    REGRESSION for a NameError: `_settled_shot` shipped calling time.sleep
    without `import time`. It was never exercised, because every test drove the
    pure measurement helpers and nothing drove the screenshot loop — the whole
    suite passed while the tool exited 2 on every real page.
    """

    def test_the_module_imports_time(self):
        self.assertTrue(hasattr(keyboard_audit, "time"))
        self.assertTrue(callable(keyboard_audit.time.sleep))

    def test_agreeing_frames_report_agreement(self):
        frame = flat((10, 20, 30))
        self.assertTrue(keyboard_audit._frames_agree(frame, frame))

    def test_frames_within_tolerance_agree(self):
        self.assertTrue(keyboard_audit._frames_agree(
            flat((10, 20, 30)), flat((12, 22, 32))))

    def test_frames_beyond_tolerance_disagree(self):
        self.assertFalse(keyboard_audit._frames_agree(
            flat((10, 20, 30)), flat((60, 20, 30))))

    def test_unreadable_frames_prove_nothing(self):
        self.assertIsNone(keyboard_audit._frames_agree(b"nope", b"nope"))

    def test_settle_returns_the_first_agreeing_pair(self):
        # Two identical frames arrive after one transient one: the transient
        # frame must not be the one measured.
        transient = flat((200, 0, 0))
        settled = flat((10, 10, 10))
        frames = [transient, settled, settled]

        class FakeSession:
            def __init__(self):
                self.calls = 0

            def send(self, method, params, session=None):
                import base64
                frame = frames[min(self.calls, len(frames) - 1)]
                self.calls += 1
                return {"data": base64.b64encode(frame).decode()}

        with mock.patch.object(keyboard_audit.time, "sleep", lambda _s: None):
            result = keyboard_audit._settled_shot(FakeSession(), "sid", {"x": 0})
        self.assertEqual(result, settled)

    def test_settle_gives_up_and_returns_the_last_frame(self):
        # A page that never settles must still produce a frame; the caller
        # reports the measurement, it does not hang.
        frames = [flat((value, 0, 0)) for value in (10, 90, 170, 250)]

        class FakeSession:
            def __init__(self):
                self.calls = 0

            def send(self, method, params, session=None):
                import base64
                frame = frames[min(self.calls, len(frames) - 1)]
                self.calls += 1
                return {"data": base64.b64encode(frame).decode()}

        with mock.patch.object(keyboard_audit.time, "sleep", lambda _s: None):
            result = keyboard_audit._settled_shot(FakeSession(), "sid", {"x": 0},
                                                  attempts=4)
        self.assertIsNotNone(result)


class MeasurementTests(unittest.TestCase):
    """Pixel arithmetic against hand-built PNGs: no browser, no files."""

    def test_identical_frames_report_no_change(self):
        frame = flat((255, 255, 255))
        result = keyboard_audit.measure_indicator(frame, frame, BOX, margin=6)
        self.assertEqual(result["changed_pixels"], 0)
        self.assertEqual(result["qualifying_pixels"], 0)
        self.assertTrue(result["measured"])

    def test_high_contrast_ring_is_qualified(self):
        # A ring of near-black on white: well over 3:1, so every ring pixel
        # qualifies and the adjacent surface contrast is high.
        focused = ringed((255, 255, 255), (20, 20, 20), (8, 6, 20, 14), thickness=3)
        blurred = flat((255, 255, 255))
        result = keyboard_audit.measure_indicator(focused, blurred, BOX, margin=6)
        self.assertGreater(result["changed_pixels"], 100)
        self.assertEqual(result["changed_pixels"], result["qualifying_pixels"])
        self.assertGreater(result["same_pixel_median"], 15)
        self.assertGreater(result["adjacent_worst"], 3.0)

    def test_faint_ring_changes_pixels_without_qualifying_any(self):
        # REGRESSION: the smoke page's #faint ring moved 846 pixels but peaked
        # at 1.11:1. Change alone must not read as "there is an indicator".
        focused = ringed((255, 255, 255), (243, 243, 243), (8, 6, 20, 14), thickness=3)
        blurred = flat((255, 255, 255))
        result = keyboard_audit.measure_indicator(focused, blurred, BOX, margin=6)
        self.assertGreater(result["changed_pixels"], 50)
        self.assertEqual(result["qualifying_pixels"], 0)
        verdict = keyboard_audit.indicator_verdict(result)
        self.assertEqual(verdict["status"], "FAIL")
        self.assertEqual(verdict["clause"], "WCAG 1.4.11")

    def test_ring_flush_on_a_similar_border_is_not_perceivable(self):
        # A real page pattern: an inset ring drawn on top of a border that is
        # nearly the same colour. The pixels change (geometry), but at 1.03:1
        # the change is invisible — and on a flat surface the same-pixel
        # contrast and the adjacent contrast are the same number, so this is
        # the honest shape of that defect.
        ring_colour, border = (146, 146, 146), (150, 150, 150)
        blurred_rows = canvas((255, 255, 255))
        paint(blurred_rows, (2, 0, 30, HEIGHT), border)
        focused_rows = canvas((255, 255, 255))
        paint(focused_rows, (2, 0, 30, HEIGHT), border)
        paint(focused_rows, (4, 2, 24, HEIGHT - 4), ring_colour)
        result = keyboard_audit.measure_indicator(
            encode(focused_rows), encode(blurred_rows), BOX, margin=6)
        self.assertGreater(result["changed_pixels"], 0)
        self.assertEqual(result["qualifying_pixels"], 0)
        verdict = keyboard_audit.indicator_verdict(result)
        self.assertEqual(verdict["status"], "FAIL")
        self.assertEqual(verdict["clause"], "WCAG 1.4.11")

    def test_area_minimum_uses_the_element_box_not_the_clip(self):
        result = keyboard_audit.measure_indicator(
            flat((255, 255, 255)), flat((255, 255, 255)), BOX, margin=6)
        # 4h + 4w for 20x14 = 56 + 80 = 136; the 12px margins must not enter it.
        self.assertEqual(result["area_minimum"], 136)

    def test_side_statistics_split_the_ring(self):
        focused = ringed((255, 255, 255), (20, 20, 20), (8, 6, 20, 14), thickness=3)
        blurred = flat((255, 255, 255))
        result = keyboard_audit.measure_indicator(focused, blurred, BOX, margin=6)
        for side in ("top", "bottom", "left", "right"):
            self.assertIn(side, result["adjacent_by_side"])

    def test_size_mismatch_is_uncertain(self):
        result = keyboard_audit.measure_indicator(
            flat((255, 255, 255), width=40), flat((255, 255, 255), width=41), BOX)
        self.assertTrue(result["status"].startswith("uncertain"))

    def test_non_png_bytes_are_not_evidence(self):
        self.assertIsNone(keyboard_audit.crops_identical(b"not a png", b"not a png"))

    def test_matching_crops_are_identical(self):
        frame = flat((10, 20, 30))
        self.assertTrue(keyboard_audit.crops_identical(frame, frame))

    def test_one_changed_pixel_breaks_identity(self):
        first = flat((10, 20, 30))
        rows = canvas((10, 20, 30))
        rows[HEIGHT - 1][0:3] = bytes((40, 20, 30))  # 30/channel: past tolerance
        self.assertFalse(keyboard_audit.crops_identical(first, encode(rows)))

    def test_tolerance_absorbs_compressor_noise(self):
        first = flat((10, 20, 30))
        second = flat((12, 22, 32))  # 2/channel: at the tolerance, not past it
        self.assertTrue(keyboard_audit.crops_identical(first, second))

    def test_clip_is_centred_on_the_element_with_margins(self):
        clip = keyboard_audit.make_clip(BOX, margin=10)
        self.assertEqual(clip["x"], -2)
        self.assertEqual(clip["y"], -4)
        self.assertEqual(clip["width"], 40)
        self.assertEqual(clip["height"], 34)
        self.assertEqual(clip["scale"], 1)

    def test_decoder_is_shared_with_image_diff(self):
        # The audit decodes in memory; the bytes-in entry point must agree with
        # the path-based one production screenshots go through.
        data = flat((1, 2, 3), width=4, height=3)
        width, height, pixels = image_diff.decode_png_bytes(data)
        self.assertEqual((width, height), (4, 3))
        self.assertEqual(pixels[:3], b"\x01\x02\x03")


if __name__ == "__main__":
    unittest.main()
