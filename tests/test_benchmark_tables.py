"""Tests for tools/benchmark_tables.py and the README blocks it generates.

The 2.2.10 re-measurement updated benchmark/RESULTS.md and both READMEs kept
the old numbers for a full release — an external review named that drift as a
trust defect. These tests pin the actual repo state: if RESULTS.md changes and
the READMEs are not regenerated, the unit suite fails here, in CI's table
check, and in `tools/benchmark_tables.py --check`. That is deliberate — the
test fails until the generated views match the report, which is the only way
"every number is a script output" stays true for the headline table.
"""

import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import benchmark_tables  # noqa: E402


class ResultsParsingTests(unittest.TestCase):
    def setUp(self):
        self.three, self.generation = benchmark_tables.parse_results(
            benchmark_tables.RESULTS.read_text(encoding="utf-8"))
        self.en, self.zh = benchmark_tables.render_blocks(self.three, self.generation)

    def test_both_tables_found(self):
        self.assertGreaterEqual(len(self.three[1]), 9, "the seven-metric table lost rows")
        self.assertGreaterEqual(len(self.generation[1]), 5, "the two-generation table lost rows")

    def test_synthetic_tables_are_found_by_shape(self):
        text = "\n".join([
            "| 指标 | bare | baseline | treatment |",
            "|---|---|---|---|",
            "| 对比度 fail | 1 | 2 | 3 |",
            "",
            "| 指标 | 2.0 原始 treatment | 2.2.10 修复后 |",
            "|---|---|---|",
            "| 键盘 fail | 7 | 0 |",
        ])
        three, generation = benchmark_tables.parse_results(text)
        self.assertEqual(three[1][0], ["对比度 fail", "1", "2", "3"])
        self.assertEqual(generation[1][0], ["键盘 fail", "7", "0"])

    def test_missing_generation_table_is_a_hard_error(self):
        text = "| 指标 | bare | baseline | treatment |\n|---|---|---|---|\n| 对比度 fail | 1 | 2 | 3 |"
        with self.assertRaises(SystemExit):
            benchmark_tables.parse_results(text)


class DriftRegressionTests(unittest.TestCase):
    """The numbers that actually drifted must appear in the generated blocks."""

    def setUp(self):
        self.three, self.generation = benchmark_tables.parse_results(
            benchmark_tables.RESULTS.read_text(encoding="utf-8"))
        self.en, self.zh = benchmark_tables.render_blocks(self.three, self.generation)

    def test_the_drifted_numbers_carry_through(self):
        # 2.2.10 re-measured baseline contrast at 105 (README said 101) and
        # bare slop at 30 important (README said 54); treatment important is
        # 1 (README said 2). If these regress, both READMEs must be redone.
        for number in ("105", "30", "45", "1"):
            self.assertIn(number, self.en, f"EN block lost the re-measured {number}")
            self.assertIn(number, self.zh, f"zh block lost the re-measured {number}")

    def test_both_readme_blocks_match_the_report(self):
        for readme, block in zip(benchmark_tables.READMES, (self.en, self.zh)):
            current = benchmark_tables._current_block(readme.read_text(encoding="utf-8"))
            expected = (f"{benchmark_tables.START} tools/benchmark_tables.py --write; "
                        f"do not edit -->\n{block}\n{benchmark_tables.END}")
            self.assertEqual(current, expected,
                             f"{readme.name} drifted from RESULTS.md; run "
                             f"tools/benchmark_tables.py --write")

    def test_both_generation_tables_are_present(self):
        # The headline table shows the repaired generation; the 2.0 originals'
        # numbers belong beside it, not buried in the report. (The "48 real
        # defects" claim is prose in the README, outside the generated block.)
        for block in (self.en, self.zh):
            self.assertIn("2.0", block)
        self.assertIn("| Keyboard failures | **2** | 0 |", self.en)
        self.assertIn("| 键盘 fail | **2** | 0 |", self.zh)


class MappingTests(unittest.TestCase):
    def test_unknown_label_is_an_error_not_a_dropped_row(self):
        with self.assertRaises(SystemExit):
            benchmark_tables._mapped([("某条新指标", "1", "2", "3")],
                                     benchmark_tables.EN_LABELS, "English")

    def test_known_labels_translate(self):
        rows = benchmark_tables._mapped([("文本间距 fail（1.4.12）", "0", "8", "0")],
                                        benchmark_tables.EN_LABELS, "English")
        self.assertEqual(rows[0][0], "Text-spacing failures (1.4.12)")
        self.assertEqual(rows[0][1], ["0", "8", "0"])

    def test_bold_markers_carry_through(self):
        # Bold in RESULTS.md is the report's own emphasis; the README copies it
        # verbatim instead of re-deciding what deserves emphasis.
        rows = benchmark_tables._mapped([("文本间距 fail（1.4.12）", "**8**", "0", "0")],
                                        benchmark_tables.EN_LABELS, "English")
        self.assertEqual(rows[0][1], ["**8**", "0", "0"])


if __name__ == "__main__":
    unittest.main()
