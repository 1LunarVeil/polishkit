# PolishKit

An agent skill for making visual decisions that are specific to a product, and for checking them with something other than an opinion. It is built to run alongside the official `frontend-design` skill: that skill sets the stance, and this one supplies the decision rules, the precedent data and the checks.

Works in Claude Code, ZCode, Cursor, OpenAI Codex, VS Code Copilot and any agent that reads the Agent Skills format (`<skill-name>/SKILL.md`). It needs Python 3.9 or newer; no third-party packages, and no network calls from any script. Visual capture uses a Chromium-family browser already installed on the machine, if there is one.

## What it is for

Ask an agent to "make this look better" and you usually get one of two failures: a page that looks like the average of everything the model has seen, or a page that quietly breaks a floor nobody checked. This skill attacks both, and then makes the agent prove the result by looking at it.

Concretely, it changes four things about how an agent works on UI:

1. **It forces a brief before styling.** Subject, audience, density, and three things the design must not look like. Then a direction with a stated reason, not a mood board.
2. **It supplies numbers instead of adjectives.** Nine directions with starting palettes whose contrast values were computed; spacing, type and motion scales; a state matrix; accessibility floors.
3. **It gives the agent tools to check its own work.** Contrast, precedents, a tell scanner, and a render-capture-diff loop.
4. **It makes claims falsifiable.** If the agent says a change moved a section, the diff must cover that section. If it did not capture the UI, it must say "not visually verified" instead of describing a page it never saw.

## What it can do

| Capability | How |
|---|---|
| Decide a visual direction for a new or bland UI | `SKILL.md` steps 1-4, `references/principles.md`, `references/directions.md` |
| Choose colors that pass contrast, including dark theme | `references/color-and-type.md` + `scripts/wcag.py` (hex, rgb, oklch) |
| Look up precedents for a product type | `scripts/design_lookup.py` over eight vendored datasets, with palettes auto contrast-checked |
| Get the desktop platform checklist for a target OS | `design_lookup.py --platform macos|windows|desktop`: window chrome, platform units, control sizes, materials and accelerators from `references/native-feel.md`, alongside the web UX rows |
| Find generic "AI slop" tells and craft defects in code | `scripts/slop_scan.py`, 20 checks (17 line rules plus focus, reduced-motion and raw-colour checks), severity-ranked, exit 1 on blocking |
| Capture the real rendered UI at several sizes and scales | `scripts/visual_capture.py`, waits for a settled frame, reports console errors and blank frames |
| Capture dark theme, full page, element and hover/focus states | `scripts/visual_capture.py` over CDP: real `prefers-color-scheme` emulation, clipped and interaction views; falls back to plain screenshots and says so |
| Audit the token file and raw-value leaks | `scripts/token_lint.py`: definition-site contrast, `RAW-LEAK`, missing semantic roles, unused tokens, off-scale values |
| Audit every visible text pair in the rendered page | `scripts/page_audit.py`: measurable verdicts separated from uncertain ones (gradients, images, occlusion) |
| Audit the keyboard path and the focus ring as rendered | `scripts/keyboard_audit.py`: real Tab presses, traps, `tabindex="-1"` controls, overlay-obscured focus, hover-only contrast failures, and the indicator's pixel contrast against the control it surrounds (2.1.1, 2.1.2, 2.4.7, 2.4.11, 1.4.11; 2.4.13 as AAA evidence) |
| Prove the layout survives a user's text-spacing overrides | `scripts/text_spacing.py`: applies WCAG 1.4.12's four values and reports clipped cards, `max-height` boxes, single-line labels losing text and text runs that only collide after the override |
| Prove the layout reflows at 320 CSS px | `scripts/reflow.py`: loads the page at three widths, reports horizontal scrolling (1.4.10) and the elements that cause it, honours the two-dimensional exception, and takes a 1.4.4 text-scale reading |
| Audit Chinese line-breaking as rendered | `scripts/cjk_breaks.py`: walks each rendered line and reports clreq §6.1.1 violations (a closing bracket starting a line, an opening bracket ending one) plus the `word-break: break-all` that usually causes them |
| Read how a page allocates attention, then judge it yourself | `scripts/expression_audit.py`: the loudest first-screen element, how much of its own column is filled before the fold, the size ladder and the text density — reported, with the questions they raise, and never as a score. Imagery in the band is reported as uncertain because a rectangle cannot tell a photograph from a void |
| Read contrast through a draft lens; test hue-dependent meaning | `wcag.py --apca` (draft APCA Lc, supplementary) and `scripts/color_sim.py` (Machado 2009 CVD simulation with a pair-collapse check) |
| Prove what a change actually did to the screen | `scripts/image_diff.py`, zero-dependency PNG decode, changed region and ratio, plus a baseline directory report |
| Review an existing UI and get prioritized findings | `references/critique.md` (ten pillars) and `/design-review` |
| Run every mechanical check and get one merged verdict | `/polish-audit`: source checks plus both rendered audits, with blocking, important, review, uncertain and not-checked stated separately |
| Compare all three rendered audits across several pages | `tools/crosscheck.py URL...`: one table of failures and uncertain counts per clause, so a page that is clean in one dimension and unmeasured in another is visible at a glance |
| Apply the rules inside a desktop or WebView app | `references/desktop-app.md` |

