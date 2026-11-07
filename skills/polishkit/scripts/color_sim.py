"""Color-vision-deficiency simulation for design palettes (Machado et al. 2009).

Usage:
  python color_sim.py COLOR [COLOR ...]
  python color_sim.py --check FG BG

Prints each color simulated under protanopia, deuteranopia and tritanopia
(severity 10, the full dichromacy matrices), plus --check FG BG reports the
WCAG contrast of the pair before and after simulation: if the ratio collapses,
the pair's meaning depended on a hue a deficient viewer cannot separate.

Matrices are applied in LINEAR RGB, per the model. Constants are the published
severity-10 values of Machado, Oliveira and Fernandes 2009 (see
references/sources.md); conversion helpers come from the sibling wcag module.
Read-only, standard library only, no network.
"""

import argparse
import sys

sys.dont_write_bytecode = True
import wcag  # noqa: E402  (sibling module)

# Machado et al. 2009, severity 10 (full dichromacy), linear RGB.
MATRICES = {
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritanopia": (
        (1.255528, -0.066788, -0.188740),
        (-0.076839, 0.918054, 0.158788),
        (0.004333, -0.015550, 1.011217),
    ),
}

# Convenience order and a partial-deficiency tier for palette triage.
ORDER = ("protanopia", "deuteranopia", "tritanopia")


def _to_linear(rgb):
    return tuple(wcag._to_linear(channel) for channel in rgb)


def _to_srgb(rgb):
    return tuple(wcag._to_srgb(channel) for channel in rgb)


def simulate(rgb, kind):
    """Simulate one 0..1 sRGB color under a CVD kind; returns a 0..1 sRGB tuple."""
    matrix = MATRICES[kind]
    linear = _to_linear(rgb)
    out = []
    for row in matrix:
        value = sum(coefficient * channel for coefficient, channel in zip(row, linear))
        out.append(min(max(value, 0.0), 1.0))
    return _to_srgb(tuple(out))


def _hex(rgb):
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in rgb)


def pair_report(fg, bg):
    """WCAG ratio of the pair before and after each simulation."""
    fg_rgb, bg_rgb = wcag.parse_color(fg), wcag.parse_color(bg)
    original = wcag.contrast_ratio(fg, bg)
    rows = []
    for kind in ORDER:
        simulated_fg = _hex(simulate(fg_rgb, kind))
        simulated_bg = _hex(simulate(bg_rgb, kind))
        remaining = wcag.contrast_ratio(simulated_fg, simulated_bg)
        rows.append((kind, simulated_fg, simulated_bg, remaining))
    return original, rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Simulate colors under protanopia, deuteranopia and tritanopia (Machado 2009).")
    parser.add_argument("colors", nargs="+", metavar="COLOR",
                        help="colors to simulate, or exactly FG BG with --check")
    parser.add_argument("--check", action="store_true",
                        help="treat the two colors as a text/UI pair and report its contrast before and after simulation")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        if args.check:
            if len(args.colors) != 2:
                parser.error("--check needs exactly FG BG")
            original, rows = pair_report(args.colors[0], args.colors[1])
            print(f"{args.colors[0]} on {args.colors[1]}: {original:.2f}:1 original")
            for kind, simulated_fg, simulated_bg, remaining in rows:
                verdict = "still separates" if remaining >= 3.0 else "COLLAPSES below 3:1 — meaning depended on hue"
                print(f"  {kind:<12} -> {simulated_fg} on {simulated_bg}: {remaining:.2f}:1  {verdict}")
            return 0

        parsed = [wcag.parse_color(color) for color in args.colors]
    except ValueError as exc:
        parser.error(str(exc))

    header = "color       " + "".join(f"  {kind:<9}" for kind in ORDER)
    print(header)
    for color, rgb in zip(args.colors, parsed):
        simulated = "  ".join(_hex(simulate(rgb, kind)) + "   " for kind in ORDER)
        print(f"{color:<12}{simulated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
