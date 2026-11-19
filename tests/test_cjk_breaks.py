"""Browser-free tests for cjk_breaks.py.

The collector walks rendered lines with a Range, so what is pinned here is the
deciding logic: which characters are forbidden at a line edge, which findings
are failures versus judgements, and that a page without CJK text claims
nothing.

The character sets are the interesting part. They are derived from Unicode
categories rather than copied from clreq's table, so the tests assert the
derivation holds where it could drift: every closing bracket is forbidden at
line start, no opening bracket is, and a full stop is forbidden while an
opening quote is not.
"""

import io
import json
import sys
import unittest
import unicodedata
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "skills" / "polishkit" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cjk_breaks  # noqa: E402


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


def element(**overrides):
    base = {"tag": "p", "word_break": "normal", "line_break": "auto",
            "text_autospace": "normal", "mixed_scripts": False, "lines": []}
    base.update(overrides)
    return base


def payload(elements=None, **overrides):
    base = {"cjk": True, "checked": len(elements or []), "lines": 0,
            "elements": elements or [], "capped": False, "viewport_width": 390}
    base.update(overrides)
    return base


class CharacterSetTests(unittest.TestCase):
    def test_every_closing_bracket_may_not_start_a_line(self):
        # `Pe` is the whole closing-bracket category; none of them may open a
        # line, and the derivation must not have lost one.
        closers = [chr(cp) for cp in range(0x20, 0x30000)
                   if unicodedata.category(chr(cp)) == "Pe"]
        self.assertTrue(closers, "expected the Pe category to be populated")
        for char in closers:
            self.assertTrue(cjk_breaks.forbidden_at_start(char),
                            f"{hex(ord(char))} {unicodedata.name(char, '?')} "
                            f"is a closer and must be forbidden at line start")

    def test_no_opening_bracket_is_forbidden_at_line_start(self):
        openers = [chr(cp) for cp in range(0x20, 0x30000)
                   if unicodedata.category(chr(cp)) == "Ps"]
        self.assertTrue(openers)
        for char in openers:
            self.assertFalse(cjk_breaks.forbidden_at_start(char),
                             f"{hex(ord(char))} {unicodedata.name(char, '?')} "
                             f"may open a line")

    def test_terminal_punctuation_is_forbidden_at_line_start(self):
        for char in "、。，：；！？":
            self.assertTrue(cjk_breaks.forbidden_at_start(char), char)

    def test_an_opening_quote_is_not_forbidden_at_line_start(self):
        # It is `Pi` in Unicode, and it opens rather than closes.
        for char in "“‘「『":
            self.assertFalse(cjk_breaks.forbidden_at_start(char), char)

    def test_opening_brackets_may_not_end_a_line(self):
        for char in "（［｛「『【〈《":
            self.assertTrue(cjk_breaks.forbidden_at_end(char), char)

    def test_closing_brackets_may_end_a_line(self):
        for char in "）」』】〉》":
            self.assertFalse(cjk_breaks.forbidden_at_end(char), char)

    def test_an_empty_line_edge_is_never_a_violation(self):
        self.assertFalse(cjk_breaks.forbidden_at_start(""))
        self.assertFalse(cjk_breaks.forbidden_at_end(""))


class CjkDetectionTests(unittest.TestCase):
    def test_han_text_is_cjk(self):
        self.assertTrue(cjk_breaks.is_cjk_text("这是一个中文句子，没有拉丁字母。"))

    def test_latin_text_is_not_cjk(self):
        self.assertFalse(cjk_breaks.is_cjk_text("This is an English sentence."))

    def test_mixed_text_with_a_few_han_characters_is_not_cjk_prose(self):
        # A single 中 in an English paragraph must not make the element a CJK
        # element and pull the whole paragraph into the audit.
        self.assertFalse(cjk_breaks.is_cjk_text("This is mostly English with 中 only."))

    def test_cjk_punctuation_counts_as_cjk(self):
        # The punctuation blocks are part of the range, so a run of them is not
        # mistaken for Latin.
        self.assertTrue(cjk_breaks.is_cjk_text("……？！"))

    def test_whitespace_does_not_dilute_the_ratio(self):
        self.assertTrue(cjk_breaks.is_cjk_text("中 文 字\t词\n句"))

    def test_empty_text_is_not_cjk(self):
        self.assertFalse(cjk_breaks.is_cjk_text(""))
        self.assertFalse(cjk_breaks.is_cjk_text("   "))


