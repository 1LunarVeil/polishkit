# Directions

Nine starting points. Each is a complete, checkable choice, not a mood board. Use one as written, mix two on purpose, or write your own with the same fields. All hex values below pass WCAG AA for the pairs listed; if you change a value, re-run `wcag.py` on the pairs it affects.

The hex values are a **verified floor, not the design**. After choosing a direction, move the palette toward the subject: the accent at minimum takes its hue from the brief's world — a hotel earns the brass and linen of its building, a coffee shop earns coffee, a photography portfolio earns the tones of its landscapes. A direction adopted verbatim, with its hexes untouched, is itself a tell: it says nobody looked at the subject.

Choosing: match the subject first, then the density.

| Subject | Start from |
|---|---|
| Developer tools, launchers, consoles, admin | 1 (light) or 6 (dark-first) |
| Documentation, journals, publishing | 2 |
| Personal productivity, wellness, learning | 3 |
| Portfolios, agencies, brands | 4 or 9 |
| Field operations, hardware, safety status | 5 |
| Monitoring, logs, trading, long sessions | 6 |
| Children, creative tools, communities | 7 |
| Premium retail, private banking, hospitality | 8 |

## 1. Technical instrument

- Use for: developer tools, launchers, consoles, admin panels, anything read in short bursts while working.
- Avoid for: consumer, emotional or editorial products.
- Palette, light: canvas #F6F7F9, surface #FFFFFF, text #15181E, muted text #556070, control border #7B8594 (3.73:1, UI only), divider #D9DEE5 (decorative only), accent #2563EB with text #FFFFFF, success #15803D, warning #92400E, danger #B42318 (text on white).
- Palette, dark: canvas #13161B, surface #1A1E25, text #E7EAF0, muted text #A3ABB8, accent #7DA2FF with text #0B1020.
- Type: system UI stack at 14px and 1.5 line-height. Mono (Cascadia Code, Consolas) at 12 to 13px for paths, numbers and logs. Tabular numerals in every numeric column.
- Shape: radius 4 to 6px, 1px borders, elevation none or one level.
- Density: compact. Rows 28 to 32px.
- Motion: 120 to 160ms ease-out on state changes. No entrance choreography.
- Signature: a status rail or log pane where every value has units and aligns in columns.

## 2. Warm editorial

- Use for: long-form reading, journals, documentation, content sites, publishing tools.
- Avoid for: dense operations and dashboards.
- Palette: paper #F7F4EE, ink #1F1B16, muted text #5C554B, rule #D9D2C5 (decorative), accent #8A2F1D with text #FFFFFF. Dark: canvas #1A1714, text #EDE7DC.
- Type: a text serif for body and display (Georgia on Windows, Iowan Old Style on macOS, or a self-hosted serif). A humanist sans only for UI labels. Body at 17 to 18px, line-height 1.6 to 1.7, measure 60 to 72 characters. Wide measures want the taller line-height (line-height and measure are proportional, Refactoring UI, refactoringui.com/previews/line-height-is-proportional).
- Shape: radius 2 to 4px. Hairlines only for section breaks.
- Motion: none beyond link underlines and focus. No page transitions.
- Signature: a large headline with a deck beneath it, generous vertical rhythm on an 8px base, and no numbered badges.

## 3. Calm consumer

- Use for: personal productivity, notes, wellness, learning, habit tracking.
- Avoid for: data-heavy work and anything that needs fast scanning.
- Palette: canvas #FAFAF7, surface #FFFFFF, text #1F2421, muted text #56635E, accent #0F766E with text #FFFFFF. Dark: canvas #101412, text #E6EEEB, accent #5EC7B7 with text #0B1210.
- Type: a humanist or geometric sans (a system stack is acceptable). Body at 16px, line-height 1.55 to 1.6. Headings at weight 600.
- Shape: radius 12 to 16px with nested radii, one soft elevation, 1px borders. The soft shadow offsets vertically, light from above, instead of inflating blur (Refactoring UI, "Offset your shadows").
- Motion: 200 to 260ms ease-out for expanding and confirming. Success feedback is gentle.
- Signature: one generous state (a calm summary or an illustration), with everything else kept quiet.

## 4. Swiss grid

