# B3 — E-commerce daily analytics dashboard (treatment-v3)

## Brief

Daily-use analytics dashboard for a small e-commerce shop: orders, conversion, top products.
Single self-contained index.html, inline CSS/JS, system fonts (Segoe UI + Cascadia/Consolas for
numerals), no external requests.

**Concrete subject:** Mill & Crumb, a small bakehouse — the dashboard is the owner's morning
screen at the counter. v2's subject and palette carried forward as the floor; v3's mandate is
expression — and per `expression.md`'s 刻意不采用, a data-dense instrument earns its beauty
through **the data display itself**, not decoration: the expression budget goes to the morning
band and the giant figure.

**Three refusals:**
1. No default blue SaaS dashboard on a cool grey canvas — the tool belongs to a bakehouse
   (v2's flour/rye/crust palette kept as floor).
2. No error box in the first paint — the default view is the working Saturday morning;
   loading/empty/disabled states live behind Refresh and the channel filter.
3. No identical-card soup — panels differ by job, hierarchy from size and colour, and v3
   removes the card borders entirely (space and one tinted shadow do the separating).

## Direction

**Direction 1 (technical instrument, light)** — a daily operations screen read in short bursts.
`design_lookup.py "e-commerce analytics dashboard" --charts` re-run for v3: first style was
again "Vibrant & block-based" (trend pick, wrong for a working instrument); superseded by the
direction floor + subject movement per the skill.

**Palette movement** (v2 values kept as floor):

| Role | Shipped | Origin |
|---|---|---|
| Canvas | #F7F3EA | flour |
| Surface | #FFFDF8 | warm white |
| Ink | #241D14 | rye |
| Muted | #6B6257 | warm grey |
| Accent | #963D0D | burnt crust |
| Chart weekday | #A9702F | baked ochre (graphic-only) |
| Band | #F9F5EC → #F1E7D2 | new: the morning band's flour-dust tint gradient |

Token block:

```css
--canvas:#F7F3EA; --surface:#FFFDF8; --ink:#241D14; --muted:#6B6257;
--border:#8A8275;  /* UI boundaries only */  --divider:#E4DCCC;  /* table rows only */
--accent:#963D0D; --accent-hover:#7C3209; --accent-graphic:#A9702F;
--tint-green:#E4EFE6; --tint-amber:#F3E3C9; --tint-crust:#F6E7DC; --tint-red:#F9E4E0;
--success:#15803D; --warning:#8A6D00; --danger:#B42318;
--shadow:0 1px 2px rgba(58,44,24,.05),0 10px 28px rgba(58,44,24,.07); /* tinted, directional */
--mono:'Cascadia Code',Consolas,'Courier New',monospace;
--sans:'Segoe UI',system-ui,-apple-system,sans-serif;
--serif:Georgia,'Iowan Old Style','Times New Roman',serif;
```

## Expression checklist (the six items, with what was actually done)

1. **Type drama — display ≥ 3× body, weights at both ends.** The dashboard's display moment IS
   the data: revenue "£1,847" set at up to 70px in Segoe UI Light (weight 300), tracking
   −0.03em, line-height 1.0, tabular figures — 5× the 14px body, and the other KPIs visibly
   step down (22px/600, then 13px table text). Weights reach both ends: 300 (the giant figure)
   against 700 (chip, panel titles, table headers, CTAs). The one serif display moment is the
   wordmark "Mill & Crumb" in Georgia italic — the hand-painted shop sign.
2. **Exactly one asymmetry, one full-bleed/overlap moment.** Full-bleed: the morning band runs
   edge-to-edge against the inset panels. Overlap: the delta chip "+12% vs last Saturday, same
   time" is stamped OVER the giant numeral's bottom corner, rotated. *(复判修复: retired — the
   chip now sits beside the figure, un-rotated; see 复判修复 below.)* Asymmetry: the band is
   left-anchored — a gauge-style vertical label ("Revenue today, to 14:00", writing-mode
   vertical) climbs the left edge while the right side keeps only the small "Saturday lift"
   note; the void concentrates right of the figure. *(复判修复: the band's lower half now
   carries the KPI row — see 复判修复 below.)*
3. **Exactly one focal point, two levers.** £1,847: scale (70px vs 22px vs 13px) + isolation
   (an entire quiet band around it) + contrast (the darkest, largest mark on the page). Every
   other number is visibly dimmer and smaller — the eye lands on revenue in one second.
