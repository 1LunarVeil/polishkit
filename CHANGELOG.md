# Changelog

All notable changes to this project are recorded here. The format follows Keep a Changelog, and versions follow Semantic Versioning.

## [2.2.11] - 2026-11-20

The benchmark grew from three measured dimensions to seven, and gained the two things that made its numbers re-derivable: an environment record and a failure library.

### Added

- **`tools/benchmark_env.py`** — records the environment a measurement was taken in: plugin version, Python, platform, machine, browser build, and a SHA-256 digest of every audit script. `--diff` compares the current environment against the record field by field and reports which tool drifted.
  - It exists because of a real drift: the 2.0 benchmark recorded 101 contrast failures on the baseline condition, and the same never-edited pages now measure 105, stably, twice. Nothing in the pages or the audit changed. Without an environment record a reader cannot tell that from a regression.
- **`benchmark/ENVIRONMENT.json`** — the fingerprint this report was measured under (Chrome 157.0.8103.79, Python 3.11.9, Windows 26200/AMD64).
- **`benchmark/FAILURE-MODES.md`** — ten failure modes extracted from the actual failures across the three conditions, not from a taxonomy: narrow-viewport reflow, fixed widths, invisible focus rings, keyboard traps, text-spacing clipping, CJK line-breaking, contrast, attention misallocation, ladder gaps, and the reviewer-side trap of one root cause producing a dozen findings. Each names its measurable check, a real sample, the root cause and the fix, and which condition produced it.

### Changed

- **`benchmark/RESULTS.md` was re-measured end to end with 2.2.10 tooling.** Seven metrics now, four of them new (keyboard, text spacing, reflow, CJK line-breaking), across all three conditions. The number that matters: bare 5 / baseline 12 / treatment 0 keyboard failures; 21 / 28 / 0 reflow failures; 0 / 8 / 0 spacing failures; 0 / 1 / 0 CJK failures.
- **The report now measures treatment twice.** The benchmark pages were repaired across four releases, so the 2.0 originals and the fixed pages are both measured and both shown. The originals carry **48 real defects** on the four dimensions the 2.0 tooling could not see — B1 losing a model name to an ellipsis, B3's chart ring at 1.01:1 against its own bar, B3 639px wide at a 320px viewport, B5's nav clipped with nothing to scroll toward. The 2.0 "0 fail" claim was true on the three dimensions it measured.

### Fixed

- **`keyboard_audit` focus findings carried no `check` name.** Three FAIL branches set `clause` but not `check`, so a JSON consumer grouping by check saw `None` for all sixteen focus failures in the benchmark. They are now `NO-FOCUS`, `LOW-CONTRAST` and `INDICATOR`.

### Verified

- 430 tests pass (412 + 18 for the environment tool).
- Re-measuring all three conditions reproduced the recorded contrast totals: bare 48 (recorded 48), baseline 105 (recorded 101, the drift above), treatment 0 (recorded 0). Baseline measured twice, identical.

## [2.2.10] - 2026-11-20

The platform dimension `design_lookup` was missing.

### Added

- **`design_lookup.py --platform`** — `all` (default), `web`, `mobile`, `visionos`, `macos`, `windows`, `desktop`. The vendored `ux-guidelines.csv` has no desktop rows (its Platform column offers All/Web/Mobile/VisionOS), so the macOS and Windows checklists live in the lookup itself and index `references/native-feel.md`: window chrome and the three window states, type at platform units (13pt default, 10pt floor, no Light weights on macOS), control sizes (28×28pt default, 44×44pt hit region), Mica and the content layer above it, Win11 radii and the two densities, and the accelerators each platform expects. `desktop` prints both and says to pick one window's platform and commit.
- `tests/test_lookup_zh.py` gains 15 tests over the mapping, the checklist contents and backward compatibility.

### Verified

- 412 tests pass (397 + 15).
- Default output is unchanged: with no `--platform`, the lookup still prints the All/Web row set and no desktop checklist.
- Each choice exercised: `web`, `mobile`, `visionos` narrow the row set; `macos` and `windows` add their checklist; `desktop` prints both; a platform without `--ux` still prints its checklist.

## [2.2.9] - 2026-11-20

Fixes B3's first screen — the page the new expression audit was built to find — and corrects one metric that was charging a hero for width it never claimed.

### Fixed

