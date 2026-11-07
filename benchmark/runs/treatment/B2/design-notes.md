# B2 — Landscape photographer portfolio (treatment-v3)

## Brief

Portfolio site for a landscape photographer — image-forward, quiet, lets the work breathe.
Single self-contained index.html: inline CSS/JS, system fonts only (Georgia serif stand-in +
Segoe UI for small UI and the light-weight numeral end), no external requests.

**Concrete subject:** Maren Holt, working the North Atlantic coast (Shetland/Faroes) in long
exposures — sea fog, basalt, slack tide. v2's subject and palette carried forward; v3's mandate
is expression: the page must not be "correct but inert".

**Three refusals:**
1. No neutral white-wall gallery — the page smells of the coast (v2 palette kept as floor).
2. No placeholder rectangles for photographs — with no image assets the photographs are painted
   (layered gradients, clip-path terrain, turbulence grain).
3. No failure theatre in the first paint — the default view is the full working grid; error,
   empty and sold-out states live behind real controls.

## Direction

**Direction 2 (warm editorial), cooled to the coast** — long-form captions and paper ground are
what "lets the work breathe" means typographically; v3 keeps the direction and pushes the
expression layer on top. `design_lookup.py "photography portfolio gallery"` re-run for v3: first
style was again the Motion-Driven trend pick (scroll effects, parallax) — wrong for "quiet" —
so the palette evidence is superseded by the direction floor + subject movement, per the skill.

**Palette movement** (v2 values kept as the verified floor; no further hue moves needed — v3's
work is expression, not re-palette):

| Role | Shipped | Origin |
|---|---|---|
| Paper | #F1F2EE | sea-fog paper (floor #F7F4EE cooled) |
| Ink | #1B2224 | basalt |
| Muted | #59645F | sea grey |
| Accent | #175E52 | deep sea-glass teal — the hue of the subject's water |
| Card | #FAFBF8 | the one elevated paper (hanging field note) |
| Lightbox | #121517 / #E8EAE6 / #9FA9A4 | dark chamber |

Token block:

```css
--paper:#F1F2EE; --ink:#1B2224; --muted:#59645F; --teal:#175E52; --tide:#D3D6CE;
--card:#FAFBF8; --box:#121517; --box-text:#E8EAE6; --box-dim:#9FA9A4;
--err:#8C2F1B; --input-border:#77837C;   /* UI boundary, 3:1 floor */
--serif:Georgia,'Iowan Old Style','Times New Roman',serif;
--sans:'Segoe UI',system-ui,-apple-system,'Helvetica Neue',sans-serif;
--sans-light:'Segoe UI Light','Segoe UI',system-ui,sans-serif;  /* weight-200 end */
```

Type: body 17.5px/1.65 Georgia; display clamp(58px, 8.2vw, 102px) italic, tracking −0.022em,
line-height 1.0; UI 12.5–14px Segoe UI.

## Expression checklist (the six items, with what was actually done)

1. **Type drama — display ≥ 3× body, tracking/line-height contrast, weights at both ends.**
   Display "Slack water" at up to 102px italic = 5.8× the 17.5px body, tracking −0.022em and
   line-height 1.0 against the body's 1.65 — the tight/open contrast is the liveliness.
   Weights: Georgia's family ends are 400↔700 and both are used (400 display and body vs 700
   wordmark and the overline's bold "featured this month"); the sans end reaches 200↔700 — the
   giant "12" (editions) is set in Segoe UI Light at weight 200, 118px, while filter counts and
   the bolded overline run 700. The "12" is real information wearing display clothes.
2. **Exactly one asymmetry, one full-bleed/overlap moment.** Full-bleed: the hero runs
   edge-to-edge (82vh) against inset content below. Overlap: the display sits ON the
   photograph, backed by a bottom scrim + text-shadow. Asymmetry: the field-note card hangs
   over the hero's bottom edge into the paper (bottom: −42px, offset right), leaving the void
   below-left deliberately empty — the whitespace is concentrated, not distributed.
3. **Exactly one focal point, earned by two levers.** The hero seascape with the sun: scale
   (82vh full-bleed, the largest field by far) + contrast (the only dark, saturated field on a
   pale page) + isolation (nothing else is on the first screen but title and note card). The
   grid plates visibly step down — smaller, inset, quieter.