## What it cannot do

Stated plainly, because the alternative is users discovering it later.

- **It does not generate designs.** It gives a model rules, data and checks; the model still does the designing.
- **It does not judge beauty.** It measures contrast, catches patterns and shows you before and after. Whether the result looks good remains a human call.
- **It is not a regression gate.** `image_diff.py` never fails on difference: a deliberate redesign may change every pixel. It answers "did this change", not "is this better".
- **It does not ship a browser.** Capture needs Chrome, Edge or Chromium already installed, found by absolute path. Without one it exits 2 and says so.
- **It does not see interaction.** Hover, focus rings, open menus and mid-transition states need a driving tool (Playwright and similar) to reach; this skill captures landed states only.
- **Its palette data is a starting point.** Of 192 palette rows, 173 have a border below 3:1 and 30 have a primary fill below 3:1 against their background. Only one row has a failing text pair. Check UI pairs before shipping.

## Credits

This plugin paraphrases and synthesizes others' work, and says so.

- **Anthropic's `frontend-design`** sets the stance this skill builds on, and its advice to take screenshots is the origin of the visual loop.
- **ui-ux-pro-max-skill** (Next Level Builder, MIT) supplies the eight CSV datasets, vendored unchanged and attributed in `THIRD_PARTY_NOTICES.md` and `skills/polishkit/data/PROVENANCE.md`.
- **claude-dev-kit** (pillip, MIT) is the precedent for capture scripts and pixel-diff acceptance; the implementations here are independent.
- **buildwithclaude**, the **"4 design skills"** article, the **AI UX Playground** catalogue and the **Learning AI** chapter contributed framing and workflow ideas, rewritten rather than copied.
- Per-item detail, including what was rejected and why, is in `skills/polishkit/references/sources.md`.

`frontend-design` is what this plugin is meant to be used with. It does not replace it.

## How this differs from ui-ux-pro-max

The eight CSV datasets are vendored from ui-ux-pro-max-skill, so the data overlaps by design. What surrounds the data does not:

- ui-ux-pro-max ships a CLI engine and wide catalogues (icons, Google Fonts, landing and React performance content). This plugin vendors only the eight design datasets, rewrites the lookup with name-weighted matching, and adds three things ui-ux-pro-max does not have: automatic WCAG contrast checks on every palette it reports, a severity-ranked tell scanner with a CI exit code, and the render-capture-diff loop that proves a change landed on screen.
- If both are installed, both skills may fire on a UI task and the precedent lookup runs twice. Nothing conflicts — names, commands and data paths are separate — but one of the two is redundant; installing this plugin alone is enough.

## Install

### Any agent that supports Agent Skills

Copy the skill folder so that `SKILL.md` sits directly inside a folder named after the skill:

```
git clone https://github.com/1LunarVeil/polishkit
cp -r polishkit/skills/polishkit ~/.claude/skills/
```

