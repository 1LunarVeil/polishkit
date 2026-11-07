"""Browser-free tests for page_audit.py.

The collector runs in a browser, so everything Python-side is pinned here with
synthetic rows shaped exactly like the collector emits (page_audit.row fields
are dicts; real-browser behaviour is a manual smoke, per the WS-A convention).
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

import page_audit  # noqa: E402


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
    """One collector row: near-black on white body text by default."""
    base = {
        "method": "resolved",
        "fg": "rgb(51, 51, 51)",
        "bg": "rgb(255, 255, 255)",
        "font_size": 16,
        "font_weight": 400,
        "rect": {"x": 8, "y": 8, "width": 200, "height": 24},
        "text": "sample text",
        "tag": "p",
        "evidence": None,
    }
    base.update(overrides)
    return base


def payload(rows, **overrides):
    base = {"color_scheme": "light", "canvas": "#ffffff",
            "rows": rows, "skipped": 0, "capped": False, "limit": 400}
    base.update(overrides)
    return base


class ThresholdTests(unittest.TestCase):
    def test_measurable_pass_gets_ratio_and_threshold(self):
        # rgb(118,118,118) on white is 4.54:1 — over the 4.5 floor.
        result = page_audit.verdict(row(fg="rgb(118, 118, 118)"))
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["threshold"], 4.5)
        self.assertAlmostEqual(result["ratio"], 4.54, places=2)

    def test_fail_at_4_5(self):
        # rgb(153,153,153) on white is 2.85:1.
        result = page_audit.verdict(row(fg="rgb(153, 153, 153)"))
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["threshold"], 4.5)
        self.assertAlmostEqual(result["ratio"], 2.85, places=2)

    def test_large_text_thresholds_at_boundaries(self):
        cases = [
            ({"font_size": 24, "font_weight": 400}, 3.0),   # >= 24px, any weight
            ({"font_size": 24, "font_weight": 700}, 3.0),
            ({"font_size": 23.9, "font_weight": 400}, 4.5),
            ({"font_size": 18.66, "font_weight": 700}, 3.0),  # bold large floor
            ({"font_size": 18.65, "font_weight": 700}, 4.5),
            ({"font_size": 18.66, "font_weight": 400}, 4.5),  # large size, not bold
            ({"font_size": 16, "font_weight": 900}, 4.5),
        ]
        for overrides, expected in cases:
            self.assertEqual(page_audit.threshold_for(row(**overrides)), expected, overrides)

    def test_large_text_3_to_1_verdict(self):
        # rgb(128,128,128) on white is 3.95:1: passes as 24px bold, fails as body text.
        large = page_audit.verdict(row(fg="rgb(128, 128, 128)",
                                       font_size=24, font_weight=700))
        self.assertEqual(large["verdict"], "pass")
        self.assertEqual(large["threshold"], 3.0)
        body = page_audit.verdict(row(fg="rgb(128, 128, 128)"))
        self.assertEqual(body["verdict"], "FAIL")
        self.assertEqual(body["threshold"], 4.5)


class ClassifyTests(unittest.TestCase):
    def test_assumed_canvas_labeled_verdicted_and_counted(self):
        rows = [
            row(method="assumed-canvas", bg="#ffffff"),
            row(method="assumed-canvas", bg="#ffffff", fg="rgb(153, 153, 153)"),
        ]
        verdicts, uncertain, skipped = page_audit.classify_rows(rows)
        self.assertEqual(skipped, 0)
        self.assertEqual(uncertain, [])
        self.assertEqual([v["method"] for v in verdicts], ["assumed-canvas"] * 2)
        self.assertEqual([v["verdict"] for v in verdicts], ["pass", "FAIL"])
        report = page_audit.build_report("http://x/", payload(rows))
        self.assertEqual(report["summary"]["assumed_canvas"], 2)

    def test_uncertain_methods_preserved_verbatim_never_verdicted(self):
        methods = [
            ("uncertain:gradient-or-image", "linear-gradient(90deg, rgb(11, 87, 208), rgb(168, 199, 250))"),
            ("uncertain:blend-or-filter", "div.fade opacity=0.5"),
            ("uncertain:occluded", "div.cookie-bar"),
            ("uncertain:some-future-method", "whatever"),
        ]
        rows = [row(method=method, evidence=evidence) for method, evidence in methods]
        verdicts, uncertain, skipped = page_audit.classify_rows(rows)
        self.assertEqual([verdicts, skipped], [[], 0])
        self.assertEqual([u["method"] for u in uncertain], [m for m, _ in methods])
        self.assertEqual([u["evidence"] for u in uncertain], [e for _, e in methods])
        for entry in uncertain:
            self.assertNotIn("verdict", entry)
            self.assertNotIn("ratio", entry)
            self.assertIsNone(page_audit.verdict(entry))

    def test_occluded_row_classified_with_cover_evidence(self):
        rows = [row(method="uncertain:occluded", evidence="header.site-nav")]
        verdicts, uncertain, _ = page_audit.classify_rows(rows)
        self.assertEqual(verdicts, [])
        self.assertEqual(uncertain[0]["method"], "uncertain:occluded")
        self.assertEqual(uncertain[0]["evidence"], "header.site-nav")

    def test_skipped_counted_not_listed(self):
        rows = [
            row(),
            row(method="skipped", text="hidden heading", tag="h1"),
        ]
        verdicts, uncertain, skipped = page_audit.classify_rows(rows, skipped_count=2)
        self.assertEqual(skipped, 3)
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(uncertain, [])
        report = page_audit.build_report("http://x/", payload(rows, skipped=2))
        self.assertEqual(report["summary"]["skipped"], 3)
        self.assertNotIn("skipped", [str(entry.get("method")) for entry in report["results"]])

    def test_unparseable_color_becomes_uncertain_not_a_crash(self):
        # wcag.parse_color has no hsl support; the row must degrade, not raise.
        rows = [row(fg="hsl(0, 50%, 50%)")]
        verdicts, uncertain, _ = page_audit.classify_rows(rows)
        self.assertEqual(verdicts, [])
        self.assertEqual(uncertain[0]["method"], "uncertain:unparseable")
        self.assertIn("hsl", uncertain[0]["evidence"])

    def test_summary_math(self):
        rows = [
            row(),                                   # pass
            row(text="b"),                           # pass
            row(text="c"),                           # pass
            row(fg="rgb(153, 153, 153)", text="d"),  # FAIL
            row(fg="rgb(153, 153, 153)", text="e"),  # FAIL
            row(method="uncertain:gradient-or-image", evidence="linear-gradient(1px)"),
            row(method="uncertain:occluded", evidence="div.nav"),
        ]
        report = page_audit.build_report("http://x/", payload(rows, skipped=1))
        summary = report["summary"]
        self.assertEqual(summary["checked"], 7)
        self.assertEqual(summary["pass"], 3)
        self.assertEqual(summary["fail"], 2)
        self.assertEqual(summary["uncertain"], 2)
        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(summary["checked"], summary["pass"] + summary["fail"] + summary["uncertain"])
        self.assertEqual(summary["assumed_canvas"], 0)

    def test_exit_code_rule_is_fail_only(self):
        self.assertEqual(1 if page_audit.build_report(
            "http://x/", payload([row(fg="rgb(153, 153, 153)")]))["summary"]["fail"] else 0, 1)
        self.assertEqual(1 if page_audit.build_report(
            "http://x/", payload([row(method="uncertain:occluded", evidence="d")]))["summary"]["fail"] else 0, 0)


class ReportTests(unittest.TestCase):
    def test_header_carries_url_canvas_assumption_and_scheme(self):
        report = page_audit.build_report(
            "http://127.0.0.1:8125/", payload([row()], color_scheme="light", canvas="#ffffff"))
        self.assertEqual(report["url"], "http://127.0.0.1:8125/")
        self.assertTrue(report["verified"])
        self.assertEqual(report["color_scheme"], "light")
        self.assertIn("#ffffff", report["canvas_assumption"])
        self.assertIn("prefers-color-scheme: light", report["canvas_assumption"])

    def test_text_report_orders_fails_then_uncertain_then_summary(self):
        rows = [
            row(method="assumed-canvas", bg="#ffffff"),
            row(method="uncertain:gradient-or-image", evidence="linear-gradient(90deg, a, b)"),
            row(fg="rgb(153, 153, 153)", text="Failing pair."),
        ]
        text = page_audit.render_text(page_audit.build_report("http://x/", payload(rows)))
        lines = text.splitlines()
        self.assertIn("Page audit: http://x/", lines[0])
        self.assertIn("Clauses: WCAG 1.4.3", lines[1])       # v2 header names the clauses
        self.assertIn("Canvas assumption:", lines[2])
        fails = [i for i, line in enumerate(lines) if line.startswith("FAIL ")]
        uncertains = [i for i, line in enumerate(lines) if line.startswith("UNCERTAIN ")]
        summary = [i for i, line in enumerate(lines) if line.startswith("checked ")]
        self.assertEqual(len(fails), 1)
        self.assertEqual(len(uncertains), 1)
        self.assertLess(fails[0], uncertains[0])
        self.assertLess(uncertains[0], summary[0])
        self.assertIn('UNCERTAIN uncertain:gradient-or-image "sample text" p '
                      '[linear-gradient(90deg, a, b)]', lines[uncertains[0]])
        self.assertIn("checked 3 text pairs: 1 pass, 1 fail, 1 uncertain, "
                      "0 skipped (1 assumed canvas)", lines[summary[0]])

    def test_capped_note_in_text_and_summary(self):
        report = page_audit.build_report("http://x/", payload([row()], capped=True, limit=3))
        self.assertTrue(report["summary"]["capped"])
        self.assertEqual(report["summary"]["limit"], 3)
        self.assertIn("[capped at 3 entries]", page_audit.render_text(report))

    def test_json_report_shape(self):
        rows = [row(fg="rgb(153, 153, 153)"),
                row(method="uncertain:occluded", evidence="div.nav")]
        report = page_audit.build_report("http://x/", payload(rows, skipped=1))
        rendered = json.loads(json.dumps(report))
        self.assertEqual(set(rendered), {"url", "verified", "color_scheme",
                                         "canvas_assumption", "clause_coverage",
                                         "results", "a11y", "summary"})
        self.assertTrue(rendered["verified"])
        self.assertEqual(len(rendered["results"]), 2)
        self.assertEqual(rendered["a11y"], [])
        self.assertEqual(set(rendered["summary"]), {
            "checked", "pass", "fail", "uncertain", "skipped", "assumed_canvas",
            "capped", "target_size", "target_pass", "aria_name", "name_pass",
            "heading_order", "findings_capped"})


class CliTests(unittest.TestCase):
    URL = "http://127.0.0.1:1/"  # loopback: validate_url needs no network

    def test_rejected_url_exits_3_and_claims_nothing(self):
        code, out = run(page_audit.main, ["ftp://example.com/"])
        self.assertEqual(code, 3)
        body = json.loads(out)
        self.assertFalse(body["verified"])
        self.assertIn("URL rejected", body["reason"])

    def test_cdp_failure_exits_2_with_unverified_json(self):
        with mock.patch.object(page_audit, "audit_url",
                               side_effect=RuntimeError("browser exploded")):
            code, out = run(page_audit.main, [self.URL, "--json"])
        self.assertEqual(code, 2)
        body = json.loads(out)
        self.assertEqual(set(body), {"verified", "reason"})
        self.assertFalse(body["verified"])
        self.assertIn("browser exploded", body["reason"])

    def test_json_cli_shape_with_stubbed_audit(self):
        stub = payload(
            [row(), row(method="uncertain:occluded", evidence="div.nav")], skipped=1)
        with mock.patch.object(page_audit, "audit_url", return_value=stub):
            code, out = run(page_audit.main, [self.URL, "--json"])
        self.assertEqual(code, 0)
        body = json.loads(out)
        self.assertEqual(body["url"], self.URL)
        self.assertTrue(body["verified"])
        self.assertEqual(body["color_scheme"], "light")
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["summary"]["checked"], 2)
        self.assertEqual(body["summary"]["skipped"], 1)

    def test_text_cli_shape_and_exit_1_on_fail(self):
        stub = payload([row(fg="rgb(153, 153, 153)", text="Failing pair.")])
        with mock.patch.object(page_audit, "audit_url", return_value=stub):
            code, out = run(page_audit.main, [self.URL])
        self.assertEqual(code, 1)
        self.assertIn("FAIL rgb(153, 153, 153) on rgb(255, 255, 255) 2.85:1", out)
        self.assertIn("checked 1 text pairs: 0 pass, 1 fail, 0 uncertain, "
                      "0 skipped (0 assumed canvas)", out)


# --- v2 a11y findings -------------------------------------------------------


def target_finding(**overrides):
    """One collector TARGET-SIZE finding: 20x22 button by default (undersized)."""
    base = {"check": "TARGET-SIZE", "kind": "measure", "tag": "button.cta",
            "rect": {"x": 8, "y": 8, "width": 20, "height": 22}}
    base.update(overrides)
    return base


def name_finding(**overrides):
    """One collector ARIA-NAME finding: unnamed input by default."""
    base = {"check": "ARIA-NAME", "kind": "measure", "tag": "input.email",
            "name": None,
            "absent": ["aria-label", "aria-labelledby", "title", "label"],
            "note": "placeholder is not a name",
            "rect": {"x": 0, "y": 0, "width": 200, "height": 28}}
    base.update(overrides)
    return base


class TargetSizeTests(unittest.TestCase):
    def test_under_24px_fails_with_rect_evidence(self):
        measures, uncertain, reviews = page_audit.classify_findings([target_finding()])
        self.assertEqual((len(measures), uncertain, reviews), (1, [], []))
        entry = measures[0]
        self.assertEqual(entry["status"], "FAIL")
        self.assertEqual(entry["severity"], "important")
        self.assertEqual(entry["clause"], "WCAG 2.5.8")
        message = page_audit.a11y_message(entry)
        self.assertIn("button.cta pointer target 20x22 at (8, 8)", message)
        self.assertIn("24x24 CSS px floor (WCAG 2.5.8 AA)", message)

    def test_floor_boundary_pass_and_fail(self):
        self.assertEqual(page_audit.target_size_verdict({"width": 24, "height": 24})["status"], "pass")
        self.assertEqual(page_audit.target_size_verdict({"width": 23.9, "height": 40})["status"], "FAIL")
        self.assertEqual(page_audit.target_size_verdict({"width": 40, "height": 23.9})["status"], "FAIL")
        self.assertEqual(page_audit.target_size_verdict({"width": 0, "height": 0})["status"], "FAIL")
        self.assertEqual(page_audit.target_size_verdict(None)["status"], "FAIL")

    def test_inline_link_exception_is_uncertain_never_verdicted(self):
        finding = target_finding(method="uncertain:inline-link", tag="a.more",
                                 kind=None, text="Read more")
        measures, uncertain, reviews = page_audit.classify_findings([finding])
        self.assertEqual((measures, reviews), ([], []))
        entry = uncertain[0]
        self.assertEqual(entry["status"], "uncertain")
        self.assertEqual(entry["severity"], "review")
        self.assertIn("2.5.8 Inline exception", page_audit.a11y_message(entry))


class AriaNameTests(unittest.TestCase):
    def test_missing_name_fails_with_absent_sources(self):
        measures, uncertain, reviews = page_audit.classify_findings([name_finding()])
        self.assertEqual((len(measures), uncertain, reviews), (1, [], []))
        entry = measures[0]
        self.assertEqual(entry["status"], "FAIL")
        self.assertEqual(entry["severity"], "important")
        message = page_audit.a11y_message(entry)
        self.assertIn("input.email has no accessible name", message)
        self.assertIn("no aria-label", message)
        self.assertIn("placeholder is not a name", message)
        self.assertIn("(WCAG 4.1.2 / 1.1.1)", message)

    def test_img_without_alt_names_the_missing_source(self):
        finding = name_finding(tag="img.hero",
                               absent=["alt", "aria-label", "aria-labelledby", "title"],
                               note=None)
        message = page_audit.a11y_message(page_audit.classify_findings([finding])[0][0])
        self.assertIn("img.hero has no accessible name (no alt", message)

    def test_present_name_passes_and_names_the_source(self):
        finding = name_finding(name="text: Save changes", absent=[], note=None)
        measures, uncertain, reviews = page_audit.classify_findings([finding])
        self.assertEqual((len(measures), uncertain, reviews), (1, [], []))
        self.assertEqual(measures[0]["status"], "pass")
        self.assertIn('named via "text: Save changes"', page_audit.a11y_message(measures[0]))

    def test_decorative_alt_counts_as_a_name(self):
        # 1.1.1: alt="" is a valid text alternative for a decorative image.
        finding = name_finding(tag="img.divider", name="alt='' (decorative)",
                               absent=[], note=None)
        measures, _, _ = page_audit.classify_findings([finding])
        self.assertEqual(measures[0]["status"], "pass")


class HeadingOrderTests(unittest.TestCase):
    def test_level_jump_is_review_not_a_fail(self):
        finding = {"check": "HEADING-ORDER", "kind": "review", "tag": "h3.section",
                   "prev_tag": "h1.page", "from": 1, "to": 3,
                   "rect": {"x": 0, "y": 0, "width": 100, "height": 20}}
        measures, uncertain, reviews = page_audit.classify_findings([finding])
        self.assertEqual((measures, uncertain), ([], []))
        entry = reviews[0]
        self.assertEqual((entry["status"], entry["severity"]), ("review", "review"))
        self.assertIn("not a WCAG failure", entry["clause"])
        message = page_audit.a11y_message(entry)
        self.assertIn("h1.page (h1) to h3.section (h3)", message)

    def test_missing_h1_is_review(self):
        finding = {"check": "HEADING-ORDER", "kind": "review", "tag": None, "missing": "h1"}
        reviews = page_audit.classify_findings([finding])[2]
        self.assertEqual(reviews[0]["status"], "review")
        self.assertIn("no h1", page_audit.a11y_message(reviews[0]))


class A11yReportTests(unittest.TestCase):
    def mixed_findings(self):
        return [
            target_finding(),                                   # FAIL
            target_finding(rect={"x": 0, "y": 40, "width": 96, "height": 32}),  # pass
            name_finding(),                                     # FAIL
            name_finding(name="text: Save", absent=[], note=None),  # pass
            {"check": "HEADING-ORDER", "kind": "review", "tag": "h3.s",
             "prev_tag": "h1.p", "from": 1, "to": 3},           # review
            target_finding(method="uncertain:inline-link", tag="a.more",
                           kind=None, text="Read more"),        # uncertain
        ]

    def test_summary_counts_every_bucket(self):
        report = page_audit.build_report("http://x/", payload([row()], findings=self.mixed_findings()))
        summary = report["summary"]
        self.assertEqual((summary["target_size"], summary["target_pass"]), (1, 1))
        self.assertEqual((summary["aria_name"], summary["name_pass"]), (1, 1))
        self.assertEqual(summary["heading_order"], 1)
        self.assertEqual(len(report["a11y"]), 4)  # 2 fails + 1 review + 1 inline uncertain

    def test_a11y_failures_drive_the_exit_rule(self):
        report = page_audit.build_report("http://x/", payload([row()], findings=self.mixed_findings()))
        self.assertTrue(page_audit.has_measurable_fail(report))
        passes_only = page_audit.build_report("http://x/", payload([], findings=[
            target_finding(rect={"x": 0, "y": 0, "width": 96, "height": 32}),
            name_finding(name="text: ok", absent=[], note=None),
            {"check": "HEADING-ORDER", "kind": "review", "tag": "h3.s",
             "prev_tag": "h1.p", "from": 1, "to": 3},
            target_finding(method="uncertain:inline-link", tag="a.more", kind=None),
        ]))
        self.assertFalse(page_audit.has_measurable_fail(passes_only))

    def test_render_text_groups_fails_uncertains_reviews_and_summary(self):
        report = page_audit.build_report("http://x/", payload([], findings=self.mixed_findings()))
        lines = page_audit.render_text(report).splitlines()
        kinds = []
        for line in lines:
            if line.startswith("FAIL TARGET-SIZE"):
                kinds.append(("FAIL", line))
                self.assertIn("below the 24x24 CSS px floor", line)
            elif line.startswith("FAIL ARIA-NAME"):
                kinds.append(("FAIL", line))
            elif line.startswith("UNCERTAIN uncertain:inline-link"):
                kinds.append(("UNCERTAIN", line))
                self.assertIn("Read more", line)
            elif line.startswith("REVIEW HEADING-ORDER"):
                kinds.append(("REVIEW", line))
                self.assertIn("h1.p (h1) to h3.s (h3)", line)
        statuses = [kind for kind, _ in kinds]
        self.assertEqual(statuses.count("FAIL"), 2)
        self.assertEqual(statuses.count("UNCERTAIN"), 1)
        self.assertEqual(statuses.count("REVIEW"), 1)
        positions = [statuses.index(k) for k in ("FAIL", "UNCERTAIN", "REVIEW")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("a11y: 1 target-size fails (1 pass), 1 unnamed (1 named), "
                      "1 heading-order reviews", lines[-1])

    def test_findings_capped_note(self):
        report = page_audit.build_report("http://x/", payload([], findings_capped=True))
        self.assertTrue(report["summary"]["findings_capped"])
        self.assertIn("[findings capped at 200]", page_audit.render_text(report))


if __name__ == "__main__":
    unittest.main()
