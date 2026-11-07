# Data provenance

## Source

- Repository: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- Path: `cli/assets/data/`
- Commit: bf41cbc (the HEAD when the files were copied; the clone was shallow)
- License: MIT, copyright 2024 Next Level Builder. See `LICENSE-ui-ux-pro-max.txt`.

## Files copied unchanged

- `products.csv`: product types, keywords, recommended styles, color focus, key considerations
- `colors.csv`: per-product palettes with on-color and UI roles
- `ui-reasoning.csv`: per-product pattern, style priority, effects, decision rules and anti-patterns
- `styles.csv`: style catalogue with keywords, use cases and status
- `typography.csv`: font pairings with moods (URLs and CSS snippets are present but unused)
- `ux-guidelines.csv`: UX rules with do and don't text, platform and severity
- `motion.csv`: duration tiers, easings and do and don't text (framework snippets are present but unused)
- `charts.csv`: chart types with accessibility fallbacks

## Not copied

`landing.csv`, `app-interface.csv` and `react-performance.csv` (funnel, mobile and React content), `icons.csv` and `google-fonts.csv` (catalogues), and the Phosphor and catalogue JSON files.

## Known data issues

Read these before trusting a row.

- `colors.csv`: measured across all 192 rows with `wcag.py`'s formulas. 173 rows have a `Border` below 3:1 against `Background`, and 30 rows have a `Primary` below 3:1 against `Background`. Only one row has a text pair below 4.5:1. A border only needs 3:1 when it is the sole edge of a control, so the first figure matters less than the second. `design_lookup.py` reports the failures for each product type. The Notes column marks some palettes as adjusted for contrast, but not all.
- `styles.csv`: 9 rows are `deprecated` and 17 are `Mobile` type. The lookup marks deprecated styles; mobile rows are included because some are useful as references.
- `motion.csv` and `styles.csv` disagree on the subtle hover duration (150 to 200ms against 200 to 250ms). Use the tiers in `layout-and-motion.md`.
- The Material Motion 3 mapping of those tiers is recorded in `layout-and-motion.md` (§ Material Motion mapping); `motion.csv`'s GSAP vocabulary and snippets stay precedent-only.
- `ui-reasoning.csv`: the Confidence and Reasoning columns are blank for most rows.
- `ux-guidelines.csv`: "Font Loading" appears more than once.
- Trend styles (glassmorphism, neon and similar) are the first recommendation for several product types. Weigh them against the brief.
- `charts.csv`: the Accessibility Grade column is schema residue — it contains the literal string "deprecated: use Accessibility Risk" in all 25 rows, so read the Accessibility Risk column instead; the tension between the Color Guidance hexes and the plugin's OKLCH role system is adjudicated in `references/charts.md` (§ 与 vendored 数据的张力裁定), where the role system wins and the rows stay precedent evidence.

## Refreshing

Copy the eight files again from a newer commit, then run the fixtures and tests in the plugin's `tests/` folder. The scripts read columns by name; if a column is renamed upstream, update `design_lookup.py` to match.
