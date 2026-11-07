"""Tests for token_lint, the design-token auditor.

Run from the plugin root: python -B -m unittest discover -s tests -v
(-B keeps __pycache__ out of the plugin tree.)
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "skills" / "polishkit" / "scripts"
FIXTURES = TESTS / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import token_lint  # noqa: E402


def run(main, argv):
    """Run a script's main() with stdout and stderr captured; return (exit code, stdout text)."""
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


def write(tmp, name, text):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def findings_for(text, name="tokens.css"):
    """Scan one hand-written token file in a throwaway directory."""
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, name, text)
        findings, _ = token_lint.scan([tmp])
    return findings


class RawLeakTests(unittest.TestCase):
    def test_raw_leak_fires_under_the_old_threshold_of_eight(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "app.css", ".a { color: #0f172a; }\n.b { border-color: #123456; }\n")
            findings, scanned = token_lint.scan([tmp])
        raw = [f for f in findings if f.rule == "RAW-LEAK"]
        self.assertEqual(len(raw), 1)
        self.assertEqual((raw[0].severity, scanned), ("polish", 1))
        self.assertIn("2 raw hex colors", raw[0].message)

    def test_suppressed_for_definitions_and_var_uses(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "app.css", ":root { --brand: #5b3df5; }\n.a { color: var(--brand); }\n")
            findings, _ = token_lint.scan([tmp])
        self.assertEqual([f for f in findings if f.rule == "RAW-LEAK"], [])

    def test_suggests_var_when_the_value_matches_a_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "tokens.css", ":root { --brand: #5b3df5; }\n")
            write(tmp, "app.css", ".a { background: #5B3DF5; }\n")  # uppercase on purpose
            findings, _ = token_lint.scan([tmp])
        raw = next(f for f in findings if f.rule == "RAW-LEAK")
        self.assertIn("use var(--brand)", raw.message)

    def test_reports_when_no_token_matches(self):
        findings = findings_for(".a { color: #0f172a; }\n", name="app.css")
        raw = next(f for f in findings if f.rule == "RAW-LEAK")
        self.assertIn("#0f172a (no token)", raw.message)
        self.assertIn("move them into the token file", raw.message)

    def test_one_finding_per_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.css", ".a { color: #0f172a; }\n")
            write(tmp, "b.css", ".b { color: #111111; }\n")
            findings, _ = token_lint.scan([tmp])
        raw = [f for f in findings if f.rule == "RAW-LEAK"]
        self.assertEqual(len(raw), 2)
        self.assertEqual(len({f.file for f in raw}), 2)


class DefContrastTests(unittest.TestCase):
    def test_failing_text_pair_is_important(self):
        findings = findings_for(":root { --bg: #ffffff; --text: #9ca3af; }\n")
        contrast = [f for f in findings if f.rule == "DEF-CONTRAST"]
        self.assertEqual(len(contrast), 1)
        self.assertEqual(contrast[0].severity, "important")
        self.assertIn("--text on --bg is 2.54:1", contrast[0].message)
        self.assertIn("WCAG 1.4.3", contrast[0].message)

    def test_passing_pair_is_silent(self):
        findings = findings_for(":root { --bg: #ffffff; --text: #111827; }\n")
        self.assertEqual([f for f in findings if f.rule == "DEF-CONTRAST"], [])

    def test_border_pair_below_three_is_review(self):
        findings = findings_for(":root { --bg: #ffffff; --border: #e5e7eb; }\n")
        contrast = [f for f in findings if f.rule == "DEF-CONTRAST"]
        self.assertEqual([(f.severity, f.line) for f in contrast], [("review", 1)])
        self.assertIn("below the 3:1 WCAG UI floor", contrast[0].message)

    def test_var_alias_resolves_before_checking(self):
        findings = findings_for(":root { --ink: #9ca3af; --text: var(--ink); --bg: #ffffff; }\n")
        contrast = [f for f in findings if f.rule == "DEF-CONTRAST"]
        self.assertEqual(len(contrast), 1)
        self.assertIn("--text on --bg is 2.54:1", contrast[0].message)


class MissingRolesTests(unittest.TestCase):
    def test_missing_roles_are_one_aggregate_finding(self):
        findings = findings_for(":root { --color-bg: #ffffff; --color-text: #111827; }\n")
        missing = [f for f in findings if f.rule == "MISSING-ROLES"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].severity, "review")
        self.assertIn("muted, border, accent, success, warning, danger", missing[0].message)

    def test_no_tokens_at_all_is_important(self):
        findings = findings_for(".a { color: red; }\n", name="app.css")
        missing = [f for f in findings if f.rule == "MISSING-ROLES"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].severity, "important")
        self.assertIn("no design tokens found", missing[0].message)


class UnusedTokenTests(unittest.TestCase):
    def test_unused_token_is_listed_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "tokens.css", ":root { --brand: #2563eb; --accent-2: #dc2626; }\n")
            write(tmp, "app.css", ".a { color: var(--brand); }\n")
            findings, _ = token_lint.scan([tmp])
        unused = [f for f in findings if f.rule == "UNUSED-TOKEN"]
        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].severity, "polish")
        self.assertIn("1 token has no var() reference", unused[0].message)
        self.assertIn("--accent-2", unused[0].message)


