"""Render the README benchmark tables from benchmark/RESULTS.md.

Why this exists: the 2.2.10 re-measurement updated RESULTS.md (baseline
contrast failures 101 -> 105, bare slop 54 -> 30 important, treatment 2 -> 1)
and both READMEs kept the old numbers for a full release. An external review
called that out by name: a project whose selling point is "every number is a
script output" had a headline table that no script had written. So now one is
written by one.

The README tables are generated views of RESULTS.md's two tables — the
three-condition comparison and the two-generation treatment measurement. The
generated block sits between markers in each README; this script writes it
(--write) or verifies it (--check, exit 1 on drift). CI runs the check, so
editing RESULTS.md without regenerating the READMEs fails the build instead
of silently publishing stale numbers.

Metric labels are mapped zh -> en by a fixed dictionary. A label RESULTS.md
gains that the dictionary does not know is an error, not a dropped row —
the mapping must grow with the report, never silently behind it.

Usage:
  python tools/benchmark_tables.py --write   # regenerate the README blocks
  python tools/benchmark_tables.py --check   # verify the blocks match RESULTS.md
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmark" / "RESULTS.md"
READMES = (ROOT / "README.md", ROOT / "README.zh-CN.md")

START = "<!-- benchmark:generated:start"
END = "<!-- benchmark:generated:end -->"

EN_LABELS = {
    "渲染页对比度 fail（WCAG 1.4.3）": "Rendered-page contrast failures (WCAG 1.4.3)",
    "对比度 uncertain（渐变/图像/遮挡，不可测）": "Contrast uncertain (gradients/images/occlusion, unmeasurable)",
    "靶标尺寸 fail（2.5.8）": "Target-size failures (2.5.8)",
    "无可访问名称元素（4.1.2）": "Elements without an accessible name (4.1.2)",
    "键盘可达性 / 焦点 fail（2.1.1 / 2.4.7 / 1.4.11 / 2.4.11）":
        "Keyboard / focus failures (2.1.1 / 2.4.7 / 1.4.11 / 2.4.11)",
    "文本间距 fail（1.4.12）": "Text-spacing failures (1.4.12)",
    "回流 fail（1.4.10，320 CSS px）": "Reflow failures (1.4.10, 320 CSS px)",
    "CJK 断行 fail（clreq §6.1.1）": "CJK line-breaking failures (clreq §6.1.1)",
    "slop_scan important 发现": "slop_scan important findings",
}
# The two-generation table's labels are short forms of the same metrics.
EN_GENERATION_LABELS = {
    "对比度 fail": "Contrast failures",
    "键盘 fail": "Keyboard failures",
    "文本间距 fail": "Text-spacing failures",
    "回流 fail": "Reflow failures",
    "CJK 断行 fail": "CJK line-breaking failures",
}
EN_CONDITION_HEADERS = ("Metric", "bare", "frontend-design", "+ PolishKit")
EN_GENERATION_HEADERS = ("Metric", "2.0 originals", "after repair")


def _tables(lines):
    """Split markdown source into tables: lists of stripped pipe rows."""
    tables, current = [], []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current.append(stripped)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _cells(row):
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _is_separator(cells):
    return all(set(cell) <= {"-", ":"} and cell for cell in cells)


def _rows(cells_by_row, columns):
    """Header + data rows of a table, minus the pipe separator row."""
    header = _cells(cells_by_row[0])
    if len(header) != columns or header[0] != "指标":
        return None
    rows = []
    for row in cells_by_row[1:]:
        cells = _cells(row)
        if _is_separator(cells):
            continue
        if len(cells) != columns:
            raise SystemExit(f"benchmark_tables: row has {len(cells)} cells, "
                             f"expected {columns}: {row!r}")
        rows.append(cells)
    return header, rows


def parse_results(text):
    """Return (three_condition, two_generation) tables from RESULTS.md.

    Identified by shape, not by position: the three-condition table has four
    columns headed 指标, the generation table three. Either one missing is a
    hard error — a RESULTS.md that lost a table is not something the README
    should keep quiet about.
    """
    three, generation = None, None
    for table in _tables(text.splitlines()):
        parsed = _rows(table, 4)
        if parsed and "bare" in parsed[0][1]:
            three = parsed
            continue
        parsed = _rows(table, 3)
        if parsed and "2.0" in parsed[0][1]:
            generation = parsed
    if three is None:
        raise SystemExit("benchmark_tables: no three-condition table "
                         "(4 columns, bare/baseline/treatment) in RESULTS.md")
    if generation is None:
        raise SystemExit("benchmark_tables: no two-generation treatment table "
                         "(3 columns) in RESULTS.md")
    return three, generation


def _mapped(labels, mapping, source):
    """Translate one table's labels, refusing to drop any row."""
    out = []
    for label, *values in labels:
        key = label.strip("*").strip()
        if key not in mapping:
            raise SystemExit(f"benchmark_tables: metric label {key!r} has no "
                             f"{source} translation; add it to the mapping in "
                             f"tools/benchmark_tables.py instead of dropping it")
        out.append((mapping[key], values))
    return out


