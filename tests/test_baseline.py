"""Tests for image_diff.py baseline directory mode.

Fixtures are written through make_fixtures.write_png (64x40, filter 0), so no
binary blobs ship; the size-mismatch file is assembled inline like the PNG
tests in test_design_tools.py.
"""

import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.dont_write_bytecode = True

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "skills" / "polishkit" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import image_diff  # noqa: E402
import make_fixtures  # noqa: E402


def run(main, argv):
    import io
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


def flat_rows():
    return [bytearray((246, 247, 249) * 64) for _ in range(40)]


def box_rows():
    rows = flat_rows()
    for y in range(8, 24):
        rows[y][10 * 3:40 * 3] = bytes((37, 99, 235)) * 30
    return rows


def small_png(path):
    raw = bytearray()
    for _ in range(20):
        raw += b"\x00" + bytes((246, 247, 249)) * 32
    header = struct.pack(">IIBBBBB", 32, 20, 8, 2, 0, 0, 0)
    compressed = zlib.compress(bytes(raw), 9)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(header)) + b"IHDR" + header
        + struct.pack(">I", zlib.crc32(b"IHDR" + header) & 0xFFFFFFFF)
        + struct.pack(">I", len(compressed)) + b"IDAT" + compressed
        + struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
        + struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    )


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.baseline = self.root / "baseline"
        self.current = self.root / "current"
        self.baseline.mkdir()
        self.current.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_identical_changed_and_missing_statuses(self):
        make_fixtures.write_png(self.baseline / "same.png", flat_rows())
        make_fixtures.write_png(self.current / "same.png", flat_rows())
        make_fixtures.write_png(self.baseline / "moved.png", flat_rows())
        make_fixtures.write_png(self.current / "moved.png", box_rows())
        make_fixtures.write_png(self.baseline / "gone.png", flat_rows())
        make_fixtures.write_png(self.current / "new.png", flat_rows())
        result = image_diff.baseline_report(self.baseline, self.current)
        statuses = {pair["name"]: pair["status"] for pair in result["pairs"]}
        self.assertEqual(statuses, {
            "gone.png": "missing_current",
            "moved.png": "changed",
            "new.png": "missing_baseline",
            "same.png": "identical",
        })
        self.assertEqual(result["summary"]["changed"], 1)
        self.assertEqual(result["summary"]["identical"], 1)

    def test_changed_pair_carries_the_bounding_box(self):
        make_fixtures.write_png(self.baseline / "moved.png", flat_rows())
        make_fixtures.write_png(self.current / "moved.png", box_rows())
        result = image_diff.baseline_report(self.baseline, self.current)
        pair = result["pairs"][0]
        self.assertEqual(pair["status"], "changed")
        self.assertEqual(pair["changed_pixels"], 30 * 16)
        self.assertEqual(pair["bounding_box"], {"x": 10, "y": 8, "width": 30, "height": 16})

    def test_size_mismatch_is_one_errored_pair_not_a_crash(self):
        make_fixtures.write_png(self.baseline / "small.png", flat_rows())
        small_png(self.current / "small.png")
        result = image_diff.baseline_report(self.baseline, self.current)
        self.assertEqual(result["pairs"][0]["status"], "not_comparable")
        self.assertIn("size mismatch", result["pairs"][0]["reason"])
        self.assertEqual(result["summary"]["not_comparable"], 1)

    def test_non_png_entries_are_ignored(self):
        (self.baseline / "notes.txt").write_text("not an image", encoding="utf-8")
        make_fixtures.write_png(self.baseline / "same.png", flat_rows())
        make_fixtures.write_png(self.current / "same.png", flat_rows())
        result = image_diff.baseline_report(self.baseline, self.current)
        self.assertEqual([pair["name"] for pair in result["pairs"]], ["same.png"])

    def test_cli_requires_two_directories(self):
        make_fixtures.write_png(self.baseline / "same.png", flat_rows())
        code, _ = run(image_diff.main, [str(self.baseline)])
        self.assertEqual(code, 2)

    def test_cli_json_and_text_shapes(self):
        make_fixtures.write_png(self.baseline / "moved.png", flat_rows())
        make_fixtures.write_png(self.current / "moved.png", box_rows())
        code, out = run(image_diff.main, [str(self.baseline), str(self.current), "--json"])
        self.assertEqual(code, 0)
        self.assertIn('"mode": "baseline"', out)
        self.assertIn('"changed_pixels": 480', out)
        code, out = run(image_diff.main, [str(self.baseline), str(self.current)])
        self.assertEqual(code, 0)
        self.assertIn("changed 480 px", out)
        self.assertIn("review aid, not a gate", out)


if __name__ == "__main__":
    unittest.main()
