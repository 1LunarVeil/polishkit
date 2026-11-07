# B4 — Boutique hotel booking flow (treatment-v3)

## Brief

Booking flow for a boutique hotel — weekend-getaway audience, warm and trustworthy. Single
self-contained index.html, inline CSS/JS, system fonts (Georgia stand-in serif + Segoe UI for
UI labels and the light-weight price numeral), no external requests.

**Concrete subject:** The Larches — seven rooms above Winder Water, under old larches, in
autumn. v2's subject and palette kept as the floor; v3's mandate is expression: the first
screen must stop the eye.

**Three refusals:**
1. No ivory-and-hex-lingering direction-8 clone — the palette stays moved toward the building's
   world (honeyed linen, coppered bronze, lake pine, larch gold in paint only).
2. No native `<input type="date">`, no payment-timeout theatre — the hand-built two-month
   calendar IS the first screen's working data; errors live behind real actions.
3. No gradient-washed chrome — gradients appear only inside painted imagery (hero scene, room
   swatches); chrome stays flat ivory/ink/bronze.

## Direction

**Direction 8 (refined luxury)** — hospitality is its home ground; the brief's audience wants
unhurried. `design_lookup.py "hotel booking" --motion` re-run for v3: first style was again
"Liquid Glass" (trend pick, wrong for a country house); superseded by the direction floor +
subject movement per the skill.

**Palette movement** (v2 values kept as floor):

| Role | Shipped | Origin |
|---|---|---|
| Ivory | #F6F0E4 | honeyed linen, warmed toward autumn |
| Surface | #FBF7EC | card ground |
| Ink | #1E1811 | espresso |
| Bronze | #7E5218 / #63400F | coppered bronze — actions, prices, focus |
| Pine | #1F3A33 | the world's dark — band, arch, painted scene |
| Gold | #C98A2D | painted imagery only, never text |

Token block:

```css
--ivory:#F6F0E4; --surface:#FBF7EC; --ink:#1E1811; --muted:#6E6353;
--bronze:#7E5218; --bronze-deep:#63400F; --pine:#1F3A33; --gold:#C98A2D;
--success:#166534; --danger:#B42318;
--shadow:0 1px 2px rgba(46,34,18,.06),0 14px 34px rgba(46,34,18,.1); /* tinted, directional */
--serif:Georgia,'Iowan Old Style','Times New Roman',serif;
--sans:'Segoe UI',system-ui,-apple-system,sans-serif;
--sans-light:'Segoe UI Light','Segoe UI',system-ui,sans-serif;  /* weight-300 end */
```

## Expression checklist (the six items, with what was actually done)

1. **Type drama — display ≥ 3× body, weights at both ends.** Display: "Seven rooms / above the
   water" at up to 92px Georgia italic (5.4× the 17px body), tracking −0.02em, line-height
   1.02 against body 1.6. The price wears display clothes too: the summary total is Segoe UI
   Light (300) at 46px, tabular. Weights: Georgia 400 display ↔ 700 (wordmark, room names);
   sans 300 price ↔ 700 (CTAs, room rates, weekend days).
2. **Exactly one asymmetry, one full-bleed/overlap moment.** Full-bleed: the painted dawn hero
   (74vh, edge-to-edge). Overlap: the booking cards rise into the pine band —
   `margin-top:-40px` over the band's arch-curved bottom edge, cards straddling the dark field
   and the ivory. Asymmetry: the display's staggered lines — "above the water" indented 1.6em,
   one deliberate typographic break — with the caption void concentrated right.
3. **Exactly one focal point, two levers.** Screen one: the dawn scene + display title — scale
   (74vh full-bleed) + contrast (the warmest, most saturated field against ivory; ivory text
   over the darkened pool). Booking screen: the calendar is the instrument's heart and every
   other element (legend, message, CTA) steps down around it.
