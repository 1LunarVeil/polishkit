# Changelog

All notable changes to this project are recorded here. The format follows Keep a Changelog, and versions follow Semantic Versioning.

## [2.0.0] - 2026-11-08

First release under the new name — **PolishKit** (formerly `frontend-aesthetics`; the 0.1.0–0.1.3 announcements below were published under the old name). The 0.1.x line built the machinery; 2.0 internalizes twenty sources of design practice into the skill itself, adds the expression layer that benchmark evidence showed was missing, and ships that evidence.

### Renamed

- **frontend-aesthetics → PolishKit.** Plugin name, skill directory (`skills/polishkit/`), commands and manifests move together; the plugin identity changes, so uninstall the old entry and install PolishKit. Historical 0.1.x entries below are kept verbatim under the old name.

### Added

- **The expression layer** (`references/expression.md`): type drama (display ≥ 3× body, weights at both ends of the family), compositional tension (one deliberate asymmetry, one full-bleed or overlap), focal engineering (one focal point earned by two levers; on instrument screens the focal point IS the data — nothing overlaps a primary figure), texture on hero-scale fields, softened skeleton. Born from benchmark evidence: the 0.1.x machinery raised floors but squeezed beauty — pages were compliant and inert.
- **Subject-infused palettes**: `directions.md` hex values are a verified floor, not the design — the accent takes its hue from the brief's world. `anti-slop.md`: refusing a recipe is not refusing its ingredients.
- **States never in the default render** and a mandatory render-look-polish pass before finishing (SKILL.md §6).
- `page_audit.py` v2: TARGET-SIZE (WCAG 2.5.8), ARIA-NAME (4.1.2/1.1.1) and HEADING-ORDER checks through the existing measurable/uncertain taxonomy.
- `token_lint.py` v2: SEMANTIC-LEAK and primitive/semantic layer classification (USWDS/Carbon models).
- Three new references: `cjk-typography.md` (clreq), `charts.md` (D3/Tufte/Okabe-Ito), `native-feel.md` (Fluent + HIG). critique.md gains a tenth pillar (platform conventions) and expression criteria.
- **Benchmark evidence** (`benchmark/`): 5 briefs × three conditions (bare model / +frontend-design / +PolishKit), measured with the plugin's own tools. Rendered-page contrast failures: 48 (bare) → 101 (frontend-design alone — ambitious, floorless) → **0** (+PolishKit); scanner findings 54 / 88 / **2**; all five treatment pages render settled with full state coverage. The bare condition's own output converges on the exact AI-slop recipe the stance warns about. Protocol, tables and honest limitations in `benchmark/RESULTS.md`.
- `references/sources.md`: entries for the twenty internalized sources (standards, judgment, typography, motion, data visualization, empirical research).

## [0.1.3] - 2026-11-07

The documented limitations became tools. Everything here is a repair or a supplement to existing capabilities, agreed with the maintainer as one release; it is not a redesign.

### Added

