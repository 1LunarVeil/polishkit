"""Browser-free tests for tools/crosscheck.py.

The tool runs three audits that each need a browser, so what is pinned here is
the summarising: which numbers it headlines, and that it never reports a
verified-looking row for an audit that could not run.

REGRESSION: the first version folded contrast pairs, pointer targets and
accessible names into one "fail" count. A page with zero contrast failures and
eight collapsed-panel artefacts read as eight contrast failures, which flatly
contradicted the benchmark stored in benchmark/RESULTS.md and cost an hour of
disbelief before the numbers were re-read.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "skills" / "polishkit" / "scripts"))

import crosscheck  # noqa: E402


def page_report(contrast=0, targets=0, names=0, uncertain=0, review=0):
    return {"summary": {"fail": contrast, "uncertain": uncertain,
                        "review": review, "target_size": targets,
                        "aria_name": names, "heading_order": 0}}


class HeadlineTests(unittest.TestCase):
    def test_page_column_reports_contrast_not_every_clause(self):
        # REGRESSION: 0 contrast failures + 8 target-size failures must not
        # read as 8 contrast failures.
        board = {"summary": {"fail": 0, "uncertain": 12, "review": 0,
                             "target_size": 0, "aria_name": 0, "heading_order": 0},
                 "results": [], "a11y": []}
        with mock.patch("page_audit.audit_url", return_value={}), \
                mock.patch("page_audit.build_report", return_value=board):
            import page_audit
            result = crosscheck.run_audit(page_audit, "http://127.0.0.1:1/")
        self.assertEqual(result["fail"], 0)
        self.assertEqual(result["uncertain"], 12)
        self.assertIn("target_size_fail", result["extra"])

    def test_page_extra_keeps_the_clauses_apart(self):
        board = page_report(contrast=2, targets=5, names=1, uncertain=3)
        with mock.patch("page_audit.audit_url", return_value={}), \
                mock.patch("page_audit.build_report", return_value=board):
            import page_audit
            result = crosscheck.run_audit(page_audit, "http://127.0.0.1:1/")
        self.assertEqual(result["fail"], 2)
        self.assertEqual(result["extra"], {"contrast_fail": 2,
                                           "target_size_fail": 5,
                                           "aria_name_fail": 1})

    def test_an_audit_that_cannot_run_claims_nothing(self):
        import page_audit
        with mock.patch("page_audit.audit_url", side_effect=RuntimeError("no browser")):
            result = crosscheck.run_audit(page_audit, "http://127.0.0.1:1/")
        self.assertFalse(result["verified"])
        self.assertEqual(result["fail"], 0)
        self.assertIn("no browser", result["reason"])


class ReportTests(unittest.TestCase):
    def render_rows(self):
        return [
            {"url": "http://a/", "audits": {
                "page": {"verified": True, "fail": 0, "uncertain": 4},
                "keyboard": {"verified": True, "fail": 1, "uncertain": 0},
                "spacing": {"verified": True, "fail": 0, "uncertain": 0},
                "reflow": {"verified": True, "fail": 0, "uncertain": 2},
                "cjk": {"verified": True, "fail": 0, "uncertain": 0},
                "expr": {"verified": True, "fail": 0, "uncertain": 3}}},
            {"url": "http://b/", "audits": {
                "page": {"verified": False, "reason": "no browser"},
                "keyboard": {"verified": True, "fail": 0, "uncertain": 0},
                "spacing": {"verified": True, "fail": 0, "uncertain": 0},
                "reflow": {"verified": True, "fail": 0, "uncertain": 0},
                "cjk": {"verified": True, "fail": 0, "uncertain": 0},
                "expr": {"verified": True, "fail": 0, "uncertain": 3}}},
        ]

    def test_unverified_audits_are_named_not_zeroed(self):
        text = crosscheck.render(self.render_rows())
        self.assertIn("UNVERIFIED", text)
        self.assertIn("http://a/", text)

    def test_summary_counts_unverified_rows(self):
        lines, unverified = crosscheck.summarise(self.render_rows())
        self.assertEqual(unverified, 1)
        self.assertEqual(len(lines), 2)

    def test_legend_names_the_clauses(self):
        text = crosscheck.render(self.render_rows())
        for clause in ("1.4.3", "2.1.1", "1.4.12"):
            self.assertIn(clause, text)

    def test_all_four_audits_are_registered(self):
        names = [name for name, _module, _covers in crosscheck.AUDITS]
        self.assertEqual(names,
                         ["page", "keyboard", "spacing", "reflow", "cjk", "expr"])


if __name__ == "__main__":
    unittest.main()