| Agent | Project scope | User scope |
|---|---|---|
| Claude Code | `.claude/skills/polishkit/` | `~/.claude/skills/polishkit/` |
| Cursor | `.cursor/skills/polishkit/` or `.agents/skills/...` | `~/.cursor/skills/...` or `~/.agents/skills/...` |
| OpenAI Codex | `.codex/skills/polishkit/` | `~/.codex/skills/polishkit/` |
| VS Code Copilot | `.github/skills/polishkit/` | `~/.copilot/skills/polishkit/` |

The folder name must match the `name` in the frontmatter. The most common install failure is one extra directory level, so that `SKILL.md` ends up nested one level too deep.

Agents that share folders also see each other's installs: Claude Code and Copilot both read `.claude/skills/`, and Cursor, Copilot and Codex can read `.agents/skills/`. Installing once into `~/.agents/skills/` therefore covers several agents on the same machine.

With the `skills` CLI, install from this repository instead of copying:

```
npx skills add 1LunarVeil/polishkit --skill polishkit
```

### Claude Code plugin

```
/plugin marketplace add 1LunarVeil/polishkit
/plugin install polishkit@polishkit
```

This also installs the two slash commands. Restart the session after installing.

### ZCode plugin

In Plugin Marketplace, add this repository's directory, or the local path to a clone, as a marketplace source, then install **PolishKit**. The manifest is in `.zcode-plugin/plugin.json`.

### No install: paste and go

If you only need the rules for one task, give the agent `skills/polishkit/SKILL.md` plus the reference file the task needs. The scripts are optional but recommended.

## Use

The skill activates from its description when you ask for UI work, or you can name it. Typical prompts:

- "Build the settings page. First write the brief and three things this must not look like, then give two directions, pick one, and show the token block."
- "Review this UI: find the generic tells and the accessibility floors it breaks."
- "The current UI looks bland. Restyle it without breaking the token contract."

With commands available:

- `/design-direction saas dashboard for a local model launcher, dark first`
- `/design-review src/pages/settings`

Expected shape of a response: a short brief, a direction with a reason, a token block, and a verification section listing the commands run and their results.

## Tools

Run from the repository root:

```
python skills/polishkit/scripts/wcag.py "#1f2937" "#ffffff" "#556070" "#f6f7f9"
python skills/polishkit/scripts/design_lookup.py "saas dashboard" --ux --motion
python skills/polishkit/scripts/slop_scan.py path/to/frontend/src
python skills/polishkit/scripts/visual_capture.py http://127.0.0.1:5173 --out shots --matrix
python skills/polishkit/scripts/image_diff.py shots/wide-1440x900-light@1.png shots2/wide-1440x900-light@1.png
```

If you installed the skill into an agent, run the same scripts from the installed skill folder, for example `~/.claude/skills/polishkit/scripts/`.