def render_blocks(three, generation):
    """The markdown the two READMEs carry between the markers."""
    (three_header, three_rows), (gen_header, gen_rows) = three, generation
    en = ["| " + " | ".join(EN_CONDITION_HEADERS) + " |", "|---|---|---|---|"]
    for label, values in _mapped(three_rows, EN_LABELS, "English"):
        en.append(f"| {label} | " + " | ".join(values) + " |")
    en += ["", "| " + " | ".join(EN_GENERATION_HEADERS) + " |", "|---|---|---|"]
    for label, values in _mapped(gen_rows, EN_GENERATION_LABELS, "English"):
        en.append(f"| {label} | " + " | ".join(values) + " |")

    # The zh README keeps RESULTS.md's own labels and the generation table's
    # headers verbatim — no translation, so no translation can drift.
    zh = ["| 指标 | bare | frontend-design | + PolishKit |", "|---|---|---|---|"]
    for label, *values in three_rows:
        zh.append(f"| {label} | " + " | ".join(values) + " |")
    zh += ["", "| 指标 | " + " | ".join(gen_header[1:]) + " |", "|---|---|---|"]
    for label, *values in gen_rows:
        zh.append(f"| {label} | " + " | ".join(values) + " |")
    return "\n".join(en), "\n".join(zh)


def _replace_block(text, block):
    start = text.find(START)
    end = text.find(END)
    if start == -1 or end == -1 or end < start:
        raise SystemExit(f"benchmark_tables: markers not found — wrap the "
                         f"generated tables in {START} ... {END}")
    # The block carries its own end marker, so the splice must consume the one
    # it replaces. Returning text[end:] kept the old marker and every --write
    # run accumulated one more — while --check, which slices to the first end
    # marker, stayed green. The drift gate was blind to the only drift its own
    # tool manufactured, and 2.2.12 shipped with the duplicate already in it.
    return text[:start] + block + text[end + len(END):]


def _current_block(text):
    start = text.find(START)
    end = text.find(END)
    if start == -1 or end == -1 or end < start:
        raise SystemExit(f"benchmark_tables: markers not found — wrap the "
                         f"generated tables in {START} ... {END}")
    # Include the end marker itself: the written block carries it, so the
    # comparison must too, or --check fails on a line that is actually there.
    return text[start:end + len(END)]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate or verify the README benchmark tables from RESULTS.md.")
    parser.add_argument("--write", action="store_true", help="rewrite the README blocks")
    parser.add_argument("--check", action="store_true", help="verify the README blocks; exit 1 on drift")
    args = parser.parse_args(argv)

    three, generation = parse_results(RESULTS.read_text(encoding="utf-8"))
    en_block, zh_block = render_blocks(three, generation)
    blocks = {}
    for readme, block in zip(READMES, (en_block, zh_block)):
        blocks[readme] = (f"{START} tools/benchmark_tables.py --write; do not edit -->\n"
                          f"{block}\n{END}")

    if args.check:
        drifted = []
        for readme, block in blocks.items():
            text = readme.read_text(encoding="utf-8")
            # Count the markers, not just the first span: a second --write bug
            # of the 2.2.12 kind would stack end markers invisibly past the
            # slice below, and a gate that cannot see its own tool's drift is
            # worse than no gate.
            starts, ends = text.count(START), text.count(END)
            if starts != 1 or ends != 1:
                drifted.append(f"{readme.name}: {starts} start / {ends} end "
                               f"markers (expected exactly 1 of each)")
                continue
            if _current_block(text) != block:
                drifted.append(readme.name)
        if drifted:
            for problem in drifted:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        print("README benchmark tables match benchmark/RESULTS.md")
        return 0

    for readme, block in blocks.items():
        updated = _replace_block(readme.read_text(encoding="utf-8"), block)
        # Path.write_text gained newline= in 3.10; the suite's floor is 3.9.
        with readme.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(updated)
        print(f"  wrote {readme.name}")
    print("README benchmark tables regenerated from benchmark/RESULTS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