4. **Texture on hero-scale fields — no dead-flat hero.** The hero carries feTurbulence grain
   (mix-blend overlay), a radial vignette and the new bottom scrim; the page paper is a
   near-invisible tint gradient (#F3F4F0 → #EDEFE9), not a solid.
5. **Softened skeleton.** Every v2 hairline that separated header/sections/footer is gone —
   space is the divider (header 30px pad, sections 96–118px apart). One organic divider: the
   tide line between Works and About — a hand-drawn SVG path with a slight wobble
   (`_seg2.png` shows it). One rotated accent: the "Edition of 12 — 5 remaining" gallery stamp
   on Kelp study, rotated −2° in a bordered pill.
6. **Signature.** The seven hand-painted coastal plates (hero long-exposure seascape with sun,
   fog band, clip-path headland, silk streaks and sun-lane; kelp straps; fog line; sea stack
   with reflection; harbour lamps; rain squall; ebb-tide mirror) + working filter, lightbox
   (Esc/overlay/focus return), sold-out edition, print form with real validation. Remove them
   and the page is a generic gallery — the signature is the page.

## Render → look → fix (what I saw and changed)

- First hero capture: composition, display and hanging card all read; **weakest decision** was
  the sky — the sun was a faint smudge and the sea's sun-lane was invisible, leaving 54% of the
  frame inert. Fix: sun core to full alpha with a wider halo (3%/8.5%/15%/22% stops) and the
  sea's sun-lane strengthened (`.6 → .2 → transparent` at 64% 100%). Re-rendered: the sun has
  presence and the water carries its reflection; the eye lands on sun-then-title.
- Full-page review found no other blocking weakness: grid gap widened 34→40px, stamp visible
  (seg1), tide line + giant "12" + space-divided facts visible (seg2), prints form and footer
  calm (seg2).

## Verification (real tool outputs)

- `wcag.py` (all shipped pairs): #1B2224/#F1F2EE 14.36 · #59645F/#F1F2EE 5.47 · #175E52/#F1F2EE
  6.77 · #175E52/#FAFBF8 7.33 · #1B2224/#FAFBF8 15.54 · hero title #FFFFFF over scrimmed sea
  (worst-case composite #2E3833) 12.14 · #E8EAE6/#2E3833 10.03 · lightbox #E8EAE6/#121517 15.14,
  #9FA9A4/#121517 7.58, close-border #6A7671/#121517 3.88 (UI ≥3) · #8C2F1B/#F1F2EE 7.36 ·
  #77837C/#FFFFFF 3.95 (UI) · #FFFFFF/#175E52 7.61 · paper gradient ends #F3F4F0 14.61 and
  #EDEFE9 13.93. All text ≥4.5, all UI boundaries ≥3. (The two "AA FAIL" lines in the output
  are the UI-boundary pairs, whose floor is 3:1 — both pass it.)
- `slop_scan.py index.html` — **0 blocking, 0 important, 0 review, 0 polish** (exit 0).
- `visual_capture.py` (served via `python -m http.server 8433` from treatment-v3/, killed by
  PID afterwards): hero 1280×800 and full-page 1265×3525, CDP engine — `blank: false`,
  `console_errors: []`. Reviewed `_seg0/_seg1/_seg2.png` + two hero re-captures.

## States covered (and where they live)

- Filter tabs (aria-pressed) incl. "Winter" with 0 works → empty state with "Show all works"
  reset — reachable, not first paint.
- Lightbox: role=dialog, aria-modal, Esc + overlay click + close button, focus return; plates
  keyboard-operable (Enter/Space).
- Sold-out edition: caption label + disabled option in the print select with reason.
- Print form: inline email error, sold-out status message, success confirmation, aria-live.
- Reduced motion: hero drift and plate hover transitions disabled. Focus rings 2px teal,
  distinct from hover.

## Not verified

- Dark theme (single paper theme by design; the lightbox is the dark chamber).
- 150%-scale/phone matrix beyond the CSS breakpoints (responsive rules written, not captured).