class ClassifyTests(unittest.TestCase):
    def test_a_clean_element_yields_nothing(self):
        measures, uncertain, reviews = cjk_breaks.classify(payload([element()]))
        self.assertEqual((measures, uncertain, reviews), ([], [], []))

    def test_line_start_violation_is_a_failure(self):
        entry = element(lines=[{"index": 2, "first": "、", "last": "下",
                                "violation": "start", "snippet": "、接下来"}])
        measures, _, _ = cjk_breaks.classify(payload([entry]))
        self.assertEqual(len(measures), 1)
        self.assertEqual(measures[0]["check"], "LINE-START")
        self.assertEqual(measures[0]["clause"], "clreq §6.1.1")
        self.assertIn("、", measures[0]["message"])

    def test_line_end_violation_is_a_failure(self):
        entry = element(lines=[{"index": 1, "first": "测", "last": "（",
                                "violation": "end", "snippet": "测试文字（"}])
        measures, _, _ = cjk_breaks.classify(payload([entry]))
        self.assertEqual([m["check"] for m in measures], ["LINE-END"])

    def test_break_all_is_a_review_never_a_failure(self):
        # The property is a tell, not a failure: a page can set it and still
        # break at legal places.
        entry = element(word_break="break-all")
        measures, _, reviews = cjk_breaks.classify(payload([entry]))
        self.assertEqual(measures, [])
        self.assertEqual([r["check"] for r in reviews], ["BREAK-ALL"])

    def test_missing_autospace_is_a_review(self):
        entry = element(mixed_scripts=True, text_autospace="normal")
        measures, _, reviews = cjk_breaks.classify(payload([entry]))
        self.assertEqual(measures, [])
        self.assertEqual([r["check"] for r in reviews], ["NO-AUTOSPACE"])

    def test_autospace_on_a_pure_cjk_run_is_not_reported(self):
        entry = element(mixed_scripts=False, text_autospace="normal")
        _, _, reviews = cjk_breaks.classify(payload([entry]))
        self.assertEqual(reviews, [])

    def test_pre_formatted_text_is_uncertain(self):
        entry = element(skip="white-space-pre",
                        evidence="wrapping is authored explicitly")
        measures, uncertain, _ = cjk_breaks.classify(payload([entry]))
        self.assertEqual(measures, [])
        self.assertEqual(uncertain[0]["status"], "uncertain")
        self.assertIn("white-space-pre", uncertain[0]["method"])


class ReportTests(unittest.TestCase):
    def test_a_page_without_cjk_claims_nothing_else(self):
        report = cjk_breaks.build_report("http://x/", payload([], cjk=False))
        text = cjk_breaks.render_text(report)
        self.assertIn("No CJK prose", text)
        self.assertFalse(cjk_breaks.has_measurable_fail(report))

    def test_a_violation_drives_the_exit_rule(self):
        entry = element(lines=[{"index": 1, "first": "测", "last": "（",
                                "violation": "end", "snippet": "测试（"}])
        report = cjk_breaks.build_report("http://x/", payload([entry]))
        self.assertTrue(cjk_breaks.has_measurable_fail(report))
        self.assertEqual(report["summary"]["line_end"], 1)

    def test_break_all_alone_does_not_fail_the_page(self):
        report = cjk_breaks.build_report("http://x/", payload([element(word_break="break-all")]))
        self.assertFalse(cjk_breaks.has_measurable_fail(report))
        self.assertEqual(report["summary"]["review"], 1)

    def test_json_output_is_parseable(self):
        with mock.patch.object(cjk_breaks, "audit_url", return_value=payload([element()])):
            code, output = run(cjk_breaks.main, ["http://127.0.0.1:1/", "--json"])
        report = json.loads(output)
        self.assertTrue(report["verified"])
        self.assertTrue(report["cjk"])

    def test_a_failed_audit_claims_nothing(self):
        def boom(url, **kwargs):
            raise cjk_breaks.cdp.BrowserError("navigation failed: net::ERR_CONNECTION_REFUSED")

        with mock.patch.object(cjk_breaks, "audit_url", side_effect=boom):
            code, output = run(cjk_breaks.main, ["http://127.0.0.1:1/"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output)["verified"])

    def test_url_rejection_exits_three(self):
        code, output = run(cjk_breaks.main, ["file:///etc/passwd"])
        self.assertEqual(code, 3)


class CollectorContractTests(unittest.TestCase):
    def test_the_collector_script_carries_the_character_sets(self):
        # The browser-side walker needs both sets; a serialisation slip would
        # silently disable every prohibition test.
        self.assertIn("CLOSING", cjk_breaks.COLLECTOR_JS)
        self.assertIn("OPENING", cjk_breaks.COLLECTOR_JS)
        closing = json.dumps("".join(sorted(cjk_breaks.CLOSING_PUNCTUATION)),
                             ensure_ascii=False)
        self.assertIn("、", closing)
        self.assertIn("。", closing)
        # Round-trip: every character survives the encoding the collector uses.
        self.assertEqual(json.loads(closing),
                         "".join(sorted(cjk_breaks.CLOSING_PUNCTUATION)))


if __name__ == "__main__":
    unittest.main()