- `scripts/cdp.py`: a stdlib-only RFC 6455 WebSocket client and a thin CDP session layer — masked client frames, masked-server rejection, fragmentation assembly, strict UTF-8, a 64 MB message guard, and loopback-only endpoint validation reusing the capture tool's address checks. Pinned by byte-level protocol tests (the RFC 6455 §1.3 handshake vector, both extended-length tiers, every rejection path); no browser or network needed for them.
- `visual_capture.py` over CDP: one persistent browser for the whole plan. `--dark` really emulates `prefers-color-scheme` — the light and dark frames of the same view come out different across the full viewport, which retires the old "`--theme` is recorded in the filename only" self-contradiction. `--full-page`, `--element`, `--hover` and `--focus` reach the states plain screenshots could not. Any CDP failure falls back to the legacy per-view engine, and the JSON reports which engine ran (`engine`, `cdp_error`). The blank heuristic is calibrated per theme, because dark pages legitimately produce fewer colours.
- `scripts/page_audit.py`: a rendered-page contrast audit. Every visible text pair gets either a measurable verdict (with large-text thresholds) or an explicit `uncertain` class — gradient/image, blend/filter, occlusion, unparseable — never a guessed one. The canvas assumption is stated in the report header, and gradient detection is chain-aware (a gradient behind an opaque background stays measurable).
- `scripts/token_lint.py`: token-file audits — definition-site contrast (`DEF-CONTRAST`, text pairs important, UI pairs review), `RAW-LEAK`, `MISSING-ROLES` (important when the project defines no tokens at all), `UNUSED-TOKEN` and `OFF-SCALE`. No rule here is blocking.
- `scripts/color_sim.py`: Machado 2009 severity-10 simulation for protanopia, deuteranopia and tritanopia, applied in linear RGB as the model requires; `--check FG BG` reports whether a pair's contrast collapses under simulation — the runnable form of the "color never carries meaning alone" floor.
- `wcag.py --apca`: draft APCA Lc with constants quoted verbatim from apca-w3 0.0.98G-4g, clearly marked supplementary; the WCAG verdicts in the same line remain the only gate.
- `image_diff.py` baseline mode: two directories produce a per-pair report (identical, changed with bounding box, missing on either side, not comparable), still never a gate.
- Chinese keywords in `design_lookup.py`: CJK runs are greedily longest-matched against `data/zh-keywords.csv` (original content, ~110 terms aimed at the real vocabulary of the vendored data), each match contributes its English tokens to the unchanged scoring, and matched terms are printed as a trace line. NFKC normalization folds full-width input. Every failing palette pair now also prints an adjusted suggestion marked "not applied" (deterministic binary search toward black or white), and hopeless pairs say to move the background instead.
- The typography section names its own conflict: the Google Fonts CDN imports in the data contradict the CSP/self-host rule, so they are reference only.
- A README section on how this plugin differs from ui-ux-pro-max, and the matching section in the Chinese README.
- `SKILL.md` states that the skill stands alone when `frontend-design` is not installed.

### Changed

- **RAW-LEAK ownership.** The raw-hex heuristic left `slop_scan.py` (the rule ID `COLOR-RAW-HEX` is gone) and became `token_lint.py`'s token-aware `RAW-LEAK`: no threshold, and each raw value names the token it duplicates, if any. BREAKING for anything that matched on `COLOR-RAW-HEX`.
- `slop_scan.py` joins multi-line tags before scanning, so an `<img>` whose attributes span lines no longer escapes `A11Y-IMG-ALT`; honours line-level `/* slop-ignore: RULE-ID */` and a project `.sloprc` (suppressed findings are counted in the summary); adds review-level `EMOJI-ICON`, `HOVER-LIFT` and the aggregate `MOTION-UNIFORM`; and has a `--changed` mode over git's changed and untracked files, with git anchored at the first given path. The severity philosophy is written down: only accessibility floors are blocking.
- `design_lookup.py` exit semantics: a query that matches nothing — including Chinese terms outside the mapping table — now lists the product types and exits 1, where empty-token queries previously errored with exit 2.
- Development workflow restored: the dev tree is the single source of truth again. The 0.1.2 release files (READMEs, this changelog, CONTRIBUTING, the PNG-bomb regression tests, `make_fixtures.py`, `.claude-plugin` manifest) were synced back from the release mirror, which had drifted ahead of the dev tree. A duplicated 0.1.0 section was removed from this changelog.

### Fixed

- `slop_scan.py --changed` ran git in the process working directory instead of the scanned path, so a repository given by path was reported as unavailable; it now anchors at the first path.
- Tests caught the CDP client draft writing the WebSocket mask bit as a separate byte instead of folding it into the length byte — the byte-level fixture strategy paying for itself before any real browser run.

## [0.1.2] - 2026-11-02

Security fix, found by a manual audit of the release repository.

### Fixed

- **`image_diff.py` could be made to exhaust memory with a tiny input.** A 65 KB PNG declaring a 1x1 image inflated to 64 MB and was accepted, because `zlib.decompress()` ran without an output bound and the size check happened afterwards. Decoding now checks the declared dimensions against a 40-million-pixel limit and the expected scanline size against a 160 MB limit before inflating, and inflates with `decompressobj().decompress(data, max_length)` so excess output is never produced. Two tests pin it, and both fail against the old implementation.