- `wcag.py FG BG ...` prints the contrast ratio for each pair, with verdicts for AA text (4.5:1), large text and UI (3:1) and AAA text (7:1). It accepts `#hex`, `rgb()` and `oklch()`. Out-of-gamut OKLCH values are clipped to sRGB, the same way a browser clips them. `--apca` adds a draft APCA Lc value, marked as supplementary; the WCAG verdicts stay the gate.
- `design_lookup.py "<keywords>"` returns matching product types, styles, a contrast-checked palette, type pairings and reasoning rules from the vendored data. Chinese keywords work through `data/zh-keywords.csv`; failed palette pairs come with suggested adjusted values marked "not applied". Use `--ux`, `--motion` and `--charts` for extra sections.
- `slop_scan.py PATH ...` reports generic tells and craft defects as `blocking`, `important`, `review` or `polish`, honours line-level `/* slop-ignore: RULE-ID */` and a project `.sloprc`, and has a `--changed` mode for git. It exits with status 1 when a blocking finding exists, so it can gate CI. Use `--json` for machine output.
- `token_lint.py PATH ...` audits token files: definition-site contrast, raw-value leaks with "use var(--token)" suggestions, missing semantic roles, unused tokens and off-scale values.
- `visual_capture.py URL --out DIR` shoots the page at one size, or a standard matrix with `--matrix` (1440x900, 1440x900 at 150%, 1100x720, 390x844). Over CDP, `--dark` really emulates `prefers-color-scheme`, and `--full-page`, `--element`, `--hover`, `--focus` capture the states plain screenshots cannot; any CDP failure falls back to the legacy engine and the JSON says which engine ran. It shoots repeatedly until two consecutive frames are identical, so a half-rendered shell is not mistaken for a design. Exit 2 means no browser was found; exit 3 means the URL was rejected (only http/https, no leading `-`, and no private addresses without `--allow-private`).
- `page_audit.py URL` walks the rendered page and audits every visible text pair: measurable pass/fail, and an explicit `uncertain` class for gradients, images, blend modes and occlusion instead of a guessed verdict.
- `keyboard_audit.py URL` presses Tab for real, stop by stop, and screenshots each stop focused and unfocused. It reports controls the keyboard cannot reach (2.1.1, including `tabindex="-1"` on something interactive), traps (2.1.2; a modal dialog's cycle is a review, not a failure), a missing or unperceivable focus ring measured against the control it surrounds (2.4.7 / 1.4.11), focus hidden under author content (2.4.11), and text contrast that only fails on focus or hover (1.4.3). 2.4.13's area and same-pixel readings are printed as AAA evidence and never gate the exit status. `--measure N` bounds how many stops are photographed and the report names the ones walked but not measured; exit 1 means a measurable keyboard or focus FAIL.
- `text_spacing.py URL` applies WCAG 1.4.12's four user overrides and compares the two states: line height 1.5×, paragraph gap 2×, letter spacing 0.12×, word spacing 0.16×. It reports clipped boxes (including the usual case where the clipping box is an ancestor), `max-height` blocks that now need more room, single-line labels that lose another em of text, and sibling text runs that collide only after the override. A page need not ship those values; it must survive them. Exit 1 on a measurable failure.
- `tools/crosscheck.py URL ...` runs `page_audit`, `keyboard_audit`, `text_spacing`, `reflow`, `cjk_breaks` and `expression_audit` against each page and prints one table: failures and uncertain counts per clause. It exists so a page that is clean in one dimension and unmeasured in another is visible without reading three reports in a row. An audit that cannot run shows as `UNVERIFIED`, never as a zero.
- `color_sim.py COLOR ...` simulates protanopia, deuteranopia and tritanopia (Machado 2009); `--check FG BG` reports whether a pair's contrast collapses under simulation.
- `image_diff.py A.png B.png` decodes PNG with the standard library and reports the changed pixel count, ratio and bounding box; two directories run a baseline report. `--stats` summarises one or two images instead.

On Windows, use `py -3` if `python` is not on PATH.

## The visual loop

Code review cannot see a page that renders as a bare shell, content that stops two thirds down the window, or a transition caught mid-frame. The loop is:

1. **Render.** Start the app, or serve the built frontend statically on loopback. Most UIs render their shell and empty states without a backend.
2. **Capture.** `visual_capture.py` with `--matrix`. Look at the images.
3. **Change.**
4. **Capture again** to a second directory and `image_diff.py` the pairs. If the changed region does not match what you claimed to change, the claim is wrong. Then look again: the diff proves something changed, not that it changed for the better.

Why the tool waits for identical frames: on a real app, a fixed 4-second wait captured a half-rendered shell (204 colours) at 1440x900 while the same page was complete (837 colours) after a longer wait, and a 390px viewport needed three attempts to settle. File size was no help: the shell was a 12 KB PNG, comfortably "non-empty". Details in `references/visual-review.md`.

## What is inside

```
skills/polishkit/
  SKILL.md                  workflow, floors, taste rules, the choice test
  references/
    principles.md           decision order and the brief template
    directions.md           nine directions with verified starting tokens
    color-and-type.md       palettes, dark theme, contrast, scales, fonts, CJK
    layout-and-motion.md    spacing, density, radii, elevation, motion
    components-and-states.md  state matrix, copy rules, the break test
    desktop-app.md          WebView and desktop app rules
    anti-slop.md            tells, why they read as defaults, questions to ask
    critique.md             review procedure, ten pillars, severity, output
    visual-review.md        render, capture, read, re-diff
    sources.md              where each rule came from, and what was rejected
  scripts/                  wcag, design_lookup, slop_scan, token_lint, visual_capture,
                            image_diff, page_audit, keyboard_audit, text_spacing, reflow,
                            cjk_breaks, expression_audit,
                            color_sim, cdp
  data/                     eight MIT-licensed CSV files from ui-ux-pro-max
commands/                   optional slash commands
tests/                      standard-library unit tests and fixtures
```

## Verification

```
python -B -m unittest discover -s tests -v
```

The suite covers the contrast math against published reference values, the draft APCA implementation against anchors derived from the quoted source, OKLCH agreement with sRGB, the Machado simulation matrices (grey invariance, the red-to-olive anchor), name-weighted product matching, every scanner rule and token check against fixtures that contain each defect, the multi-line and suppression plumbing, PNG decoding and exact diff geometry on generated fixtures, size-mismatch and non-PNG handling, decompression-bomb and oversized-dimension rejection, the capture tool's URL validation (option-like strings, non-http schemes, private and link-local addresses, the explicit override), the WebSocket/CDP protocol layer at byte level (handshake vector, frame layouts, fragmentation, limits, loopback guard), and the keyboard audit's deciding logic and pixel arithmetic (bucket assignment, trap endings, indicator measurement on hand-built frames). No test needs a network connection or a browser; the PNG fixtures are generated by `tests/make_fixtures.py`.

## Known limitations

- The scanner finds patterns. It cannot judge taste, and each finding needs a human decision. For example, `outline: none` only matters when nothing replaces the focus style.
- The palettes are starting points. Measured across all 192 rows, only one has a failing text pair, but 173 have a border below 3:1 and 30 have a primary fill below 3:1 against their background. Check the UI pairs before shipping.
- Visual capture reaches hover, focus, element and full-page states over CDP; the legacy fallback engine only lands final states, and the JSON always says which engine ran. Open menus and mid-transition frames still need a driving browser tool.
- `keyboard_audit.py` needs a browser and photographs a bounded number of stops (`--measure`); stops beyond the budget are walked but not measured, and the report says so. It does not emulate `prefers-reduced-motion` or forced-colors. A page that restores focus after `blur()` is reported as uncertain rather than verdicted, because the second frame is then not an unfocused frame.
- `image_diff.py` is not a regression gate and decodes only non-interlaced 8-bit PNG. Other PNG variants are reported as unsupported rather than compared wrongly.
- Without a browser installed, the visual step cannot run. The skill then requires the review to say "not visually verified" rather than describing a page it never saw.
- Thresholds for durations, density and breakpoints are heuristics from practice, not standards. WCAG items are marked as such in `references/sources.md`.
- The skill has not been benchmarked against `frontend-design` alone. Its verifiable claims (contrast values, scanner hits, diff geometry) are tested; "does UI look better" is not something these tests can answer.

## Compatibility notes

- `SKILL.md` has a `description` in its frontmatter, because agents choose skills by it. Some early design skills shipped without one and were never selected automatically.
- The scripts are Python 3.9 or newer, standard library only, and print UTF-8 on all platforms.
- No script calls the network. The capture tool navigates only the URL you pass, after validating its scheme and address.
- Nothing writes outside the capture output directory, so the tools are safe to run against an untrusted repository.

## Benchmark

`benchmark/` holds a 5-brief, three-condition pilot measured with the plugin's own tools (page_audit, slop_scan, visual_capture): **bare model** (no design guidance) vs **frontend-design** alone vs **frontend-design + PolishKit**.

| Metric | bare | frontend-design | + PolishKit |
|---|---|---|---|
| Rendered-page contrast failures | 48 | 101 | **0** |
| Scanner findings | 54 (27 important) | 88 (45 important) | **2 (review)** |
| Pages with zero state markers | 1 | 2 | **0** |
| Renders that never settle | 1 | 3 | **0** |

The bare condition's own output converges on the exact AI-slop recipe the stance warns about (cream + terracotta + serif, unbidden). Full tables, protocol and honest limitations: `benchmark/RESULTS.md`. The maintainer's verdict: floors held, aesthetics at parity with a distinct, bolder style.

## License

MIT for the plugin's code and documentation, see `LICENSE`. The CSV data is MIT-licensed by Next Level Builder; see `THIRD_PARTY_NOTICES.md`.