- **B3 · the subject was below the fold.** The page a shopkeeper opens to read had its revenue chart and product list starting at y=475 of a 900px screen: 228px of padding-heavy hero, 102px of quiet KPIs and a 30px decorative score stood between the display figure and the work. Hero padding cut from 36/30 to 20/14, the KPI block pulled up, the score shrunk from 30px to 18px and the panel grid from 22px to 14px. The panels now begin at **y=411**, and the first screen holds the complete revenue chart (all seven bars, axis, target line, note) and the complete product list. Verified in the capture, not just in the numbers.
- **`expression_audit` column fill measured a narrow column far down the page.** The strip ran from the loud element to 400px past its bottom, which charged a hero figure for a 183px-wide lane while the band's other content spread horizontally beside it. The strip now runs to the fold. B3's reading moved from 41.9% to 40.4% — the number barely moved, and that is the honest outcome: this page's loud element does sit in a narrow column, and the metric says so without pretending it describes the whole band.

### Verified

- All five audits on the edited B3: text-spacing 0 FAIL, reflow 0 FAIL (190 uncertain, all table and chart exceptions), page_audit 137 pass / 0 fail / 16 uncertain, keyboard 48 pass / 0 fail, spacing clean.
- The capture after the fix reads as intended: figure, three KPIs, the whole chart, the whole product list.
- 397 tests pass; the four gates are green.

## [2.2.8] - 2026-11-20

`expression_audit` was rewritten after the maintainer's critique: a single "type ratio" score was a weak proxy that said how loud a page is, never whether the loud thing deserved to be loud.

### Changed

- **`expression_audit.py` now reads attention allocation instead of scoring drama.** It reports, measured on the first screen only:
  - **ATTENTION** the loudest element, the count of other text in its band, how much of its own column is filled before the fold, and the blank run below it.
  - **LADDER** the size steps present, with a skipped rung reported only when the band is thin *and* unpainted.
  - **DENSITY** text items per 100,000 CSS px², as a raw number with no threshold — a portfolio is legitimately sparse and a dashboard is not.
  - The old ratio survives as one reference line, printed with "reported, not judged" beside it.
- **It asks questions and answers none of them.** For each page it prints what the numbers imply — *is the loudest thing the thing this screen exists to show; is the page's own heading a third the size of one measurement; do two elements compete* — and leaves the decision to the model or the designer, which is where it belongs.
- **Imagery makes emptiness uncertain.** When the band around the loud element holds a large image, canvas or painted block, or the page paints its own background, the emptiness is reported as `uncertain` with the evidence. A photography hero's void and a dashboard's dead band have the same text geometry; only a person can tell them apart.

### Fixed

- **The ratio measured the whole page, not the first screen.** B2's largest text was a decorative `12` at 118px *2000px below the fold*, and it was deciding that page's "drama" score. First-screen restriction is the correction the rewrite is about.
- **A chained conditional swallowed the question's opening sentence.** Writing the blank-run clause, the painted-band caveat and the closing question as one `+ ... if painted else ""` chain bound the `if` to the whole concatenation, so every unpainted page printed `". Is that the thing this screen exists to show?"` with no subject.
- **`body_size: 0` fell through to the 16px fallback** in `ratio_to_body`, the same `0 or 16` mistake fixed once already in this file.

### Verification