4. **Texture on hero-scale fields — no dead-flat hero.** The scene carries grain (overlay 50%),
   the pine band its own grain at 35%, the room swatches grain at 40% over their painted
   gradients, and the body is a near-invisible tint gradient (#F7F1E5 → #F3EAD9).
5. **Softened skeleton.** v2's card borders, summary-row rules and footer rule are gone —
   surface + one tinted shadow separate the cards; summary rows are space-separated; the only
   rules left are the calendar's functional day fills and the total's single top rule. One
   organic divider: the pine band ends in a broad arch (SVG path, dipping ~44px at centre) —
   the arch is the shape the subject warrants, echoed by the arch-topped room swatches. One
   rotated accent: the desk note pinned to the hero ("Dogs report to the desk for biscuits."),
   rotated +1.5° with a bronze pin head.
6. **Signature.** The working two-month booking calendar driving live pricing: Monday-first
   grids, past days and the booked weekend (13–14 Nov) hatched, the Christmas closure struck
   with its reason on hover, tonight marked with a bronze dot, range selection with tinted
   fill and bronze endpoints, 14-night cap that trims and explains itself — every state flows
   into the sticky "Your stay" summary (nights × rate, extras, LARCH discount, total "payable
   at the hotel"). Supporting craft: the painted first-light hero, three painted arch-topped
   room swatches, the bronze wax-seal confirmation.

## Render → look → fix (what I saw and changed)

- First hero capture: title size and stagger read, but **three weaknesses**: the overline sat
  on the gold treeline with no dark backing (illegible); the pine treeline zigzag was too
  mechanical (22–70% spikes = sawteeth); the mist band washed the title zone. Fixes: treeline
  amplitudes halved and made irregular (pine 38–62%, gold 50–66%), mist lowered to 64% at
  55% alpha, and a dark pool added under the caption.
- Second capture: the pool fixed legibility but read as a **hard-edged dark rectangle** — the
  linear gradient's edge was visible despite blur(14px). Fix: rebuilt as a radial pool
  (72% 120% at 22% 100%, fading to transparent at 88%) with blur(22px) — fades on every side.
  Re-rendered: overline and staggered lines legible, pool invisible as a shape.
- Full-page capture: the arch curve and the card overlap render as intended; calendar shows
  tonight dot, hatched 13–14, filled 20–22 with bronze endpoints, struck 24–26 Dec, working
  "Choose a room" CTA; summary shows the pencilled-in weekend and the honest "—" total.
- `slop_scan` flagged the room-card hover as HOVER-LIFT (shadow change) — changed to a warm
  background tint (#FDF8EC); the selection ring stays on `.sel`. Re-scanned clean.

## Verification (real tool outputs)

- `wcag.py` (all shipped pairs): #1E1811/#F6F0E4 15.50 · #6E6353/#F6F0E4 5.18 · #7E5218/#F6F0E4
  5.95, /#FBF7EC 6.31 · #6E6353/#FBF7EC 5.49 · #1E1811/#FBF7EC 16.43 · #FFFFFF/#7E5218 6.76 ·
  #FFFFFF/#63400F 9.25 · hero caption composites (worst-case pool #594C36): #F8F2E3 7.49,
  overline #F0E7D2 6.79 · band #FFFFFF/#1F3A33 12.27, #C9D2C7/#1F3A33 7.90 · #166534/#F6F0E4
  6.28 · #B42318/#F6F0E4 5.79 · in-range days #1E1811/#EFE2C6 13.71. All text ≥4.5.
  **Fixed during the run:** inactive step-button borders #E2D8C4 (1.35, below the 3:1 UI
  floor) → #9A8D72 (3.27 UI pass). Larch gold stays restricted to painted imagery (2.59 on
  ivory, never text).
- `slop_scan.py index.html` — initial: 1 review (HOVER-LIFT on room hover). Fixed as above.
  Final: **0 blocking, 0 important, 0 review, 0 polish** (exit 0).
- `visual_capture.py` over `http://127.0.0.1:8433/B4/index.html`: hero 1280×800 (three passes:
  hero → hero2 → hero3 after the fixes above), full-page 1265×1584, CDP engine — `blank:
  false`, `console_errors: []`. Reviewed segments: hero, band-arch + card overlap, calendar +
  summary + footer.

## States covered (and where they live)

- Default render: working calendar with real availability (booked weekend hatched, closure
  struck, tonight dotted) and a pencilled-in weekend (Fri 20 – Sun 22) in the summary —
  working data, first paint.
- Disabled: past days, booked days, closed days (hover reason), Garden Room when dates overlap
  the wedding (27–29 Nov) with a named reason, step CTAs until prerequisites, summary CTA
  after holding.
- Error: incomplete form ("We need a name to hold the room." / "That email doesn't look
  complete."), unrecognised promo code — both behind real actions, none in first paint.
- Loading: "Holding your room…" during the 700 ms hold. Success: seal confirmation with
  reference code, dates, discounted total, named guest.
- Keyboard: every day a button with a full aria-label; steps expose aria-current; summary
  aria-live; custom checkboxes keep a visible focus ring; focus rings bronze, distinct from
  hover. Reduced motion disables reveals and transitions.

## Not verified

- Dark theme (single warm theme by design).
- Step 2/3 panes and the confirmation flow were not re-driven interactively in this run — the
  calendar/booking JS is carried over line-for-line from v2, where the full flow (dates →
  wedding block → promo LARCH −£72 → hold → seal) was Playwright-verified; this run verified
  the default render, the states' presence and the scanners.
- The calendar beyond November–December 2026 (page pins to the benchmark's "today").