### Added

- `SECURITY.md` documents the bounds and records this defect, rather than describing the decoder as safe without evidence.

## [0.1.1] - 2026-11-01

This is a correction to the 0.1.0 release, not a feature jump. It closes a gap the first release documented instead of implementing, and it makes the plugin's limits and lineage explicit before public release.

### Fixed

- **The visual loop existed in the sources and not in the plugin.** 0.1.0 read Anthropic's `frontend-design` ("taking screenshots to review"), claude-dev-kit's capture scripts and pixel-diff threshold, and several AI UX Playground skills that verify in a headless browser, then wrote the loop as an optional aside — "screenshots when a browser tool is available". That gave a model a legitimate reason to skip visual review. The loop is now a required step with a tool that runs it.

### Added

- `scripts/visual_capture.py`: headless capture with a Chromium-family browser found by absolute path only. Shoots repeatedly until two consecutive frames are identical, so a half-rendered shell is not mistaken for a design; reports colour counts, attempt counts, console errors and blank frames as JSON.
- `scripts/image_diff.py`: PNG decoding and pixel comparison with the standard library only, giving changed pixels, ratio and a bounding box. Decodes non-interlaced 8-bit PNG and reports anything else as unsupported instead of comparing it wrongly.
- `references/visual-review.md`: the render, look, change, look-again procedure, including the measured reasons behind the tool's design.

### Changed

- `SKILL.md` verification step now starts with rendering and looking, and requires re-capture plus diff after a change. A review with no capture must say "not visually verified".
- `critique.md` replaced the conditional screenshot step with a mandatory capture step, and added a "close the loop" section after applying fixes.
- `/design-review` now captures first and reports a Visual section in the findings.
- The README states what the plugin is for, what it can do, and what it explicitly cannot do; before, "cannot" was scattered across limitations.

### Documented

- `references/sources.md` now names, per source, where the visual loop came from and that 0.1.0 dropped it. It also adds "What this plugin does and does not do" and a "Lineage and honesty" section.
- README credits section lists every source used and links to the per-item record.

### Known limitations

- Capture reaches landed states only. Hover, focus rings, open menus and mid-transition frames need a driving browser tool.
- `image_diff.py` is not a regression gate: a deliberate redesign may change every pixel.
- No browser installed means no visual step; the review must then say so.
- The plugin has not been benchmarked against `frontend-design` alone. Its verifiable claims are tested; "does it look better" is not.

## [0.1.0] - 2026-11-01

First release.

### Added

- `frontend-aesthetics` skill: an eight-step workflow (read the project's rules, brief, precedents, direction, tokens, build, verify, report) with hard accessibility floors and a test for whether each default was chosen.
- Nine reference documents: principles and the brief template, nine directions with contrast-verified starting palettes, color and type, layout and motion, components and states, desktop app rules, the anti-slop catalogue, the critique procedure, and sources.
- `scripts/wcag.py`: WCAG contrast calculation for `#hex`, `rgb()` and `oklch()`, with reference values in the tests.
- `scripts/design_lookup.py`: product-type precedents from vendored data, with name-weighted matching and per-palette contrast checks that separate text failures from UI failures.
- `scripts/slop_scan.py`: read-only scan for generic-default tells and craft defects, with blocking, important, review and polish severities and a non-zero exit status when a blocking finding exists.
- `commands/design-direction.md` and `commands/design-review.md` for agents that support slash commands.
- Manifests for Claude Code (`.claude-plugin/`) and ZCode (`.zcode-plugin/`), plus plain `skills/` layout for Cursor, Codex, Copilot and any agent that reads Agent Skills.
- Eight MIT-licensed CSV data files from ui-ux-pro-max, with provenance and a list of data caveats.
- Unit tests using only the standard library, and a GitHub Actions workflow that runs them.

### Known limitations

- The scanner finds patterns, not taste. Every finding needs a human judgement.
- Palettes in the data are starting points: 173 of 192 rows have a border below 3:1, and 30 have a primary fill below 3:1, so UI pairs must be checked before use.
- Reference screenshots are not included. Visual review needed a browser tool; the skill described it as optional.
