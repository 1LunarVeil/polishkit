"""Decode PNGs and compare screenshots with the standard library only.

Usage:
  python image_diff.py A.png B.png [--json] [--threshold N]
  python image_diff.py A.png --stats [--json]
  python image_diff.py BASELINE_DIR CURRENT_DIR [--json]

Baseline mode: with two directories, every PNG in CURRENT_DIR is compared
against the same-named file in BASELINE_DIR; files present on only one side
and files that cannot be decoded are reported per pair instead of aborting.

Why hand-rolled: Pillow is not available on every machine, and installing a
dependency to answer "did this frame change" is not worth it. PNG is a zlib
stream of filtered scanlines, so decoding RGBA/RGB 8-bit non-interlaced files
takes about a hundred lines. Anything else is reported as unsupported rather
than guessed at.

A pixel diff is a review aid, not a CI gate: a deliberate redesign must be
allowed to change every pixel, so the exit status reflects only whether the
files could be compared, never how different they are.
"""

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
# A screenshot is far below these; the limits exist so a malformed or hostile
# file cannot make the decoder allocate an unbounded amount of memory.
MAX_PIXELS = 40_000_000
MAX_RAW_BYTES = 160_000_000


class Unsupported(Exception):
    pass


def _chunks(data):
    position = 8
    while position < len(data):
        length, kind = struct.unpack(">I4s", data[position:position + 8])
        body = data[position + 8:position + 8 + length]
        yield kind, body
        position += 12 + length


def _paeth(a, b, c):
    estimate = a + b - c
    dist_a, dist_b, dist_c = abs(estimate - a), abs(estimate - b), abs(estimate - c)
    if dist_a <= dist_b and dist_a <= dist_c:
        return a
    return b if dist_b <= dist_c else c


def decode_png(path):
    """Return (width, height, pixels) with pixels as bytes of 3 channels or 4."""
    data = Path(path).read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise Unsupported("not a PNG")
    width = height = depth = color_type = interlace = None
    idat = bytearray()
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            width, height, depth, color_type, _comp, _filter, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    if depth != 8:
        raise Unsupported(f"bit depth {depth} is unsupported (only 8-bit)")
    if interlace:
        raise Unsupported("interlaced PNG is unsupported")
    if color_type not in (0, 2, 4, 6):
        raise Unsupported(f"color type {color_type} is unsupported (indexed or greyscale-alpha)")

    channels = CHANNELS[color_type]
    stride = width * channels
    expected = (stride + 1) * height
    if width * height > MAX_PIXELS:
        raise Unsupported(
            f"{width}x{height} exceeds the {MAX_PIXELS}-pixel limit"
        )
    if expected > MAX_RAW_BYTES:
        raise Unsupported(
            f"scanline data would be {expected} bytes, above the {MAX_RAW_BYTES}-byte limit"
        )
    # Bound the output while inflating. Checking the length afterwards is too
    # late: a 65 KB file here expanded to 64 MB before any check could run.
    inflater = zlib.decompressobj()
    raw = inflater.decompress(bytes(idat), expected)
    if inflater.unconsumed_tail or not inflater.eof:
        raise Unsupported("image data larger than the declared dimensions (decompression bomb)")
    if len(raw) < expected:
        raise Unsupported("truncated image data")

    previous = bytearray(stride)
    rows = []
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        line = bytearray(raw[offset:offset + stride])
        offset += stride
        if filter_type == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                upper_left = previous[i - channels] if i >= channels else 0
                line[i] = (line[i] + _paeth(left, previous[i], upper_left)) & 0xFF
        elif filter_type != 0:
            raise Unsupported(f"unknown filter type {filter_type}")
        rows.append(bytes(line))
        previous = line

    pixels = bytearray()
    for line in rows:
        if color_type == 2:
            pixels += line
        elif color_type == 6:
            pixels += line
        elif color_type == 0:
            for value in line:
                pixels += bytes((value, value, value, 255))
        else:  # 4: greyscale + alpha
            for i in range(0, len(line), 2):
                value, alpha = line[i], line[i + 1]
                pixels += bytes((value, value, value, alpha))
    return width, height, bytes(pixels)


def _channel_count(pixels, width, height):
    total = width * height
    return 4 if len(pixels) == total * 4 else 3


