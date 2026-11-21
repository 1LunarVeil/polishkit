"""Tests for tools/benchmark_tables.py and the README blocks it generates.

The 2.2.10 re-measurement updated benchmark/RESULTS.md and both READMEs kept
the old numbers for a full release — an external review named that drift as a
trust defect. These tests pin the actual repo state: if RESULTS.md changes and
the READMEs are not regenerated, the unit suite fails here, in CI's table
check, and in `tools/benchmark_tables.py --check`. That is deliberate — the
test fails until the generated views match the report, which is the only way
"every number is a script output" stays true for the headline table.
"""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import benchmark_tables  # noqa: E402


def _quiet(call):
    """Run a tool main() with its report output captured, not printed."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        return call()


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


class IdempotenceTests(unittest.TestCase):
    """The 2.2.12 generator accumulated one end marker per --write run while
    --check stayed green: the block carries its own end marker and the splice
    kept the old one too. These tests pin the splice and the shipped state."""

    def _scaffold(self, tmp):
        results = tmp / "RESULTS.md"
        results.write_text(benchmark_tables.RESULTS.read_text(encoding="utf-8"),
                           encoding="utf-8")
        readmes = []
        for name in ("README.md", "README.zh-CN.md"):
            target = tmp / name
            target.write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
            readmes.append(target)
        return results, tuple(readmes)

    def test_replacing_twice_is_byte_identical(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        start = text.find(benchmark_tables.START)
        end = text.find(benchmark_tables.END) + len(benchmark_tables.END)
        block = text[start:end]
        filler_before, filler_after = text[:start], text[end:]

        once = benchmark_tables._replace_block(filler_before + benchmark_tables.START
                                               + "\n<!-- benchmark:generated:end -->\n"
                                               + filler_after, block)
        twice = benchmark_tables._replace_block(once, block)
        self.assertEqual(once, twice, "a second --write run must change nothing")
        self.assertEqual(once.count(benchmark_tables.END), 1)

    def test_shipped_readmes_carry_exactly_one_marker_of_each_kind(self):
        for readme in benchmark_tables.READMES:
            text = readme.read_text(encoding="utf-8")
            self.assertEqual(text.count(benchmark_tables.START), 1, str(readme))
            self.assertEqual(text.count(benchmark_tables.END), 1,
                             f"{readme}: a stray end marker means a --write run "
                             f"failed to consume the one it replaced")

    def test_write_through_main_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            results, readmes = self._scaffold(tmp_path)
            with mock.patch.object(benchmark_tables, "RESULTS", results), \
                 mock.patch.object(benchmark_tables, "READMES", readmes):
                self.assertEqual(_quiet(lambda: benchmark_tables.main(["--write"])), 0)
                first = [readme.read_bytes() for readme in readmes]
                self.assertEqual(_quiet(lambda: benchmark_tables.main(["--write"])), 0)
                self.assertEqual([readme.read_bytes() for readme in readmes], first,
                                 "the second --write must be byte-identical to the first")
                self.assertEqual(_quiet(lambda: benchmark_tables.main(["--check"])), 0)


class CheckMustBeAbleToFailTests(unittest.TestCase):
    """A gate that has never been seen failing is not a gate. These tests
    tamper with the inputs and demand exit 1 — the same burden CI already
    puts on the scanner's planted-defect fixture."""

    def _scaffold(self, tmp):
        results = tmp / "RESULTS.md"
        results.write_text(benchmark_tables.RESULTS.read_text(encoding="utf-8"),
                           encoding="utf-8")
        readmes = []
        for name in ("README.md", "README.zh-CN.md"):
            target = tmp / name
            target.write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
            readmes.append(target)
        return results, tuple(readmes)

    def test_check_fails_when_a_block_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            results, readmes = self._scaffold(tmp_path)
            # Reintroduce the drift this tool exists to catch, inside the
            # generated block: 105 -> 101.
            row = "| Rendered-page contrast failures (WCAG 1.4.3) | **48** | 105 | **0** |"
            readme_text = readmes[0].read_text(encoding="utf-8")
            self.assertIn(row, readme_text)
            readmes[0].write_text(readme_text.replace(row, row.replace("105", "101"), 1),
                                  encoding="utf-8")
            with mock.patch.object(benchmark_tables, "RESULTS", results), \
                 mock.patch.object(benchmark_tables, "READMES", readmes):
                self.assertEqual(_quiet(lambda: benchmark_tables.main(["--check"])), 1,
                                 "--check passed on a tampered block")

    def test_check_fails_on_a_doubled_end_marker(self):
        # The exact 2.2.12 defect: --write left its own end marker next to the
        # old one, and the check, which sliced to the first end marker, could
        # not see it. The marker count is now part of the gate.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            results, readmes = self._scaffold(tmp_path)
            doubled = readmes[0].read_text(encoding="utf-8").replace(
                benchmark_tables.END, benchmark_tables.END + benchmark_tables.END, 1)
            readmes[0].write_text(doubled, encoding="utf-8")
            with mock.patch.object(benchmark_tables, "RESULTS", results), \
                 mock.patch.object(benchmark_tables, "READMES", readmes):
                self.assertEqual(_quiet(lambda: benchmark_tables.main(["--check"])), 1,
                                 "--check passed with a stacked end marker")

    def test_check_fails_when_results_gains_an_unmapped_row(self):
        # RESULTS.md growing a metric the mapping does not know must be an
        # error, never a silently dropped row.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            results, readmes = self._scaffold(tmp_path)
            # Grow the report table itself, the way 2.2.10 did: an unmapped
            # metric must be an error, never a silently dropped row.
            anchor = "| slop_scan important 发现 | 30 | 45 | **1** |"
            results_text = results.read_text(encoding="utf-8")
            self.assertIn(anchor, results_text)
            results.write_text(results_text.replace(
                anchor, anchor + "\n| 新指标（9.9.9） | 1 | 2 | 3 |", 1), encoding="utf-8")
            with mock.patch.object(benchmark_tables, "RESULTS", results), \
                 mock.patch.object(benchmark_tables, "READMES", readmes):
                with self.assertRaises(SystemExit):
                    benchmark_tables.main(["--check"])


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