class OffScaleTests(unittest.TestCase):
    def test_radius_off_scale_and_on_scale_silent(self):
        findings = findings_for(":root { --radius-sm: 4px; --radius-lg: 10px; }\n")
        off = [f for f in findings if f.rule == "OFF-SCALE"]
        self.assertEqual(len(off), 1)
        self.assertEqual(off[0].severity, "review")
        self.assertIn("--radius-lg is 10px", off[0].message)
        self.assertIn("radius scale", off[0].message)

    def test_durations_outside_the_tiers(self):
        findings = findings_for(":root { --dur-fast: 80ms; --dur-base: 180ms; --dur-slow: 0.7s; }\n")
        off = [f for f in findings if f.rule == "OFF-SCALE"]
        self.assertEqual(len(off), 2)
        self.assertIn("80ms", off[0].message)
        self.assertIn("700ms", " ".join(f.message for f in off))

    def test_zero_duration_is_allowed(self):
        # 0 is the reduced-motion instant value (references/layout-and-motion.md).
        findings = findings_for(":root { --dur-none: 0ms; --dur-base: 300ms; }\n")
        self.assertEqual([f for f in findings if f.rule == "OFF-SCALE"], [])

    def test_shadow_blur_aggregates_across_the_set(self):
        varied = (
            ".a { box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); }\n"
            ".b { box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2); }\n"
            ".c { box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2); }\n"
            ".d { box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2); }\n"
        )
        off = [f for f in findings_for(varied, name="app.css") if f.rule == "OFF-SCALE"]
        self.assertEqual(len(off), 1)
        self.assertIn("4 distinct shadow blur values", off[0].message)
        self.assertIn("16px", off[0].message)
        tiered = (
            ".a { box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); }\n"
            ".b { box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2); }\n"
            ".c { box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2); }\n"
        )
        self.assertEqual(
            [f for f in findings_for(tiered, name="app.css") if f.rule == "OFF-SCALE"], [],
        )


class SemanticLeakTests(unittest.TestCase):
    def test_primitive_use_with_matching_semantic_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "tokens.css", (
                ":root {\n"
                "  --color-blue-6: #1a56db;\n"
                "  --space-2: 8px;\n"
                "  --color-action: #1a56db;\n"
                "  --space-gutter: 8px;\n"
                "}\n"))
            write(tmp, "app.css", (
                ".button { background: var(--color-blue-6); padding: var(--space-2); }\n"
                ".other { background: var(--color-blue-6); }\n"))
            findings, _ = token_lint.scan([tmp])
        leaks = [f for f in findings if f.rule == "SEMANTIC-LEAK"]
        self.assertEqual(len(leaks), 3)  # one per var() use, not per file
        self.assertEqual({f.severity for f in leaks}, {"review"})
        messages = " ".join(f.message for f in leaks)
        self.assertIn("use var(--color-action)", messages)
        self.assertIn("use var(--space-gutter)", messages)
        self.assertIn("primitive token --color-blue-6", messages)

    def test_aliasing_inside_token_definitions_is_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "tokens.css", (
                ":root {\n"
                "  --color-blue-6: #1a56db;\n"
                "  --color-action: var(--color-blue-6);\n"  # the mapping layer itself
                "}\n"))
            write(tmp, "app.css", ".button { background: var(--color-action); }\n")
            findings, _ = token_lint.scan([tmp])
        self.assertEqual([f for f in findings if f.rule == "SEMANTIC-LEAK"], [])

    def test_no_semantic_match_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "tokens.css", (
                ":root {\n"
                "  --color-blue-6: #1a56db;\n"
                "  --color-action: #dc2626;\n"  # different value: no suggestion
                "}\n"))
            write(tmp, "app.css", ".button { background: var(--color-blue-6); }\n")
            findings, _ = token_lint.scan([tmp])
        self.assertEqual([f for f in findings if f.rule == "SEMANTIC-LEAK"], [])

    def test_hex_shorthand_and_case_match_the_same_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "tokens.css", (
                ":root {\n"
                "  --gray-8: #FFF;\n"
                "  --color-bg: #ffffff;\n"
                "}\n"))
            write(tmp, "app.css", ".a { color: var(--gray-8); }\n")
            findings, _ = token_lint.scan([tmp])
        leaks = [f for f in findings if f.rule == "SEMANTIC-LEAK"]
        self.assertEqual(len(leaks), 1)
        self.assertIn("use var(--color-bg)", leaks[0].message)

    def test_no_primitives_at_all_is_silent(self):
        findings = findings_for(".a { background: var(--color-bg); }\n", name="app.css")
        self.assertEqual([f for f in findings if f.rule == "SEMANTIC-LEAK"], [])