def stats(path):
    """Summarise an image: does it look like a rendered page or a blank shell?"""
    width, height, pixels = decode_png(path)
    channels = _channel_count(pixels, width, height)
    step = max(1, (width * height) // 200000)
    colors = set()
    non_background = 0
    sampled = 0
    background = pixels[0:channels]
    minimum = [255] * channels
    maximum = [0] * channels
    for index in range(0, width * height, step):
        base = index * channels
        pixel = pixels[base:base + channels]
        sampled += 1
        colors.add(pixel)
        if pixel != background:
            non_background += 1
        for channel in range(channels):
            minimum[channel] = min(minimum[channel], pixel[channel])
            maximum[channel] = max(maximum[channel], pixel[channel])
    return {
        "file": str(path),
        "width": width,
        "height": height,
        "sampled_pixels": sampled,
        "distinct_colors_sampled": len(colors),
        # A blank or nearly blank frame has very few colours and almost no
        # pixels that differ from the top-left background.
        "non_background_ratio": round(non_background / sampled, 4) if sampled else 0.0,
        "channel_range": [(maximum[i] - minimum[i]) for i in range(channels)],
    }


def diff(first, second):
    width_a, height_a, pixels_a = decode_png(first)
    width_b, height_b, pixels_b = decode_png(second)
    if (width_a, height_a) != (width_b, height_b):
        return {
            "comparable": False,
            "reason": f"size mismatch {width_a}x{height_a} vs {width_b}x{height_b}",
        }
    channels_a = _channel_count(pixels_a, width_a, height_a)
    channels_b = _channel_count(pixels_b, width_b, height_b)
    if channels_a != channels_b:
        return {"comparable": False, "reason": "channel count differs"}

    total = width_a * height_a
    changed = 0
    min_x, min_y = width_a, height_a
    max_x = max_y = -1
    for index in range(total):
        base = index * channels_a
        if pixels_a[base:base + 3] != pixels_b[base:base + 3]:
            changed += 1
            x, y = index % width_a, index // width_a
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
    return {
        "comparable": True,
        "width": width_a,
        "height": height_a,
        "changed_pixels": changed,
        "changed_ratio": round(changed / total, 4),
        "bounding_box": None if changed == 0 else {
            "x": min_x, "y": min_y,
            "width": max_x - min_x + 1, "height": max_y - min_y + 1,
        },
        "identical": changed == 0,
    }


def baseline_report(baseline_dir, current_dir):
    """Compare every PNG in current_dir against the same-named file in baseline_dir.

    One unreadable or undecodable file becomes one errored pair; the rest of
    the directory still reports. Never a gate: the summary counts changes,
    it does not fail on them.
    """
    baseline = {p.name: p for p in sorted(Path(baseline_dir).glob("*.png"))}
    current = {p.name: p for p in sorted(Path(current_dir).glob("*.png"))}
    pairs = []
    summary = {"identical": 0, "changed": 0, "not_comparable": 0,
               "error": 0, "missing_baseline": 0, "missing_current": 0}
    for name in sorted(set(baseline) | set(current)):
        base, curr = baseline.get(name), current.get(name)
        if curr is None:
            pairs.append({"name": name, "status": "missing_current"})
            summary["missing_current"] += 1
            continue
        if base is None:
            pairs.append({"name": name, "status": "missing_baseline"})
            summary["missing_baseline"] += 1
            continue
        try:
            result = diff(base, curr)
        except (Unsupported, OSError, zlib.error) as exc:
            pairs.append({"name": name, "status": "error", "reason": str(exc)})
            summary["error"] += 1
            continue
        if not result.get("comparable"):
            pairs.append({"name": name, "status": "not_comparable", "reason": result.get("reason")})
            summary["not_comparable"] += 1
        elif result["identical"]:
            pairs.append({"name": name, "status": "identical"})
            summary["identical"] += 1
        else:
            pairs.append({
                "name": name, "status": "changed",
                "changed_pixels": result["changed_pixels"],
                "changed_ratio": result["changed_ratio"],
                "bounding_box": result["bounding_box"],
            })
            summary["changed"] += 1
    return {
        "mode": "baseline", "baseline": str(baseline_dir), "current": str(current_dir),
        "pairs": pairs, "summary": summary,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="PNG stats and diff with no dependencies.")
    parser.add_argument("first")
    parser.add_argument("second", nargs="?")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    first_is_dir = Path(args.first).is_dir()
    second_is_dir = bool(args.second) and Path(args.second).is_dir()
    if first_is_dir or second_is_dir:
        if not (first_is_dir and second_is_dir):
            parser.error("baseline mode needs two directories: BASELINE_DIR CURRENT_DIR")
        result = baseline_report(args.first, args.second)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        for pair in result["pairs"]:
            if pair["status"] == "changed":
                box = pair["bounding_box"]
                print(f"{pair['name']}: changed {pair['changed_pixels']} px "
                      f"({pair['changed_ratio']:.2%}), "
                      f"region x={box['x']} y={box['y']} {box['width']}x{box['height']}")
            elif pair["status"] == "not_comparable":
                print(f"{pair['name']}: not comparable: {pair['reason']}")
            elif pair["status"] == "error":
                print(f"{pair['name']}: error: {pair['reason']}")
            else:
                print(f"{pair['name']}: {pair['status']}")
        summary = result["summary"]
        print(f"pairs: {summary['identical']} identical, {summary['changed']} changed, "
              f"{summary['not_comparable']} not comparable, {summary['error']} error, "
              f"{summary['missing_baseline']} only in baseline, "
              f"{summary['missing_current']} only in current")
        print("review aid, not a gate: a changed pair proves change, not improvement")
        return 0

    try:
        if args.stats or not args.second:
            result = {"stats": [stats(args.first)]}
            if args.second:
                result["stats"].append(stats(args.second))
        else:
            result = {"diff": diff(args.first, args.second),
                      "before": stats(args.first), "after": stats(args.second)}
    except (Unsupported, OSError, zlib.error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    for item in result.get("stats", []):
        print(f"{item['file']}: {item['width']}x{item['height']} "
              f"colours={item['distinct_colors_sampled']} "
              f"non-background={item['non_background_ratio']:.1%}")
    if "diff" in result:
        found = result["diff"]
        if not found.get("comparable"):
            print(f"not comparable: {found['reason']}")
        elif found["identical"]:
            print("identical: no pixel changed")
        else:
            box = found["bounding_box"]
            print(f"changed {found['changed_pixels']} px ({found['changed_ratio']:.2%}), "
                  f"region x={box['x']} y={box['y']} {box['width']}x{box['height']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
