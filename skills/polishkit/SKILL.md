---
name: polishkit
description: Visual decisions and visual verification for web and desktop UI (direction, palette, type, layout, density, motion, states). Ships product precedents (Chinese and English keywords), WCAG and draft-APCA contrast checks, a token-file linter, a rendered-page contrast audit, color-vision simulation, a scanner for generic "AI slop" tells, and a CDP render-capture-diff loop that proves what a change did to the screen, dark theme and interaction states included. Use alongside frontend-design when building, restyling or reviewing a UI, choosing colors or fonts, or critiquing visual quality.
---

# PolishKit

frontend-design sets the stance: commit to a direction and avoid defaults nobody chose. This skill supplies the decision rules, the numbers, the precedent data and the checks that make those choices verifiable. If `frontend-design` is not installed, this skill stands alone: nothing in it depends on that skill being present. Open the reference a step names when you need it; do not read them all up front.

## 1. Read the project's rules first

- Look for a brief or contract before designing: `DESIGN.md`, `PRODUCT.md`, a token file (`tokens.css`, `theme.*`, `tailwind.config.*`), or a contract document such as `FRONTEND_CONTRACT.md`. These outrank the defaults in this skill.
- If the project routes visual values through tokens, a new raw hex, px or rgba value in a component is a finding, not a style choice.
- Keep what already works: theme switching, i18n keys, accessibility behaviour, existing components. Restyle the scope that was asked for, not the whole app.

## 2. Brief

Write the brief described in `references/principles.md`: subject, audience and context, the job of the main screen, density, languages, and the five dimensions (typography, color, layout, motion, details). Add three refusals: defaults this design must not look like. If the user has not described a taste, propose one direction and say why. Do not interrogate the user.

## 3. Precedents

Run this from the skill's base directory:

```
python scripts/design_lookup.py "saas dashboard dark" --ux --motion
```

Chinese keywords work too ("暗色 仪表盘"); mapped terms are printed as a trace. When the product displays data, also pass `--charts`.

Use English keywords. The output gives the matching product type, its styles, a palette with contrast-checked text and UI pairs, typography pairings and reasoning rules. Treat it as evidence, not an answer. Its first style is often a trend pick (glassmorphism, neon, bento) that is wrong for dense tools. Text pairs fail in only one of the 192 palette rows, but most palettes have a border below 3:1 against the background, so every palette needs its UI pairs checked before use.

## 4. Direction

Choose one direction from `references/directions.md`, or define your own, and state why it fits this brief and why the nearest alternative does not. The direction's values are a verified floor: move them toward the subject before building — the accent takes its hue from the brief's world, not from the table.

Spend boldness in one place: one signature element, and it must be the single most-crafted thing on the page — a real working capability (a live demo, a real calculation, a working control) or a hand-built visual. When the brief is image-forward and no image assets exist, paint the imagery: layered CSS gradients, clip-path shapes, SVG grain and filters. A placeholder rectangle, a stock waiting-state or two grey divs standing in for photos is not a signature. Everything around it is disciplined — and the craft of the signature is judged by `references/expression.md`: type drama, one compositional break, one focal point.

## 5. Tokens before components

Define color roles, the type scale, spacing, radii, elevation and motion durations as variables first (`references/color-and-type.md`, `references/layout-and-motion.md`). Check every text pair you ship, and lint the token file itself:

```
python scripts/wcag.py "#1f2937" "#ffffff" "#556070" "#f6f7f9"
python scripts/token_lint.py <source paths>
```

## 6. Build

Cover every state, not only the happy path (`references/components-and-states.md`) — but the default render shows the working data. Error and empty states are reachable behind controls or routes, never what the first paint shows. Keep copy in the product's languages and test the longest translation.

Before calling it done, render the hero and the signature once and look (`python scripts/visual_capture.py <url> --out shots`), then polish the weakest visual decision you can see, running the expression checklist in `references/expression.md`: type drama (display ≥ 3× body, weights at both ends of the family), one deliberate asymmetry or full-bleed moment, exactly one focal point earned by two levers, texture on hero-scale fields. A passing scanner is not the finish line — the page has to survive its own screenshot and hold the eye.

## 7. Verify before reporting