- 397 tests pass (391 + 6 net after the rewrite; the file's suite grew to 39).
- Five benchmark pages: B3 is the only one flagged, with three questions — a 70px figure over a 41.9%-filled column, 78px of blank, a 21px page heading, and a 70→22px ladder gap. B2, B4 and B5 report `VISUAL-FILL` as uncertain instead, because their bands carry photographs or painted backgrounds. B1, a dense dashboard, raises none of it.
- The maintainer reviewed the five pages side by side and judged 4.75–6.74× not to be over-expressed, while calling B3's first screen genuinely wrong: the number drew the eye, the page's actual subject had been pushed below the fold. The rewrite is what turns that judgement into something the tool can point at.

## [2.2.7] - 2026-11-20

The expression layer stops being a claim and becomes a measurement — for the parts of it a rectangle can measure.

### Added

- **`scripts/expression_audit.py`** — reports the numeric items from `references/expression.md` and names the ones it cannot judge.
  - **TYPE-RATIO** largest carried text against body size, measured against the file's 3× floor; under 2.5× is called flat.
  - **WEIGHT-SPAN** lightest and heaviest rendered weights, with the 400–600 middle called out as having no contrast.
  - **SIZE-STEPS** how many distinct sizes carry text; two is too few, more than twelve reads as drift.
  - **DISPLAY-SETTING** tracking and line-height at display size, reported against the file's −0.03…−0.01em and 1.0–1.2 ranges.
  - **FAMILIES** every distinct `font-family` declaration with its sample count, listed rather than counted against a threshold.
  - It also prints the five expression items no geometry can settle — one asymmetry, one full-bleed moment, one focal point, dead-flat hero fields, whether the signature is doing any work — so a passing report never reads as "the page is beautiful".
  - **Nothing it reports gates a build.** Every finding is review severity and the exit status is always 0 unless the audit could not run at all. A tool that let taste break CI would reproduce the failure mode the benchmark's human-verdict section warns about.
- `tools/crosscheck.py` runs it as a sixth column. `tests/test_expression_audit.py`: 33 browser-free tests.

### Fixed

- **`expression_audit` counted font stacks as families.** Reporting first names produced five "families" on a page with three roles, because `Segoe UI Light` is a weight of `Segoe UI`, `Cascadia Code`/`Consolas` is one mono stack, and a `Noto Sans SC` CJK fallback is a fourth role rather than a fourth family. The metric now lists declarations with sample counts and only raises a review above six.
- **A page that set tracking to exactly −0.03em was flagged as outside −0.03 to −0.01.** Float error, closed with a 0.005em tolerance.
- **`body_size: 0` fell through to the 16px fallback** instead of reporting an undefined ratio, because `0 or 16` is 16. A measured zero is not a missing value.
- **`weight_verdict(400, 600)` returned pass.** The middle band is inclusive at both ends: 400 is the default body weight and 600 is not a real bold.

### Verification

- 391 tests pass (358 + 33).
- Five benchmark pages, all review-only: type ratios 4.75–6.74× (B1 6.29, B2 6.74, B3 5.00, B5 4.75), weight spans reaching both ends on each, 7–11 size steps, no family findings.
- A deliberately inert probe page reports 1.25× body, weights 400–400 and no text at display size — the tool discriminates instead of only agreeing with good pages.
- CI: the 2.2.6 run reported failure with four matrix jobs green and both macOS jobs cancelled at the 15-minute mark with no steps recorded. Runners never picked them up; an empty commit re-triggered the matrix.

## [2.2.6] - 2026-11-19

The CJK runtime check that `cjk-typography.md` described but no tool measured.

### Added

- **`scripts/cjk_breaks.py`** — walks each rendered line character by character with a Range and reports clreq §6.1.1 violations: **LINE-START** when a line begins with a closing bracket or terminal punctuation, **LINE-END** when it ends with an opening bracket. It also names every element setting `word-break: break-all`, which is the property that disables the browser's own 禁则.
  - The character sets are **derived from Unicode categories**, not transcribed from clreq's table: every `Pe` closing bracket is forbidden at line start, `Ps` opening brackets are vetoed explicitly (they are legal there), and the terminal `Po` marks are listed. Tests enumerate every `Pe` and `Ps` character in Unicode and assert the derivation both ways, so an added closing bracket cannot silently escape the rule.
  - The walk runs at a 390px viewport on purpose: at 1440px a Chinese paragraph fits in two or three lines and the edges fall wherever the browser likes, so no prohibition is exercised.
  - Pages with no CJK prose report that and claim nothing else. `white-space: pre` runs, where wrapping is an explicit author choice, come back uncertain.
- `tools/crosscheck.py` runs it as a fifth column.
- `tests/test_cjk_breaks.py`: 27 browser-free tests over the character derivation, CJK detection, and the failure/review split.

### Fixed

- **Every audit could measure a browser error page as though it were the site.** A failed navigation still fires `Page.loadEventFired`, and Chrome's own error document is real text — the CJK audit reported `依次前往 Chrome 菜单 >“` as a Chinese line-ending violation on a page whose server had simply been stopped. `cdp.PageSession` now checks both the navigation response's `errorText` and the landed `location.href` for `chrome-error://`, and raises before any audit runs. This closes the same hole for `page_audit`, `keyboard_audit`, `text_spacing` and `reflow`.
- **B1 · an opening bracket ended a line.** `没有匹配「<span>…</span>」的模型` left `「` at a line end at 390px, because the bracket and the inline span after it are separate break opportunities. The quoted run is now wrapped in a `nowrap` span.

### Verification

- 358 tests pass (331 + 27).
- Probe pages: a forced `<br>` before `、` reports LINE-START, one before `（` reports LINE-END, a clean control reports nothing — six lines walked to prove both directions.
- A stopped server now yields `{"verified": false}` and exit 2 with `navigation failed: net::ERR_CONNECTION_REFUSED`, instead of a report about Chrome's error text.
- Real page B1: 91 CJK elements / 70 lines, 0 violations after the fix; the other four benchmark pages contain no CJK prose and say so.

## [2.2.5] - 2026-11-19

Fixes the confirmed defects in the benchmark pages, plus the audit defect that hid one of them. Repairs only; no new capability.

### Fixed

- **`text_spacing.py` compared element boxes instead of text extents.** A block heading spans its container's full width, but its words may stop half way across. The tool measured the box, so a 1136px `<h1>` whose text ended at x=758 was reported as overlapping a note that starts at x=845 — 87px of empty space apart. Measurement now uses `Range.getClientRects()`, one rect per line of text, falling back to `getClientRects()` where a range cannot be built. Two tests pin it: a heading that clears its neighbour, and a wrapped inline whose fragments stay separate.
- **B1 · model names lost a line under 1.4.12.** `.m-name` was `nowrap` + `ellipsis`, so enlarged letter spacing widened the name past its box and the ellipsis cut a whole line's worth (measured: 236px needed in a 201px box). Names now wrap, quant tags stay unbroken, and every identifier stays readable.
- **B1 · the VRAM hero and the parameter rows did not reflow at 320px.** The narrowest breakpoint was 980px, so a 320px viewport still ran the desktop grids: the document overflowed by 72px and a dozen children sat past the viewport, including the whole hero. A 520px breakpoint collapses the fixed tracks, wraps the GPU rows and shrinks the display figure. Two follow-ups came from looking at the 390px capture rather than the audit: the second GPU's name was squeezed to 152px (one word per line) and the allocation heading printed vertically at four characters wide.
- **B2 · the hanging note overlapped the title under 1.4.12.** With `line-height:1.0` the title gained a line and the note's fixed 42px overhang reached into it.
- **B3 · the orders table and the range tabs overflowed at 320px.** Document width was 639px against a 320px viewport. The table now sits in a horizontal scroller — data tables are 1.4.10's explicit two-dimensional exception and their cells must stay comparable — while the tabs, header and channel select wrap. A `td.items` cell that had been truncating since before the override now wraps to two lines.
- **B5 · the nav was pushed past a 320px viewport and clipped.** The document did not scroll, so only the element-level check found it: the links were unreachable with nothing to scroll toward. The header and nav now wrap.

### Verification

- 331 tests pass (329 + 2 for the line-box measurement).
- All five treatment pages: text-spacing 0 FAIL each; reflow 0 FAIL each (B3 keeps 190 uncertain, all table and chart exceptions).
- Probe pages unchanged: spacing probe still reports 3 FAIL, reflow probe 8, clean pages 0.
- Desktop captures of B1, B2, B3 re-read after the edits: the signature elements, the hanging note and the chart are intact; the 390px B1 capture was read twice and drove two additional fixes.

## [2.2.4] - 2026-11-19

The last two layout clauses the plugin taught but never measured.

### Added

- **`scripts/reflow.py`** — loads the page at 320, 400 and 768 CSS px and reports WCAG 1.4.10's own failure: the document scrolling horizontally on vertically-flowing content, plus the elements that cause it. A `--text-scale 2.0` reading covers 1.4.4.
  - Findings are grouped by shared right edge. One unresponsive dashboard grid produced 106 separate WIDER findings across five descendants at x=386; grouping reports it once and names how many elements restated it.
  - The criterion's two-dimensional exception is structural: content inside `table`, `svg`, `video`, `canvas`, `pre`, `[role=img]` and similar is reported as `uncertain:2d-exception` with the container named, never as a failure. `code` is deliberately absent from that list — an inline snippet with `white-space:nowrap` is exactly the overflow that must be fixed, and treating it as excepted hid the only real finding on the probe page.
- `tools/crosscheck.py` runs it as a fourth column, so the whole layout floor (contrast, keyboard, spacing, reflow) reads in one table.

### Fixed

- **`reflow.py` measured against the wrong width.** `documentElement.clientWidth` excludes the vertical scrollbar, so a 320px request reported a 305px viewport and every element reaching past the scrollbar became a false WIDER — 112 of them on one page. The requested width is now part of the measurement baseline; the scrollbar is the browser's furniture, not the page's failure.
- **`reflow.py` discarded element geometry.** `classify` wrote the viewport into each finding's `width` field and dropped `right` entirely, so every finding read "320px wide" and the de-duplication that groups by right edge had nothing to group on. Both now survive, and the tested viewport travels as its own field.
- **`reflow.py` applied the exception to ancestors but not to the element.** A wide `<table>` failed while its own cells were listed as excepted.

### Verification

- 329 tests pass (307 + 22).
- Probe page with a 900px fixed card, a nowrap code line and an excepted table: 8 FAIL at every width, table excepted, healthy paragraph silent. Clean page: 0 FAIL, exit 0.
- Five treatment pages: B1 27 FAIL grouped from 140 raw findings, B2 0, B3 4, B4 0, B5 3. B1's dashboard does not reflow at 320px — a real finding, not an artefact.

## [2.2.3] - 2026-11-19

One new tool and the defect it exposed in an existing one.

### Added

- **`tools/crosscheck.py`** — runs all three rendered audits against each URL and prints one table: failures and uncertain count per clause per page. Its reason for existing is that the audits answer different questions, and read one at a time nobody notices that a page scoring "0 failures" still has 44 uncertain text pairs no tool will settle. The legend names each column's clauses, an audit that cannot run is reported as `UNVERIFIED` rather than as zero, and `--json` keeps the full per-audit report.

### Fixed

- **`page_audit.py` failed collapsed panels under 2.5.8.** The collector skipped only `display:none` and `visibility:hidden`; a panel that is `display:block` but has no box reports a 0x0 rect, and eight of those became target-size FAILs on a booking page whose date picker was simply closed. Elements with no pointer area are now skipped at collection: 2.5.8 has nothing to measure on them. The pure verdict still treats an explicit 0x0 rect as a failure, because that is what it would be on a reachable element.
- **`crosscheck.py` itself headlined the wrong number.** Its first version added contrast failures, target-size failures and accessible-name failures into one count, so a page with zero contrast failures and eight collapsed-panel artefacts read as eight contrast failures — which flatly contradicted `benchmark/RESULTS.md` and cost an hour of re-reading before the mistake was found. The columns now keep the clauses apart, and the headline is the contrast count the benchmark tracks.

### Verification

- 307 tests pass (299 + 8 across the two changes).
- Cross-checked all five 2.0 treatment pages: contrast failures 0/0/0/0/0, matching the stored benchmark; keyboard 0 everywhere; text spacing 11/1/1/0/0, the defects 2.2 recorded and left in place as page issues.
- The B4 collapsed-panel false positives are gone (8 → 0) with the contrast count unchanged.

## [2.2.2] - 2026-11-19

One structural change and the resource leak it exposed. No new capability.

### Changed

- **`cdp.PageSession` replaces three hand-written copies of the same launch sequence.** `page_audit`, `keyboard_audit` and `text_spacing` each carried about sixty lines of launch → connect → create target → attach → enable → navigate → wait → close, identical in all three. A fix applied to one copy and not the others is exactly how a `NameError` reached a release while the suite stayed green, so the sequence now lives in `cdp.py` once, as a context manager with a guaranteed teardown. The three audits lost ~170 lines between them.

### Fixed

- **Every audit run left a Chrome profile on disk.** `_teardown` called `terminate()` and then `rmtree(..., ignore_errors=True)`; on Windows `TerminateProcess` returns before Chrome's children release their handles, so the removal failed and `ignore_errors` hid it. Measured on this machine: nine `pk-cdp-*` directories survived a normal session, and **195** `fa-profile-*` directories had accumulated from the older capture path, which had the same defect in three places. Teardown now waits for the process to exit and retries once; `visual_capture.py` got the same treatment. Verified by running the capture tool three times and the full suite once from a clean baseline: zero new directories.
- Two `PageSession` tests launched real browsers because they entered `__enter__` to exercise `__exit__`. They now call `__exit__` directly, and the suite leaks nothing.
- **`--check` failed on the hook's own bookkeeping.** Mimosa writes `.mimosa/` into `polishkit-dist` whenever a command runs near it, so the staging tree was "dirty" through no author's action and had to be rebuilt before every check. Both `build()` and `check()` now strip it; it is lossless, because nothing under `.mimosa/` is ever copied from the dev tree.

### Verification

- 299 tests pass (291 + 8 covering `PageSession` teardown ordering and the missing-browser path).
- Leak check: from a cleaned Temp baseline, the full suite leaves zero `pk-cdp-*` or `fa-profile-*` directories; three consecutive `visual_capture.py --dark` runs also leave none.
- The three audits re-run on the same page after the refactor produce byte-identical reports to before it.

## [2.2.1] - 2026-11-19

Two defects in the publish pipeline itself. No new capability: these are corrections, and the maintainer's rule is that corrections do not raise the minor version.

### Fixed

- **`.generated-by-build_dist` shipped inside the installed tree.** The marker that lets `build_dist.py` recognise a directory it created lived inside `polishkit-dist`, and a directory-type marketplace copies the whole tree — so every install since 2.0.0 carried an internal build artefact. Found by inspecting the real 2.2.0 cache, not by any test. The marker now sits beside the tree as `polishkit-dist.generated`; `--check` reports an in-tree marker as a defect instead of discarding it silently.
- **The marketplace catalog said 2.1.0 while the plugin was 2.2.0.** The plugin-creator spec requires the catalog entry and the manifests to agree, and nothing checked it. A user reading the marketplace saw the wrong version, and an installer comparing versions would have skipped the update. The catalog now matches, and `build_dist.py --catalog-check` verifies name, version, description and source path against the manifest.

### Changed

- `CONTRIBUTING.md` records the maintainer's correction to the versioning rule: +0.1.0 is reserved for a genuine leap, new audits of the existing shape are +0.0.1, and repairs never justify a bump.

### Fixed (continued)

- **`tools/build_dist.py` in the mirror was stale.** `CONTRIBUTING.md` tells contributors to run it there, but it was never in the sync set — the copy had been made by hand once and stopped moving. `MIRROR_SHARED_DIRS` now includes `tools/`.
- **`--mirror-check` printed each drift twice.** Files present in both trees were compared by the dev→mirror pass and reported again by the mirror-only pass. Each class is now reported exactly once, verified against a scratch mirror with an edited file, a mirror-only file and a leaked hook ledger.

### Verification

- 291 tests pass.
- Four gates green: staging byte comparison, mirror comparison, catalog check, and the three-audit no-browser contract.
- The in-tree marker check was proven by copying the staging tree, writing the old marker back, and confirming the gate reports it.
- Installed 2.2.0 cache inspected directly: identity, 11 scripts, one skill directory, no `notes/`, `.mimosa/`, `tests/` or `benchmark/`.

## [2.2.0] - 2026-11-19

WCAG 1.4.12 becomes measurable. The plugin shipped the rule as prose and called it a manual check; the clause is testable, so it is now a tool.

### Added

- **`scripts/text_spacing.py`** — applies WCAG 1.4.12's four user overrides (line height 1.5×, paragraph gap 2×, letter spacing 0.12×, word spacing 0.16×) and diffs the DOM geometry between the authored page and the overridden one. It reports, as measurable FAILs:
  - **CLIP** — an element whose text is now larger than a box that hides it, including the common case where the clipping box is an *ancestor* (a 48px `overflow:hidden` card around a paragraph that reports a comfortable client box of its own);
  - **FIXED** — a `max-height` box whose content now needs more than one extra line;
  - **TRUNCATION** — a single-line ellipsis that now loses at least one more em of text than it did authored;
  - **OVERLAP** — sibling text runs that occupy the same pixels only after the override, with parent/child pairs excluded by ancestor path and a 24 px² floor so line-box brushes do not count.

  It also reports the authored spacing values (informative: SC 1.4.12 does not require a page to ship them, only to survive them), lists content hidden by a transform, mask or clip-path as `uncertain:not-measured`, and states when the collector was capped. Exit 1 on a measurable failure, 2 with a browser problem (`{"verified": false}`), 3 on a rejected URL.
- `tests/test_text_spacing.py`: 40 browser-free tests over the override stylesheet, the clipping and overlap geometry, and the classify decisions.
- `/polish-audit` runs it alongside the other two rendered audits.

### Fixed

- **`text_spacing.py` pairing key was a document coordinate.** The override moves every element down, so every key changed, nothing paired with anything, and the first version reported a clean page for content it never compared. The key is now the element's child-index path from `<body>`, which a reflow does not move.
- **`text_spacing.py` missed every ancestor-clipped card.** Clipping was tested on the text element only, so a paragraph inside a fixed-height `overflow:hidden` card passed. The nearest clipping ancestor is now collected and tested too.
- **`text_spacing.py` reported pre-existing truncation as a 1.4.12 failure.** A four-pixel growth threshold counted table cells that were already truncating before the override — a different defect, under a different clause. The floor is now one em of extra required width, which is roughly one lost character cell.
- **`text_spacing.py` never reached its truncation check.** The "already clipped before the override" guard ran first, and a single-line ellipsis is by definition already clipping. TRUNCATION is now tested before that guard.

### Verification

- 291 tests pass (251 + 40).
- Smoke pages: a probe page with a clipped card, a `max-height` block and a `nowrap` label reports 3 FAIL; a clean page reports 0 FAIL; both run from the dev tree and from the installed staging tree.
- Real pages, unmodified: B1 (145 text elements) reports 11 FAIL including two spans that genuinely collide only after the override and five model names that lose a line of their GPU description; B3 (150 elements) reports 1; B5 (73 elements) reports 0. Each was checked against the raw before/after geometry before being trusted.
- Two false-positive classes were found this way and removed: nested elements counted as overlapping their own container, and cells already truncated at rest.

## [2.1.1] - 2026-11-19

Corrects two defects in the audit itself and the two page defects it reported. No new capability: a tool that returns different answers for an unchanged page is not evidence, so these landed before the release could be called done.

### Fixed

- **`keyboard_audit.py` reported different verdicts for an unchanged page.** A focus style carrying `transition: box-shadow` meant the first frame after focus was mid-animation; one real button passed on one run and failed at 1.02:1 on the next. Every measured frame now waits for two consecutive identical crops, the rule the capture tool already used. Without this the audit's output was not reproducible.
- **`keyboard_audit.py` called `time.sleep` without importing `time`**, so it exited 2 on every real page while all 244 tests passed — every test drove the pure helpers and nothing drove the screenshot loop. `SettleTests` now covers that path, including an assertion that `time` is imported.
- **B3 chart focus ring** used `--accent`, the same colour the focused bar is filled with, rendering at 1.01:1. It now uses `--ink` with a 2px offset, which places the ring on the panel surface at 16.38:1.
- **B5 copy button focus ring** landed on the container's ink border and the button's own hard ink shadow, at 1.01:1 on two of four sides. It now draws an inset ring on the button's amber fill at 11.46:1. Removing the shadow on focus was tried and rejected: it changed 1000+ unrelated pixels and made the audit's own measurements fluctuate.
- Both READMEs said "nine pillars" where `critique.md` has ten.

### Verification

- 251 tests pass (244 + 7 covering the settling path).
- Five treatment pages re-audited: B1, B2, B3, B4, B5 all report 0 FAIL. B3 and B5 were re-run 2–3 times each with identical verdicts.
- Full-project static security scan: `findingCount: 0`, sealed `sha256:808567aa…`, evidence boundary `static_only_no_runtime_execution`.
- The publish mirror was re-audited end to end: its `benchmark/runs/treatment/` B3 and B5 pages also report 0 FAIL.

### Added

- `tools/build_dist.py --mirror-check`: compares the publish mirror against the dev tree for the shipped files plus `tests/` and `benchmark/`, which are published but never installed. Neither the old manifest check nor the new staging check could see a test file edited in one tree only — that is how the mirror once ran 244 tests while dev ran 251. Verified against three drift classes: an empty mirror, a mirror with shipped files but no `tests/`, and a single edited byte.

## [2.1.0] - 2026-11-19

The interaction-level audit. 2.0 taught keyboard and focus rules the plugin never verified; this release measures them, closing the largest self-contradiction in the skill.

### Added

- **`scripts/keyboard_audit.py`** — a keyboard and focus audit over CDP. It dispatches real Tab presses (not simulated `focus()` calls, so `:focus-visible`, scroll anchoring and in-page focus management behave as they do for a keyboard user), screenshots each stop focused and unfocused, and compares the two frames pixel by pixel.
  - **2.1.1 keyboard reach**: interactive elements carrying `tabindex="-1"` (which never enter a Tab walk by construction, so walking alone cannot find them), plus tabbables the walk never reached when the walk finished normally.
  - **2.1.2 traps**: a walk that never leaves the document fails — including the case where every tabbable is reachable but the browser's own UI is not. A cycle confined to a dialog is a review naming the container.
  - **2.4.7 / 1.4.11 focus indicator**: identity of the two frames, the indicator's same-pixel change, and its contrast against the colours it actually touches. Measurement is pixel evidence because `outline: auto` computes as `1px` whatever the browser draws, and `box-shadow` and pseudo-element rings have no outline at all.
  - **2.4.11 focus obscured**: five hit-test samples inside the border box; "entirely hidden" is the criterion's bar, so a partly covered control passes.
  - **1.4.3 in transient states**: the element's own text pair in the focused and hovered states, composited exactly as `page_audit.py` composites the resting state — catching pairs that pass at rest and fail on hover.
  - **2.4.13 (AAA)**: indicator area against the 4h + 4w two-pixel perimeter and same-pixel state contrast, printed as supplementary evidence that never drives the exit code.
  - Same taxonomy as `page_audit.py` (measurable pass/FAIL, uncertain, review), same "claims nothing" contract with no browser, `--measure` bounds photographed stops and the report names those walked but not measured.
- `tests/test_keyboard_audit.py`: 62 browser-free tests over the deciding logic and the pixel arithmetic, including REGRESSION tests for three defects a real smoke page caught first — the trap cascade that reported every later control as unreachable, the hover read that happened after the pointer left (turning a hover contrast failure into a pass), and the `<body>` end-of-walk stop that `label()` renamed and so went unrecognised, producing a trap FAIL and a "no indicator" FAIL on a clean page.
- `image_diff.decode_png_bytes`: the PNG decoder without a path, so the audit can measure crops it never writes to disk.
- `/polish-audit`: one command that runs the source checks and both rendered audits, and reports a merged verdict separated into blocking, important, review, uncertain and not-checked. It exists because the tools answer different questions and a merged report is what a reviewer actually needs.
- `tools/build_dist.py --check` now compares the staged tree against the dev tree file by file. The old check compared manifests only, so editing a reference or a script after the last build left a stale staged tree that passed as clean — the same class of failure that made installs serve old content.

### Changed

- `SKILL.md` step 7 runs the keyboard audit instead of asking for a manual keyboard pass; the description, references and both READMEs name the new capability.
- `critique.md` pillar 9 and the mechanical-checks list split the accessibility floor between `page_audit.py` (contrast, target size, names) and `keyboard_audit.py` (reach, traps, focus, states). `visual-review.md` gains a keyboard-pass section. `components-and-states.md` records the three failure modes the audit caught on real pages.
- `sources.md` adds the clause texts for 2.1.1, 2.4.7, 2.4.11, 1.4.11 and 2.4.13 with their conformance levels, and states plainly which two measurements (per-side median adjacency; adjacency only over qualifying pixels) are engineering decisions rather than quoted thresholds.
- Both READMEs also correct "nine pillars" to ten, which 2.0 had already changed and the capability table had not.

### Evidence

Run against the five 2.0 treatment pages, the new audit found a defect class `page_audit.py` cannot see. B3's chart bars carry `focus-visible` rings drawn in `--accent` (#963D0D) while the focused bar is filled with that same colour. Two bars lose the ring almost everywhere — "Sun 1 Nov" reads 1.01:1 on its top edge with only 1 of 3 comparable sides above the floor, and "Sat 7" 1.64:1 with 1 of 4 — so the ring is effectively invisible on the element it marks. Two more (`Thu 5`, `Fri 6`) have the same ring colour but keep three readable sides because the bar fills the plot area on only one edge; those pass, and the pass is correct under 1.4.11, whose test is whether the state can be picked out rather than whether every edge is perfect. An earlier per-side-minimum rule flagged all six as failures; checking the measured sides against the clause text is what corrected it. B2 and B4 report the expected background-image uncertainties on texture-heavy pages with no measurable failure; B1 and B5 are clean. B5 is the instructive near-miss: a 3px black ring on a button with a black hard shadow merges into that shadow at 1.02:1 on one edge while the other three sit at ~17.7:1.

The B3 and B5 pages are fixed in this release. B3's chart ring moved to `--ink` with a 2px offset, which puts it on the panel surface at 16.38:1 instead of on the bar. B5's copy button takes an inset ring at −5px, landing on its own amber fill at 11.46:1; moving the shadow aside was tried first and rejected, because removing it changed 1000+ unrelated pixels and made the audit's own measurements fluctuate. Both pages now measure 0 FAIL.

### Fixed

- **`keyboard_audit.py` reported different verdicts for an unchanged page.** A focus style carrying `transition: box-shadow` meant the first frame after focus was mid-animation; B5's copy button passed on one run and failed at 1.02:1 on the next. Every measured frame now waits for two consecutive identical crops, the same rule the capture tool uses. Without this the audit was not evidence.
- **`keyboard_audit.py` shipped calling `time.sleep` without importing `time`.** It exited 2 on every real page while the whole suite passed, because every test drove the pure helpers and nothing drove the screenshot loop. Fixed, and `SettleTests` now covers the settle path including the import.

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
