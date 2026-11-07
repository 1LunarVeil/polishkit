# Expression (表现层)

The layer between "correct" and "beautiful". Floors, tokens and direction tables keep a page from being wrong; this file keeps it from being inert. Every technique here is checkable — a page that skips all of them reads as a wireframe that learned manners.

Diagnosis this file exists for: type applied at correct sizes with no drama, layouts fully aligned with no tension, mechanical hairlines everywhere, nothing that pulls the eye. The fix is not decoration — it is four kinds of deliberate contrast.

## 1. 字阶戏剧 (type drama)

A type scale gives correct sizes; expression needs contrast between them.

- Display ≥ 3× body size (16px body earns a 48–64px display). A page whose largest text is under 2.5× body reads flat.
- Weight extremes: use the ends of the family — 200–300 against 700–800. The 400/500/600-only page is the dullest possible use of a variable font.
- Tighten display tracking (−0.01 to −0.03em) and cut display line-height to 1.0–1.2; the contrast between tight display and open body (1.6+) IS the liveliness.
- One italic or serif display moment per page, chosen for the subject.
- Oversized content as ornament: a price, a date, a section numeral set at 3–6× body — real information wearing display clothes.

## 2. 构图张力 (composition tension)

A grid keeps things aligned; expression needs one deliberate break per screen.

- One asymmetry per screen: an element breaking the column edge, overlapping the signature visual, or hanging into whitespace. Pick the break; do not spread it around.
- Whitespace is asymmetric — concentrate the void on one side of the composition instead of distributing it evenly. Even gaps everywhere is the wireframe tell.
- One full-bleed moment (hero or plate) against inset content; the edge-to-edge vs framed contrast structures the page without borders.
- Overlap, once: text over the signature visual with a contrast backing, or a plate bleeding off the viewport edge.
- Scale rhythm between sections: one dense cluster, one airy expanse. Sections at identical density read as a form.

## 3. 软化结构 (softening the skeleton)

Mechanical lines are the stiffest tell in the set.

- Borders whisper: before adding a rule, ask whether space can be the divider. Most pages need fewer than half the hairlines they ship.
- Where the subject warrants, replace straight dividers with organic ones — an arch (hotel), a wave or pour line (coffee), a horizon (travel). One per screen at most.
- Rotate one accent element 1–3° for a hand-placed feel. One. More reads chaotic.
- Shadows are directional and tinted (a light source exists), never a symmetric glow.

## 4. 焦点工程 (focal engineering)

Exactly one focal point per screen, earned by at least two of the three levers: scale (largest), contrast (highest), isolation (most whitespace around it). Everything else visibly steps down — smaller, dimmer, denser. Two competing focal points cancel each other; zero focal points means the eye has nowhere to land and leaves.

On instrument screens (dashboards, monitoring, trading) the focal point IS the data: never overlap, stamp or rotate anything across primary figures — a badge sits beside the number, not on top of it, however tempting the composition. Occluding a key figure to make a compositional point is the costliest tell in this file.

## 5. 质感 (texture)

Flat 100% solid fills at hero scale read as wireframes.

- Grain: SVG feTurbulence noise over large fields (2–6% opacity).
- Paper warmth on light themes: a near-invisible tint gradient, not a solid.
- The signature element gets the texture budget; the rest stays quiet.

## The checklist (run in the polish pass)

1. Is the display at least 3× body, with tracking and line-height that contrast the body setting?
2. Do the weights reach both ends of the family?
3. Is there exactly one asymmetry, one full-bleed or overlap moment?
4. Can you point at the focal point in one second? Which two levers earn it?
5. Is any hero-scale field dead flat?
6. Would removing the signature element leave the page generic? If yes, the signature is not crafted yet — go back.

## 刻意不采用

- Random rotation of body text or content blocks (reads broken, not lively).
- Gradient text on body copy (accessibility and taste).
- More than one asymmetric break per screen (tension needs a baseline of calm to exist against).
- Expression on data-dense instrument screens beyond weight/size discipline — dashboards earn trust through calm. Their expression budget lives in the band, the typography and the texture AROUND the data: a large empty canvas band reads as venting, so fill the frame with the working content and let the figures stay dense, legible and unobstructed.