class TokenLayerTests(unittest.TestCase):
    def test_naming_convention_classifies_layers(self):
        cases = {
            "--color-blue-6": "primitive",      # USWDS family+grade
            "--gray-70": "primitive",
            "--space-2": "primitive",
            "--indigo-warm-60v": "primitive",   # USWDS vivid suffix
            "--font-size-md": "primitive",      # t-shirt size step
            "--color-action": "semantic",       # role word wins
            "--text-fg": "semantic",
            "--layer-01": "semantic",           # Carbon context suffix stays semantic
            "--background-hover": "semantic",   # Carbon state variant
            "--muted": "semantic",
            "--space-gutter": "semantic",       # layout role word
            "--unknown-thing": None,
            "color.blue.6": "primitive",        # JSON dotted names classify too
            "color.action": "semantic",
        }
        for name, expected in cases.items():
            self.assertEqual(token_lint.token_layer(name), expected, name)


class JsonTokenTests(unittest.TestCase):
    def test_json_tokens_drive_contrast(self):
        data = '{\n  "color": {\n    "bg": "#ffffff",\n    "text": "#9ca3af",\n    "radius-md": "8px"\n  }\n}\n'
        findings = findings_for(data, name="theme.json")
        contrast = [f for f in findings if f.rule == "DEF-CONTRAST"]
        self.assertEqual(len(contrast), 1)
        self.assertEqual(contrast[0].severity, "important")
        self.assertIn("color.text on color.bg is 2.54:1", contrast[0].message)
        self.assertEqual([f for f in findings if f.rule == "OFF-SCALE"], [])  # 8px is on scale

    def test_invalid_json_token_file_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "theme.json", "{ not json")
            code, _ = run(token_lint.main, [tmp])
        self.assertEqual(code, 2)


class CliTests(unittest.TestCase):
    def test_json_flag_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "app.css", ".a { color: #0f172a; }\n")
            code, out = run(token_lint.main, [tmp, "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data)
        for item in data:
            self.assertEqual(
                set(item), {"rule", "severity", "file", "line", "snippet", "message"},
            )
        self.assertIn("RAW-LEAK", [item["rule"] for item in data])

    def test_exit_is_zero_even_with_findings(self):
        # No rule in token_lint is blocking, so findings never produce exit 1.
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "app.css", ".a { color: #0f172a; }\n")
            code, out = run(token_lint.main, [tmp])
        self.assertEqual(code, 0)
        self.assertIn("scanned 1 file: 0 blocking", out)
        self.assertIn("1 important", out)  # MISSING-ROLES with no token contract

    def test_unreadable_file_is_skipped_with_a_stderr_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "good.css", ".a { color: #0f172a; }\n")
            write(tmp, "locked.css", ".b { color: #111111; }\n")
            real_read = Path.read_text

            def fake_read(self, *args, **kwargs):
                if self.name == "locked.css":
                    raise OSError(13, "Permission denied")
                return real_read(self, *args, **kwargs)

            err = io.StringIO()
            with mock.patch.object(Path, "read_text", fake_read):
                with contextlib.redirect_stderr(err):
                    findings, scanned = token_lint.scan([tmp])
        self.assertEqual(scanned, 1)
        self.assertIn("RAW-LEAK", [f.rule for f in findings])
        self.assertIn("locked.css", err.getvalue())


class FixtureTests(unittest.TestCase):
    def test_tokens_fixture_reports_expected_rules(self):
        findings, scanned = token_lint.scan([str(FIXTURES / "tokens")])
        self.assertEqual(scanned, 2)

        raw = [f for f in findings if f.rule == "RAW-LEAK"]
        self.assertEqual(len(raw), 1)
        self.assertEqual(raw[0].severity, "polish")
        self.assertTrue(raw[0].file.endswith("app.css"))
        self.assertIn("3 raw hex colors", raw[0].message)
        self.assertIn("#ffffff (use var(--color-bg))", raw[0].message)
        self.assertIn("#0f172a (no token)", raw[0].message)

        contrast = [f for f in findings if f.rule == "DEF-CONTRAST"]
        self.assertEqual(
            sorted(f.severity for f in contrast),
            ["important", "important", "important", "review"],
        )

        off = [f for f in findings if f.rule == "OFF-SCALE"]
        self.assertEqual(len(off), 3)  # radius 10px, 80ms, 600ms
        self.assertIn("--radius-pill is 10px", " ".join(f.message for f in off))

        self.assertEqual([f for f in findings if f.rule == "MISSING-ROLES"], [])
        # v2 no-regression: the fixture defines a primitive (--radius-sm) used
        # in app.css, but no semantic token shares its 4px value, so no leak.
        self.assertEqual([f for f in findings if f.rule == "SEMANTIC-LEAK"], [])

        unused = [f for f in findings if f.rule == "UNUSED-TOKEN"]
        self.assertEqual(len(unused), 1)
        self.assertTrue(unused[0].message.startswith("11 tokens"))

        code, _ = run(token_lint.main, [str(FIXTURES / "tokens")])
        self.assertEqual(code, 0)  # no rule here is blocking


if __name__ == "__main__":
    unittest.main()
