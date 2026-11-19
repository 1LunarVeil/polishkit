# Sources

Each rule in this skill was either checked against a standard, measured with the scripts, or taken from one of the sources below and rewritten. Nothing here is copied verbatim except the vendored data in `data/`, which keeps its MIT license.

## Standards

- WCAG 2.2 (W3C): the contrast minimums (1.4.3, 1.4.11), text resize and reflow (1.4.4, 1.4.10), text spacing (1.4.12), focus visibility and appearance (2.4.7, 2.4.11), target size (2.5.8), flashing (2.3.1), animation from interactions (2.3.3). The large-text definition (18pt, or 14pt bold) is from the same document.
- Color-vision safe palette: the Okabe-Ito set, from Okabe and Ito's color universal design guidance.

## Resources reviewed for this plugin

1. frontend-design, Anthropic (the official Claude Code design skill, version 1.1.1 at the time of writing). Used for the stance: commit to a direction, avoid the defaults nobody chose, plan then review then build then critique, and the AI-cluster list of defaults. Its sentence "taking screenshots to review if your environment supports it" is the origin of the visual loop in `visual-review.md`; version 0.1.0 of this skill read that line and then wrote the loop as an optional aside, which was a mistake. Its text is not copied beyond that idea. Its terms are in its own LICENSE.txt.

2. ui-ux-pro-max-skill, Next Level Builder, MIT, copyright 2024 Next Level Builder. Repository: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill (HEAD bf41cbc when cloned for this plugin). Used:
   - Eight CSV data files, vendored unchanged into `data/` with the MIT notice (see `data/PROVENANCE.md`).
   - The idea of joining product types to styles, palettes and reasoning rules.
   Not used: the Python engine (we wrote a smaller lookup that adds name-weighted matching and contrast checks), the landing, app-interface, react-performance, icon and Google Fonts data, and the CLI.

3. claude-dev-kit, pillip, MIT, copyright 2025 pillip. Repository: https://github.com/pillip/claude-dev-kit. Used as a source for the critique pillars and state coverage, and for desktop items: shortcut hints with the platform modifier, focus restoration after dialogs, density judged by visible rows, and the keyboard path for resizers. It also contains the capture pattern the visual loop is built on: `scripts/capture_reference.py` and `scripts/capture_source.py` (screenshot capture) and a pixel-difference acceptance threshold in `agents/qa-designer.md`. Version 0.1.0 of this skill filed those under "repo-specific workflow" and dropped them; that judgement was wrong, and they are the direct precedent for `visual_capture.py` and `image_diff.py`. The implementations here are independent (no code was copied), but the workflow idea came from there. Its numeric claims were checked and rewritten. Two conflicts were resolved in favour of the WCAG values: iOS target size (44pt in one file, 48pt in another) and the placeholder contrast (3:1 in one file, 4.5:1 for text in another).

4. buildwithclaude, davepoon, MIT, copyright 2025 davepoon. Repository: https://github.com/davepoon/buildwithclaude. Reviewed and rated low for this purpose: several contrast examples were wrong, its guidance was WCAG 2.1 only, and its font advice contradicts itself. Used only for the idea that a recipe copied from a reference becomes the next default. No text was taken.

5. "4 design skills that improved my UIs", Aridan Martin, https://aridanemartin.dev/blog/design-skills-for-developers/. Used for the framing that AI-generated UI suffers from a taste problem, for the principles of one dominant color with a sharp accent, typography carrying most of the personality, one orchestrated animation over scattered ones, and spatial surprise used sparingly, and for the practice of reading a brief document before generating. Its key instruction for this update — use design skills "for reviews, not just generation", because asking an agent what is visually weak produces better feedback than generation — is the reason the loop closes with re-capture and comparison rather than ending at the first screenshot. Impeccable's rule set is mentioned in that post, but its rules were not used; the scanner rules here were written independently.

6. "Agent Skills for Designers", AI UX Playground, https://aiuxplayground.com/skills/for-designers. A catalogue of designer-oriented skills. Used as a checklist of workflow ideas rather than content: expanding a happy path into loading, empty, error, disabled, focus, partial and recovery states; testing with worst-case data; checking spacing against a 4 and 8 grid; building palettes in OKLCH with semantic tokens; a motion frequency gate; blocking, important and polish severities; and a DESIGN.md-style brief. Its live-browser entries are the second precedent for the visual loop: Scroll Craft "verifies every scroll frame and contrast in a headless browser", Extract Design System extracts with Playwright, and Impeccable advertises "live browser iteration". None of their code or text is used; the loop is implemented from scratch on the standard library.

