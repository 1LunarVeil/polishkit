"""WCAG 2.x contrast checks for #hex, rgb() and oklch() colors.

Usage: python wcag.py FG BG [FG BG ...]

Alpha channels are ignored: composite a translucent color onto its real
background before checking it. Out-of-gamut oklch values are clipped to sRGB.
"""

import argparse
import math
import re
import sys

AA_TEXT = 4.5
AA_LARGE_OR_UI = 3.0
AAA_TEXT = 7.0

_HEX = re.compile(r"#([0-9a-f]{3}|[0-9a-f]{6})")
_RGB = re.compile(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)")
_OKLCH = re.compile(
    r"oklch\(\s*([\d.]+%?)\s+([\d.]+)\s+([\d.]+)(?:deg)?(?:\s*/\s*[\d.]+%?)?\s*\)"
)


def _to_linear(channel):
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _to_srgb(channel):
    channel = min(max(channel, 0.0), 1.0)
    if channel <= 0.0031308:
        return 12.92 * channel
    return 1.055 * channel ** (1 / 2.4) - 0.055


def parse_color(value):
    """Return (r, g, b) with each channel in 0..1."""
    text = value.strip().lower()
    match = _HEX.fullmatch(text)
    if match:
        digits = match.group(1)
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
        return tuple(int(digits[i:i + 2], 16) / 255 for i in (0, 2, 4))

    match = _RGB.match(text)
    if match:
        return tuple(min(max(float(part) / 255, 0.0), 1.0) for part in match.groups())

    match = _OKLCH.fullmatch(text)
    if match:
        lightness_text, chroma_text, hue_text = match.groups()
        if lightness_text.endswith("%"):
            lightness = float(lightness_text[:-1]) / 100
        else:
            lightness = float(lightness_text)
        chroma = float(chroma_text)
        hue = math.radians(float(hue_text))
        a = chroma * math.cos(hue)
        b = chroma * math.sin(hue)
        l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
        m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
        s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
        red = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
        green = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
        blue = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
        return tuple(_to_srgb(channel) for channel in (red, green, blue))

    raise ValueError(f"unsupported color {value!r}; use #hex, rgb() or oklch()")


def relative_luminance(rgb):
    red, green, blue = (_to_linear(channel) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(fg, bg):
    lighter, darker = sorted(
        (relative_luminance(parse_color(fg)), relative_luminance(parse_color(bg))),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


# APCA 0.0.98G-4g, supplementary and draft. Constants verified verbatim against
# Myndex/apca-w3 src/apca-w3.js (W3-licensed); the WCAG ratios above remain the
# normative check this plugin gates on. Lc is signed: positive means dark text
# on a light background, negative means light text on a dark background.
_APCA = {
    "mainTRC": 2.4,
    "sRco": 0.2126729,
    "sGco": 0.7151522,
    "sBco": 0.0721750,
    "normBG": 0.56,
    "normTXT": 0.57,
    "revTXT": 0.62,
    "revBG": 0.65,
    "blkThrs": 0.022,
    "blkClmp": 1.414,
    "scale": 1.14,
    "loOffset": 0.027,
    "deltaYmin": 0.0005,
    "loClip": 0.1,
}

# Published APCA Lc guidance levels (draft); see references/sources.md.
_APCA_LEVELS = (
    (90, "fluent body preferred"),
    (75, "body minimum"),
    (60, "large/bold minimum"),
    (45, "headline minimum"),
    (30, "very large or disabled minimum"),
    (15, "non-text/spot minimum"),
)


def _apca_y(rgb):
    """APCA screen luminance: D65 weights over a pure 2.4 exponent (no linear segment)."""
    return (
        _APCA["sRco"] * rgb[0] ** _APCA["mainTRC"]
        + _APCA["sGco"] * rgb[1] ** _APCA["mainTRC"]
        + _APCA["sBco"] * rgb[2] ** _APCA["mainTRC"]
    )


def _apca_soft_clamp(y):
    if y > _APCA["blkThrs"]:
        return y
    return y + (_APCA["blkThrs"] - y) ** _APCA["blkClmp"]


def apca_lc(fg, bg):
    """Signed APCA Lc for text color fg on background bg (both 0..1 tuples)."""
    txt_y = _apca_soft_clamp(_apca_y(fg))
    bg_y = _apca_soft_clamp(_apca_y(bg))
    if not (0.0 <= txt_y <= 1.1 and 0.0 <= bg_y <= 1.1):
        return 0.0
    if abs(bg_y - txt_y) < _APCA["deltaYmin"]:
        return 0.0
    if bg_y > txt_y:  # dark text on a lighter background
        sapc = (bg_y ** _APCA["normBG"] - txt_y ** _APCA["normTXT"]) * _APCA["scale"]
        if sapc < _APCA["loClip"]:
            return 0.0
        return (sapc - _APCA["loOffset"]) * 100.0
    sapc = (bg_y ** _APCA["revBG"] - txt_y ** _APCA["revTXT"]) * _APCA["scale"]
    if sapc > -_APCA["loClip"]:
        return 0.0
    return (sapc + _APCA["loOffset"]) * 100.0


def apca_contrast(fg, bg):
    """Signed APCA Lc for color strings; see apca_lc for the sign convention."""
    return apca_lc(parse_color(fg), parse_color(bg))


def _apca_level(lc):
    magnitude = abs(lc)
    for threshold, label in _APCA_LEVELS:
        if magnitude >= threshold:
            return label
    return "fails even spot text"


def _verdict(ratio, threshold):
    return "pass" if ratio >= threshold else "FAIL"


def main(argv=None):
    parser = argparse.ArgumentParser(description="WCAG contrast check for FG BG color pairs.")
    parser.add_argument("colors", nargs="+", metavar="COLOR", help="FG BG pairs, e.g. '#1f2937' '#ffffff'")
    parser.add_argument("--apca", action="store_true",
                        help="also report the draft APCA Lc value (supplementary, not a gate)")
    args = parser.parse_args(argv)
    if len(args.colors) % 2:
        parser.error("colors must come in FG BG pairs")

    pairs = list(zip(args.colors[::2], args.colors[1::2]))
    try:
        ratios = [contrast_ratio(fg, bg) for fg, bg in pairs]
        lc_values = [apca_contrast(fg, bg) for fg, bg in pairs] if args.apca else None
    except ValueError as exc:
        parser.error(str(exc))

    sys.stdout.reconfigure(encoding="utf-8")
    for index, ((fg, bg), ratio) in enumerate(zip(pairs, ratios)):
        line = (
            f"{fg} on {bg}: {ratio:.2f}:1  "
            f"text AA {_verdict(ratio, AA_TEXT)}  "
            f"large text / UI AA {_verdict(ratio, AA_LARGE_OR_UI)}  "
            f"text AAA {_verdict(ratio, AAA_TEXT)}"
        )
        if lc_values is not None:
            lc = lc_values[index]
            line += f"  APCA Lc {lc:+.1f} (draft; {_apca_level(lc)})"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
