# Color and type

## Color roles, not swatches

Name colors by the job they do, then give each role a value per theme:

- canvas: the page background
- surface: cards, panels, inputs
- raised: menus, popovers, the layer above a surface
- border: control edges and dividers (control edges need 3:1 against the surface)
- text and muted text
- accent, and accent-text: the text color on top of the accent fill
- success, warning, danger, each with its own text-on-color and soft tint
- data series: categorical hues and a sequential ramp

Two tokens are rarely enough. Write the full set, even when some roles repeat a value.

## Build in OKLCH

Describe palettes in OKLCH, which keeps lightness steps even across hues. Use fixed lightness steps. On light surfaces, for example, OKLCH L of 0.99, 0.97, 0.94 and 0.90. Keep neutrals low in chroma (about 0.005 to 0.02) and tint them toward the accent hue. Keep the accent chroma as high as the design needs, then check it in sRGB: colors outside sRGB are clipped by the browser, so `wcag.py` clips them the same way.

Proportions: about 60% neutral canvas, 30% surfaces and secondary neutrals, and 10% or less accent. The accent can be smaller than that.

## Contrast

- Text: at least 4.5:1, including placeholder text, which is text.
- Large text (24px regular, or 18.66px bold) and UI parts (control boundaries, focus indicators, icons that carry meaning): at least 3:1.
- Disabled controls are exempt under WCAG. Keep their labels legible anyway.
- AAA (7:1 for text) is a good target for long reading and optional elsewhere.

Check every pair you ship: `python scripts/wcag.py FG BG`. A palette that passes on paper can still fail on a tinted surface, so check the surface a text actually sits on.

## Dark theme is a ladder, not an inversion

- Base surfaces at OKLCH L of about 0.15 to 0.20: a dark slate such as #13161B, never pure black unless the brief is brutalist.
- Each raised level steps OKLCH L up by roughly 0.02 to 0.03. Depth comes from these steps.
- Text at OKLCH L of about 0.92 to 0.96. Pure white for long text is harsh.
- Desaturate the accent by 10 to 20 percent and re-check its contrast.
- Borders that are the only affordance for a control still need 3:1.
- Check success, warning and danger again on the dark surfaces.

Light theme: avoid pure black body text on pure white for long reading. An off-white canvas (for example #F7F7F5) with ink near #1F2421 is easier to read.

## Color is never the only signal

Pair every status color with a shape, an icon or a word. For charts, distinguish series by pattern, label or position as well as hue. Do not separate states with red against green alone, because red-green colour blindness is common.

## Data colors

- Categorical: no more than six or seven hues. The Okabe-Ito set is safe for most color-vision deficiencies: #E69F00, #56B4E9, #009E73, #F0E442, #0072B2, #D55E00, #CC79A7.
- Sequential (magnitude): one hue, stepping lightness. Never a rainbow.
- Label series directly where possible. Legends make the eye travel.

## Theme switching

Offer system, light and dark. Apply the stored theme before first paint so a wrong theme never flashes. Test both themes with every state, not only the default screen.

## Type families

- One family is often enough. Two at most, plus one mono face for code-like values. Pick for the subject, not for a trend. If you cannot name the reason for a face, use the system stack.
- Avoid pairing two near-identical sans families. Pair contrast in classification (serif with sans, grotesk with mono), not in name.
- Do not use italic for Chinese or Japanese text; those scripts have no true italic.

## Font stacks and loading

- Windows desktop UI, system fonts: `"Segoe UI Variable", "Segoe UI", system-ui`, then the CJK fallbacks `"Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif`.
- Mono: `"Cascadia Code", "Cascadia Mono", Consolas, ui-monospace, monospace`.
- Self-hosted: bundle woff2 files with the app, keep their license file beside them, and use `font-display: swap`. Prefer variable fonts to several static weights.
- Do not bundle a full CJK font. Use the system CJK stack, or subset only the characters you need.
- In apps whose content security policy blocks external font hosts, a CDN `@import` fails silently and the fallback is what users see. Test the fallback as a design, not as an accident.

## Type scale

Pick one ratio and use five to seven steps. Do not invent sizes per component.

- 1.125 (major second) for dense application UI.
- 1.2 (minor third) for balanced product UI.
- 1.25 (major third) for content and marketing.
- 1.333 (perfect fourth) only for display-heavy pages.

Base sizes: 14px for dense desktop UI, 16px for web body text. Never go below 12px for required content.

## Line length, height and weight

- Prose measure: 45 to 75 characters, and no more than 80 (Baymard: optimal 50–75 characters, baymard.com/research-articles/line-length-readability). Set the measure with `max-width` in `ch`.
- CJK prose: count full-width characters. A comfortable line is roughly 30 to 40 characters (Baymard, same source: 40 or fewer for CJK). This is a heuristic, so test it on a real paragraph. Mixed-script spacing, punctuation rules and weight availability live in `cjk-typography.md`.
- Body line-height: at least 1.5. WCAG 1.4.12 requires text to stay readable at 1.5, so a fixed value below that breaks the text-spacing criterion. CJK body text reads well at 1.6 to 1.75; clreq's hard anchor (§5.5.3.2) is ≥1.5× when annotation (ruby) is present.
- Headings: 1.1 to 1.3. UI labels in dense controls: 1.3 to 1.4.
- Weights: two or three in use, typically 400, 500 or 600, and 700. Use weight for hierarchy before changing size.

## Numerals, tracking and wrapping

- `font-variant-numeric: tabular-nums` for tables, logs, counters, token counts and any column that changes. Proportional numerals elsewhere.
- Headlines: letter-spacing of -0.01 to -0.02em. Small all-caps labels: +0.04 to +0.08em, and only for short labels.
- `text-wrap: balance` for headings, `text-wrap: pretty` for paragraphs.
- Identifiers such as paths, model names and IDs: `overflow-wrap: anywhere` or truncation with the full value available on hover and focus.

## Things to avoid

- All-caps Chinese text; it has no meaning in caps.
- A mono face for all small labels by default. Use it for values and code-like strings only.
- Italic or bold to accent one word in a headline, unless the brief asks for it.
- Letter-spacing added to body text.