7. "Make Interfaces Beautiful with LLMs and Skills", Learning AI (aiecos), https://learning.aiecos.ai/en/stage-2/frontend/llm-skills-beautiful/. Used for the five-dimension vocabulary (typography, color, layout, motion, details) in the brief, and for the principle that a named aesthetic direction beats a generic prompt. Caveats: several example templates in the chapter (Inter for body text, grey shadows, a glassmorphism recipe) are the defaults this skill warns against, so none was adopted. The URL ending in `/plugin-creator` returns 404 on the English site; the skill-creation material is in the chapter's section 6, "Create your own design system skill".

8. APCA 0.0.98G-4g, Andrew Somers / Myndex, https://github.com/Myndex/apca-w3 (W3-collaboration license). Used for the supplementary `--apca` output in `scripts/wcag.py`: the SA98G constants and the BoW/WoB branch structure were quoted verbatim from `src/apca-w3.js` and the anchors re-derived (black on white +106.0, white on black −107.9, #767676 on white +71.6). Status: APCA is a draft and this output is supplementary only — the WCAG 2.2 ratios in the same line remain the only gate. Not used: the font-size/weight lookup table interpolation and the full ARC criterion; the printed guidance compresses the published Lc levels (90/75/60/45/30/15) into one label.

9. Machado, Oliveira and Fernandes, "A Physiologically-based Model for Simulation of Color Vision Deficiency", IEEE Computer Graphics and Applications 29(1), 2009, https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/CVD_Simulation.html. Used for the severity-10 (full dichromacy) protanopia, deuteranopia and tritanopia matrices in `scripts/color_sim.py`, applied in linear RGB as the model requires. Not used: the ten partial-severity interpolation tables and the bisector-correction variants. Grey invariance (the matrix rows sum to 1) is pinned by a test; pure red under deuteranopia lands in the olive range, which is the behavior the palette checker relies on when it warns that a hue pair has collapsed.

## Internalized sources (2.0)