4. **Texture on hero-scale fields.** The band is a flour-dust field: tint gradient
   (#F9F5EC → #F1E7D2) + feTurbulence grain at overlay 40%. No dead-flat band; panels stay
   quiet surface.
5. **Softened skeleton.** v2's panel borders, panel-header rules and KPI card boxes are all
   gone — panels are surface + one tinted warm shadow; KPIs are space-separated on canvas; the
   only hairlines left are the orders-table rows (functional). One organic divider: the baker's
   score — a single gently-curved SVG cut drawn just below the band, the blade line across the
   dough. One rotated accent: the delta chip (−1.5°). *(复判修复: rotation retired on this
   instrument screen — see 复判修复 below.)*
6. **Signature.** The hand-built SVG revenue chart — three real datasets (Today hourly, This
   week, 28 days), range tabs that re-render, weekend columns in crust brown encoding the
   shop's weekly rhythm, dashed £1,200 target line with a surface pill label, hover AND
   keyboard-focus tooltips, today's "live" dot, mono axis labels, and a caption line that
   explains the rhythm. Around it: quiet secondary KPIs, top products with share meters, a
   four-stage funnel, a ten-order table with four pill states, and a Needs-attention list whose
   buttons really act.

## Render → look → fix (what I saw and changed)

- First hero capture: band, vertical label, giant figure and scored line all read — **weakest
  decision** was a collision: the rotated chip covered the "to 14:00" suffix inside the figure,
  leaving both illegible. Fix: removed the suffix (the vertical label already carries "to
  14:00") so the chip stamps the numeral's corner cleanly. Re-rendered: overlap reads as a
  hand-stamped delta, digits fully legible.
- Full-page review: panel index numerals were too faint (caught by wcag before it reached the
  render, see below); orders panel bottom has some air next to the taller right column — left
  as breathing room, not a hole (content fills both columns).

## Verification (real tool outputs)

- `wcag.py` (all shipped pairs): #241D14/#F1E7D2 13.56 (band, darkest end) · #6B6257/#F1E7D2
  4.87 (vertical label) · #241D14/#F7F3EA 15.04 · #241D14/#FFFDF8 16.38 · #6B6257/#F7F3EA 5.40,
  /#FFFDF8 5.89 · chip #963D0D/#F6E7DC 5.85 · #963D0D/#FFFDF8 6.96, /#F7F3EA 6.38 ·
  #FFFFFF/#963D0D 7.07 · #15803D/#F7F3EA 4.53 · #B42318/#F7F3EA 5.94 · #8A6D00/#F3E3C9 3.90
  (pill dot, graphic ≥3) · #A9702F/#FFFDF8 4.09 (chart columns, graphic) · #8A8275/#FFFDF8 3.74
  (UI boundaries) · toast #F7F3EA/#241D14 15.04 · pill tints with ink text 13.20–14.11. All
  text ≥4.5, all UI/graphic pairs ≥3. **Fixed during the run:** panel index numerals were
  #B9AD98 = 2.18 (below both floors) → darkened to #6B6257 (5.89).
- `slop_scan.py index.html` — initial run 0/0/0/0; final **0 blocking, 0 important, 0 review,
  0 polish** (exit 0).
- `visual_capture.py` over `http://127.0.0.1:8433/B3/index.html`: hero 1280×800, full-page
  1265×1668, CDP engine — `blank: false`, `console_errors: []`. Hero re-captured after the chip
  fix (`hero2-*.png`).

## States covered (and where they live)

- Loading: Refresh → disabled "Refreshing…", aria-busy on the KPI strip, timestamp update,
  named toast. Reachable, not first paint.
- Empty: channel filter → "No wholesale orders yet today. Wholesale pickups land before 07:00
  on weekdays — the next van is Monday." with a "Show all orders" reset.
- Disabled: post-action attention rows swap buttons for a dated state line; Refresh disables
  in flight.
- Partial data: "to 14:00" in the vertical label and caption; live dot on today's column.
- Error: none simulated in the default view (v1's failure mode stays dropped).
- Keyboard: chart columns focusable with aria-labels; tabs and channel native; focus ring 2px
  crust, distinct from hover. Reduced motion kills all transitions.

## Not verified

- Dark theme (a morning-daylight instrument by design).
- The 5-minute auto-refresh tick (declared in copy; the Refresh control demonstrates the path).
- Hover/tooltip states beyond v2's verified implementation (chart JS carried over unchanged in
  logic; this run captured the default render).

## 复判修复 (maintainer re-judgment after v3 shipped)

**Verdict (verbatim):** "B3 会出现把标签打到字体以凸显创造的想法，但是实际上这个行为导致遮
住了数字，可能会影响识别，而且中间画幅大而空，作为电商仪表盘这种需要清晰、柔和的将人目光
吸引到关键数据上的界面，光宣泄自己的艺术行为恐怕不太行"

The governing rule (`expression.md` §4, focal engineering) now states it directly: on
instrument screens (dashboards, monitoring, trading) the focal point IS the data — never
overlap, stamp or rotate anything across primary figures; a badge sits beside the number, not
on top of it. And a large empty canvas band reads as venting: fill the frame with the working
content and let the figures stay dense, legible and unobstructed.

**Fix 1 — the figure de-obstructed.** The delta chip left its absolute, −1.5°-rotated stamp
position on the numeral's bottom corner. `.dawn-fig` is now an inline-flex **baseline row**:
the chip sits to the RIGHT of "£1,847", upright, on the shared baseline, as a quiet annotation
(weight 700→600, the stamp shadow dropped, same verified pair #963D0D on #F6E7DC). No
rotation, no overlap — every character of the figure is fully visible (confirmed on the
re-capture). The "one rotated accent" is retired on this instrument screen; the band keeps its
asymmetry in the vertical gauge label and the left-anchored mass.

**Fix 2 — the band's empty middle filled with working data.** The three quiet KPI columns
(Orders / Conversion / Average basket) moved from the canvas below INTO the band, as its lower
row: between the hero row and the baker's-score divider, same 28px side padding, 64px gaps,
`position:relative` so the row paints above the grain like the hero row does. No decorative
filler was added — the frame now carries hero figure + three working columns + the Saturday
note, and the scored line closes the band. The KPI strip keeps its canvas-level sizes (22px
values over 12.5px labels), so the 70px figure still owns the step-down hierarchy and its
isolation.

**New pair the fill created (and its fix).** The `.up` deltas (+8%, +0.3 pt) now sit on the
flour gradient, where `--success` #15803D would read **4.08** on the darkest stop (#F1E7D2) —
a fill that breaks a pair is a bug — so a band-scoped `.dawn .up{color:#12703A}` was added:
5.02 on #F1E7D2, 5.37 on #F5EFDF, 5.67 on #F9F5EC. `--success` #15803D is unchanged everywhere
else; after the move it only feeds the paid-pill dot (a graphic, 3:1 floor — unaffected).

**Re-verification (real tool outputs):**

- `page_audit.py http://127.0.0.1:8471/treatment-v3/B3/index.html` → `checked 153 text pairs:
  137 pass, 0 fail, 16 uncertain, 8 skipped (0 assumed canvas)` · `a11y: 0 target-size fails
  (8 pass), 0 unnamed (8 named), 0 heading-order reviews` · exit 0. The 16 uncertain are all
  `uncertain:gradient-or-image` — the tool's documented taxonomy for text over a gradient
  (listed with evidence, never verdicted): the 4 pre-existing band rows plus the 12 relocated
  KPI rows. Baseline before the fix was 149 pass / 0 fail / 4 uncertain; the pass count moved
  into the uncertain bucket because of where the KPIs now sit, not because any pair broke —
  each of those pairs is wcag-verified below and settled visually by the capture.
- `wcag.py` on the pairs the fill put on the band (worst case = darkest stop #F1E7D2 unless
  noted): #241D14 13.56 · #6B6257 4.87 · #12703A 5.02 (also 5.37 on #F5EFDF, 5.67 on #F9F5EC)
  · #B42318 5.35 · chip #963D0D/#F6E7DC 5.85. All text-AA pass.
- `slop_scan.py index.html` → `scanned 1 file: 0 blocking, 0 important, 0 review, 0 polish`
  (exit 0).
- `visual_capture.py` (CDP engine, Chrome) → `hero3-1280x800-light@1.png`: `blank: false`,
  `console_errors: []`, settled. The hero shows the figure unobstructed with the chip beside
  it on the baseline, the KPI row filling the band's lower half, score line at the bottom.
- Server killed afterwards (netstat + taskkill; port 8471 clear).

**Unchanged:** palette tokens (except the scoped band green above), the 70px light figure,
band gradient + grain texture, vertical gauge label, scored-line divider, chart, tables,
funnel, attention list, all JS and states; the narrow-viewport media query only swaps the now
obsolete `.chip{position:static…}` override for a `.dawn-fig{flex-wrap:wrap}` (chip wraps
under the figure when narrow). No test files touched.