- Use for: brand sites, portfolios, product marketing, print-like documents.
- Avoid for: form-heavy applications and dense tables.
- Palette: paper #FFFFFF or #F2F2EF, ink #111111, muted text #555555, accent #D6261B (5.06:1 on white, so it also works for text) with text #FFFFFF.
- Type: one grotesk family, self-hosted (Archivo or Familjen Grotesk), or Helvetica Neue where it is installed. Headlines at weight 600 to 700 with tight leading. Text at 17 to 18px.
- Shape: radius 0, 1px rules, no shadows.
- Motion: one reveal on load. No hover lift.
- Signature: an oversized headline set on a 12-column grid, flush left with a ragged right edge. The accent appears only on the primary action. Compose on the single spacing scale from `layout-and-motion.md`, fixed before designing (Refactoring UI, "Establish a spacing and sizing system").

## 5. Industrial utilitarian

- Use for: field operations, hardware panels, equipment control and safety-relevant status views.
- Avoid for: consumer and playful products.
- Palette: graphite #1C1E21, panel #26292E, text #E9E7E2, muted text #A9ADB3, amber accent #F5A524 with text #111111, status green #4ADE80, danger #FF6B6B.
- Type: a condensed or DIN-style face for labels (Bahnschrift ships with Windows 10 and later), Segoe UI for text, and a mono face for values. Uppercase labels are acceptable here with 0.04 to 0.08em tracking.
- Shape: radius 0 to 2px, 2px borders, control outlines always visible.
- Motion: 80 to 120ms, or none. Status changes by color and shape, never by animation.
- Signature: labelled gauges and readouts. Hazard stripes only for real warnings.

## 6. Night-first ops

- Use for: logs, monitoring, telemetry and trading views used for long sessions.
- Avoid for: long-form reading and bright outdoor use.
- Palette: base #0F1115, raised #161A21, overlay #1E232C, border #2C3340. Text #E6E9EF, muted text #98A1B2 (on #161A21), accent #7AA2FF with text #0A0F1F, success #5EE0A0, warning #F5C25B, danger #FF7A7A. Muted text steps toward the background hue, not a neutral grey dropped on it (Refactoring UI, "Don't use grey text on colored backgrounds").
- Type: UI sans at 13 to 14px. Mono at 12 to 13px for numbers and logs, with tabular numerals.
- Shape: radius 6px. Depth comes from the surface ladder, not shadows.
- Motion: 120 to 160ms. Live values update their content without animating. No pulsing or blinking indicators.
- Signature: a timeline or sparkline strip with consistent units, and status chips where each state has both a shape and a color.

## 7. Playful expressive

- Use for: children's learning, creative tools, casual games and community apps.
- Avoid for: finance, medical and dense data.
- Palette: base #FFF8EC, ink #2B2140, coral #FF6B5B as a fill with ink text, sunflower #FFC93C as a fill with ink text, mint #35C797 as a fill with ink text. Sky #2F8FE8 is for graphics and illustration only, since it fails as text on white (3.38:1). Use no more than three hues at once.
- Type: a rounded display face, self-hosted (Nunito or Fredoka), for headings and text. Body at 17 to 18px for young readers.
- Shape: radius 16 to 24px, soft shadows tinted to the base color. Touch targets of 44px or more.
- Motion: springy but short, 200 to 300ms. With reduced motion, keep the feedback and drop the bounce.
- Signature: a character or mascot in the empty and success states, with copy kept literal and clear.

## 8. Refined luxury

- Use for: private banking, hospitality, premium retail, galleries.
- Avoid for: dense interfaces and anything that needs quick scanning.
- Palette: ivory #F8F5EF, ink #17140F, muted text #6B6255, hairline #DDD5C7 (decorative), bronze #7A5A2B with text #FFFFFF. Dark: canvas #0F0E0C, champagne #E2CFA6 as text or accent.
- Type: a high-contrast serif for display, self-hosted (Cormorant or Playfair Display), with a neutral sans for UI. Generous leading. Small caps labels only when short, at 0.06 to 0.1em tracking.
- Shape: radius 0 to 2px, hairline rules, no gradients.
- Motion: one slow reveal at 400 to 600ms ease-out. Everything else is instant.
- Signature: oversized numerals or initials, asymmetric whitespace, and one accent used only for the primary action.

## 9. Raw brutalist

- Use for: developer-facing sites, zines, art projects and deliberately confrontational brands.
- Avoid for: medical, finance and enterprise products, where the accessibility floor needs more care than this style gives.
- Palette: paper #F4F1E8, ink #000000 (pure black is deliberate here), accent #FF3B00 used as a fill with ink text (5.88:1). Do not use #FF3B00 as text on paper (3.16:1).
- Type: a heavy grotesk or a mono face at large sizes, with tight tracking on headlines.
- Shape: radius 0. Visible structure is the design.
- Motion: abrupt step transitions of 0 to 120ms. Hover moves the element 2 to 4px and shrinks its offset shadow.
- Signature: the grid and borders as the composition, with controls that look like controls.