- Render it and look. `python scripts/visual_capture.py <url> --out shots --matrix` gives default, 150%-scale, narrow and phone views, waits for a settled frame, and reports console errors. Over CDP, `--dark` really emulates `prefers-color-scheme`, and `--full-page`, `--element`, `--hover`, `--focus` reach the states the plain screenshots cannot. Read `references/visual-review.md`; a review without a capture is not a visual review.
- After a change, capture again and run `scripts/image_diff.py before.png after.png`. If the changed region does not match what you claim to have changed, the claim is wrong.
- `python scripts/slop_scan.py <changed paths>`. Exit status 1 means blocking findings.
- `python scripts/token_lint.py <paths>` audits the token file and raw-value leaks.
- Contrast for every text and UI pair you actually shipped (`wcag.py`; `--apca` adds a draft supplementary reading). When the page can be served, `python scripts/page_audit.py <url>` audits every visible pair in the render and separates measurable verdicts from uncertain ones.
- A keyboard-only pass, a reduced-motion pass, and the break test with worst-case data.
- Console errors are failures. So is a capture reported as `blank`; treat one reported as unsettled as suspect.

When no browser can be reached, write "not visually verified", name the states you skipped, and claim nothing about what the rendered UI looks like.

## 8. Report

Name the direction and the reason for it, give the token block, and list each verification with its command and result. List what was not verified.

## Floors (never trade these for looks)

- Text contrast of at least 4.5:1. Large text (24px, or 18.66px bold) and UI boundaries or focus indicators need at least 3:1.
- Every interactive element has a visible keyboard focus indicator that differs from its hover state.
- Color never carries meaning on its own.
- Motion honours `prefers-reduced-motion`. Nothing flashes more than three times per second.
- Body text is at least 16px on the web and 14px in dense desktop UI. No text under 12px.
- Every state exists: loading, empty, error, disabled and partial data.
- No placeholder copy ships. Errors say what happened and what to do next.
- Text survives the longest realistic string: translations, CJK, long paths and model names.

## Taste rules

- One dominant neutral does most of the work. One accent covers at most about 10% of the screen. Success, warning and danger colors stay fixed across themes.
- Two type families at most, plus a mono face if needed. One scale ratio. Hierarchy comes from size, weight, color and space before boxes.
- Fewer borders and fewer nested cards. Radius from one small scale. Shadows tinted to the palette, with at most three elevation levels.
- Motion: one purposeful moment per screen, transform and opacity only, and no animation on actions repeated many times in a session.
- Copy: sentence case, plain verbs, and the same name for an action in the button, the result message and the menu.

## The choice test

Every default (font, palette, radius, shadow, layout, icon set) must be chosen for this brief. If you cannot name the reason, change it. A default you chose is not a tell. `references/anti-slop.md` lists the common tells and the scanner rule that flags each one.

## Files

- `references/principles.md`: decision order, brief template, refusals.
- `references/directions.md`: nine directions with verified starting tokens.
- `references/color-and-type.md`: palettes, dark mode, contrast, type scale, font loading, CJK.
- `references/layout-and-motion.md`: grid, density, spacing, radii, elevation, motion.
- `references/components-and-states.md`: components, state matrix, copy, break test.
- `references/desktop-app.md`: rules for WebView and desktop apps.
- `references/native-feel.md`: macOS and Windows platform conventions, materials and metrics for desktop shells.
- `references/cjk-typography.md`: mixed-script spacing, punctuation rules, CJK line height and weight availability.
- `references/charts.md`: chart selection, data-ink discipline and the colour authority order for data display.
- `references/expression.md`: the layer between correct and beautiful — type drama, compositional tension, focal engineering, texture.
- `references/anti-slop.md`: tells, why they read as defaults, questions to ask, scanner rule IDs.
- `references/critique.md`: review procedure, ten pillars, severity, output format.
- `references/visual-review.md`: how to render, capture, read and re-diff the UI.
- `references/sources.md`: where each rule came from and what was deliberately not used.
- `scripts/wcag.py`, `scripts/design_lookup.py`, `scripts/slop_scan.py`, `scripts/token_lint.py`, `scripts/visual_capture.py`, `scripts/image_diff.py`, `scripts/color_sim.py`, `scripts/cdp.py`, `scripts/page_audit.py`: read-only, no third-party packages, no network (the capture and audit tools talk to a loopback browser you already have). Use `py -3` if `python` is not on PATH.
- `data/`: MIT-licensed CSV data vendored from ui-ux-pro-max (see `data/PROVENANCE.md`).