Twenty further sources were read, extracted and internalized across batches A–F and the platform track (per-source process notes live in the repository's `notes/batch-*` files; the rules below name where each landed):

- **Standards & systems**: WCAG 2.2 non-contrast clauses (2.5.8, 4.1.2/1.1.1) and WAI-ARIA APG → `page_audit.py`'s TARGET-SIZE, ARIA-NAME and HEADING-ORDER checks; GOV.UK Design System, U.S. Web Design System and IBM Carbon → `token_lint.py`'s SEMANTIC-LEAK and primitive/semantic layer models, `critique.md` pillar 5; Apple HIG and Microsoft Fluent 2 → `native-feel.md`; The A11Y Project → heading and naming checks. Where a source contradicted a plugin floor, the floor won and the tension is recorded (NNG's loading-indicator guidance vs the plugin's 200–300ms; HIG's 44pt hit region vs WCAG 2.5.8's 24px — the 44pt is documented as a platform expectation, not a gate).
- **Judgment**: Refactoring UI (ten concrete judgments, from the official site and the authors' public article — the book is paywalled and the boundary is recorded), Radix UI primitives (dialog/menu/tabs/tooltip/toast interaction contracts in `components-and-states.md`), shadcn/ui token discipline → `anti-slop.md`「Judgments worth stealing」and `directions.md` citations.
- **Typography**: W3C clreq (¼-em mixed-script spacing, 行首行尾禁则 three processing tiers, punctuation squeeze as progressive enhancement, the §5.5.3.2 ruby line-height anchor) → new `cjk-typography.md`; Better Web Type (line-height as the rhythmic base unit) as the rhythm anchor. clreq gives no UI numbers; the existing heuristics stay heuristics, honestly labelled.
- **Motion**: Material Motion 3 → the mapping section in `layout-and-motion.md`. Verified finding: the plugin's `--ease-out` cubic-bezier(0.2, 0, 0, 1) is character-for-character M3's `standard` curve, and M3 itself prescribes standard as the web fallback for emphasized easing. m3.material.io is JS-rendered; values were extracted from a real rendered session and quoted verbatim.
- **Data visualization**: D3/Tufte data-ink (grounded via Boyd's University of Michigan chapter after d3js.org proved principle-free) → new `charts.md`; the Okabe-Ito palette was re-verified against the origin figure, seven of seven hex values exact. `charts.md` also adjudicates the tension between the vendored palettes and the OKLCH role system: the role system wins, CSV literals are precedent evidence.
- **Empirical**: Nielsen Norman Group and Baymard → three citations landed (line length 50–75/≤80, CJK ≤40, touch-target physical floor), twelve plugin heuristics honestly marked "no empirical source found (checked 2026-11-07)" in the batch notes. A widely-circulated "Baymard touch-target" article was verified 404 and re-attributed to UX Movement 2012.
- **Expression**: the expression layer itself (`expression.md`) synthesizes the judgment sources into the checklist that benchmark evidence showed was needed — pages were compliant and inert without it.

## Keyboard and focus audit (2.1)

Normative text for every clause `scripts/keyboard_audit.py` reports was read
from the W3C Understanding documents on 2026-11-19, not recalled:

- **2.1.1 Keyboard (A)** — https://www.w3.org/WAI/WCAG22/Understanding/keyboard
- **2.1.2 No Keyboard Trap (A)** — the trap the audit tests for; a modal
  dialog's internal cycle is expected behaviour, so it is reported as a review
  naming the container.
- **2.4.7 Focus Visible (AA)** — https://www.w3.org/WAI/WCAG22/Understanding/focus-visible
- **2.4.11 Focus Not Obscured (Minimum) (AA)** — https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.
  Verbatim requirement: "When a user interface component receives keyboard
  focus, the component is not entirely hidden due to author-created content."
  The word *entirely* is why the audit passes a partly covered control, and its
  Note 2 ("If the user can reveal the focused component without advancing the
  keyboard focus") is why a scrollable-into-view control is not reported.
- **1.4.11 Non-text Contrast (AA)** — https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.
  "The visual presentation of the following have a contrast ratio of at least
  3:1 against adjacent color(s)". This is the clause behind the plugin's own
  3:1 focus-indicator floor, and it is what the pixel measurement checks: the
  indicator against the colours it actually touches.
- **2.4.13 Focus Appearance (AAA)** — https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance.
  Area: "at least as large as the area of a 2 CSS pixel thick perimeter of the
  unfocused component or sub-component"; the Understanding document gives the
  rectangle form as **4h + 4w**, which is the constant this plugin uses.
  Contrast: "a contrast ratio of at least 3:1 between the same pixels in the
  focused and unfocused states". **This criterion is AAA**, so it is reported as
  supplementary evidence and never drives the exit status.

Two measurements in the tool are engineering decisions rather than quoted
thresholds, recorded here so the boundary is visible:

- **Adjacent contrast is a per-side median, and the verdict needs most sides to
  clear the floor.** Measured on hand-built indicator styles, a per-pixel
  minimum is defeated by antialiased corners: a clean 6:1 ring reported 3.07:1
  because one corner pixel blended toward the surface. A per-side median fixes
  that, but taking the *worst* side as the verdict was wrong in the other
  direction: a real page with a black 3px ring on a button carrying a black hard
  shadow merges into the shadow at 1.02:1 on one edge while the other three sit
  at 17.7:1, and 1.4.11 asks whether the state can be picked out, not whether
  every edge is perfect. The tool therefore fails an indicator only when more
  than half of its measured sides sit under the floor, and otherwise passes it
  with the caveat recorded in `note`. Verified on five real pages: two chart
  bars whose ring matched their own fill failed, two with the same ring but a
  readable majority passed.
- **The 1.4.11 adjacency check only runs on qualifying pixels** (those whose
  focused-vs-unfocused change is already at least 3:1). A ring whose entire
  change is below 3:1 has no indicator to measure and fails through the same
  clause with the "not perceivable" message.

Deliberately not covered: `prefers-forced-colors` (Windows High Contrast turns
most rings into system colours the author does not control), `prefers-reduced-motion`,
and 1.3.1 structure. None is implied by a clean audit result.

## Text spacing audit (2.2)

**1.4.12 Text Spacing (AA)** — https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html,
read 2026-11-19. The criterion is a survival test, not a design instruction:

- "Line height (line spacing) to at least 1.5 times the font size"
- "Spacing following paragraphs to at least 2 times the font size"
- "Letter spacing (tracking) to at least 0.12 times the font size"
- "Word spacing to at least 0.16 times the font size"

applied "by setting all of the following and by changing no other style
property", with "no loss of content or functionality". The Understanding
document adds plainly: "Content is not required to use these text spacing
values." So `text_spacing.py` never reports a page for shipping tighter
spacing; it injects the four values and reports what broke. The first rule of
`override_css()` is that nothing but those four properties appears in the
stylesheet — a test asserts the property set exactly, because adding `width`
or `display` would invalidate the comparison.

Three measurements in that tool are engineering decisions:

- **The pairing key is the child-index path from `<body>`, not a coordinate.**
  A coordinate key changes the moment the override reflows the page, so the
  first version compared nothing and called every page clean.
- **Clipping is tested on the element *and* its nearest clipping ancestor.** A
  paragraph inside a 48px `overflow:hidden` card reports a comfortable client
  box of its own; only the card's `scrollHeight` (96) against its
  `clientHeight` (64) shows the loss. A Range-based "text needs X, box offers Y"
  test was also written and then removed: Range height excludes the lead the
  line box adds, so it disagreed with what the browser clipped.
- **Truncation needs one em of extra required width, measured before and
  after.** A four-pixel threshold counted cells that already truncated at rest,
  which is a different defect under a different clause, and it buried the cells
  the override actually broke.

**Not covered by this tool**, and stated rather than implied: 1.4.4 Resize Text
(200% zoom) and 1.4.10 Reflow (320 CSS px) need a real zoom or a real narrow
viewport rather than a style override, and both remain manual checks.
`prefers-reduced-motion` also stays manual.

## CJK line-breaking audit (2.2.6)

**clreq §6.1.1 行首行尾禁则** — https://www.w3.org/TR/clreq/, read 2026-11-19.
The prohibition is not reimplemented here: browsers already apply it under
`line-break: auto`, and a Python copy of the character table would rot. What
`scripts/cjk_breaks.py` does is walk the rendered lines and find where the
prohibition was *broken* — by `word-break: break-all`, by an inline element
boundary, or by an authored `<br>`.

The character sets are derived from Unicode, not transcribed:

- **Forbidden at line start**: every `Pe` closing bracket, plus the terminal
  punctuation that Unicode files under `Po`. `Ps` opening brackets are legal at
  line start and are vetoed explicitly, because `Po` alone would let an opening
  quote through.
- **Forbidden at line end**: the opening brackets and opening quotes. This is
  the mirror of the rule above, and clreq states it as one requirement.

Server-side check: the page's `location.href` after load must not begin with
`chrome-error://`. A failed navigation still fires `Page.loadEventFired`, and
Chrome's own error page is a real document — auditing it reported
"依次前往 Chrome 菜单 >“" as a Chinese line-ending violation on a page whose
server had simply stopped. `cdp.PageSession` now raises before any audit runs.

Deliberately not covered: hanging punctuation (`text-spacing-trim` is still
partial), the GB 法 stricter tier, and vertical text.

## Deliberately not used

- Icon, font-catalogue and CDN metadata, and any stack-specific code (React, Next.js, Tailwind, Figma plugin APIs). They do not match a vanilla or desktop WebView UI.
- Brand assets and brand guidelines. Any brand's logo, illustrations or proprietary typeface.
- Numeric claims that could not be verified (for example, counts of styles or palettes on marketing pages).

## Verification

- Contrast values in `directions.md` were computed with `scripts/wcag.py`, which was checked against reference values: black on white 21.00:1, #767676 on white 4.54:1, #777777 on white 4.48:1, and pure red on white 4.00:1.
- The APCA implementation reproduces the anchors derived from the quoted source (black on white +106.0, white on black −107.9, #767676 on white +71.6) and follows the sign convention: dark text on light is positive.
- The Machado matrices are pinned by grey-invariance (every matrix row sums to 1, so greys survive) and by the red-under-deuteranopia anchor (pure red lands near #a39000, in the olive range).
- Scanner rules were checked against `tests/fixtures/` and against a real frontend, where they produced the findings they describe.
- The capture rules in `visual-review.md` are not theory. On a real app, a fixed 4-second wait captured a half-rendered shell (204 colours, 12 KB) at one window size while a longer wait captured the same page complete (837 colours, 61 KB), and a 390px viewport needed three attempts to settle. Those numbers are why the tool requires two identical frames instead of a delay, and why the blank test counts colours instead of file size.

## What this plugin does and does not do

Stated plainly, so nobody has to infer it from the files.

- It does not generate designs. It provides rules, precedents and checks for a model that does.
- It does not judge beauty. It measures contrast, catches patterns, and lets you compare renders before and after. Whether the result looks good is still a human call.
- It does not replace `frontend-design`; it is written to run alongside it.
- It does not ship a browser. `visual_capture.py` uses a Chromium-family browser already installed on the machine, resolved by absolute path. With none installed, it reports that and stops.
- It does not call the network. No script in `scripts/` makes a request; the capture tool navigates only the URL you pass, and refuses non-http(s) schemes and, without an explicit flag, non-public addresses.
- It does not write outside the output directory for captures, and never edits source files.
- The palette data is a starting point, not a source of truth: measured across its 192 rows, only one has a failing text pair, but 173 have a border below 3:1 and 30 have a primary fill below 3:1.

## Lineage and honesty

The visual loop (render, look, change, look again) is not an original idea of this plugin. Anthropic's `frontend-design` says to take screenshots and review them; claude-dev-kit ships capture scripts and a pixel-diff acceptance step; several catalogued skills in the AI UX Playground advertise headless-browser verification. Version 0.1.0 of this skill read all of that and implemented none of it, describing the loop as something that "needs a browser tool". That was a gap in execution, not in understanding. Version 0.1.1 closes it with two scripts written from scratch, with no third-party code and no copied text.
