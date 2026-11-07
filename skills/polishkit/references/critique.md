# Critique procedure

Use this when someone asks for a review, and as the last check before reporting a visual change. A review is read-only: report findings and offer fixes, and edit files only when asked.

## 1. Scope and brief

State the target: a file, a directory, a URL or screenshots. Read the project's brief or contract if one exists. If none exists, write three lines of brief from the product and the screen, and say they are assumptions.

## 2. Capture

Use `references/visual-review.md`. In short: get the UI renderable, capture with `scripts/visual_capture.py` (it waits for two identical frames, so a half-rendered shell is not mistaken for a design), and look at the images. At minimum, capture the default, narrow and 150%-scale views; add empty, loading and error states, and capture the dark theme with `--dark` — over CDP this really emulates `prefers-color-scheme` instead of only naming the file. `--hover`, `--focus`, `--element` and `--full-page` capture the states the legacy engine could not reach; the JSON reports which engine ran, and a fallback to the legacy path is stated there honestly.

Console errors count as failures. A `blank` capture counts as a failure. An unsettled capture is suspect.

Only when no browser can be reached at all, say "not visually verified", list the states you skipped, and make no claims about rendering, density or colour as seen. Do not replace the capture with a description of what the code should produce.

## 3. Mechanical checks

- `python scripts/slop_scan.py <paths>` over the UI source. Exit status 1 means blocking findings exist.
- `python scripts/token_lint.py <paths>` when the project has a token file: it audits definition-site contrast, raw-value leaks (`RAW-LEAK` superseded the scanner's old raw-hex heuristic), missing semantic roles, unused tokens and off-scale values.
- `python scripts/wcag.py FG BG ...` for each text and UI pair in the token file. `--apca` adds a draft APCA Lc reading; treat it as supplementary evidence, never as the gate.
- `python scripts/page_audit.py <URL>` when the page can be served: it audits every visible text pair for contrast (1.4.3), pointer target sizes (2.5.8) and accessible names (4.1.2/1.1.1 subset), plus heading-order reviews, and separates measurable verdicts from uncertain ones (inline links in paragraphs are reported as uncertain per 2.5.8's Inline exception). It supplements, never replaces, the capture loop.
- The break test from `components-and-states.md`, run against the code paths for long or empty data, or in the browser with real data.

The scanner finds patterns. Each hit still needs a judgement: `outline: none` is a problem only when no focus style replaces it, and an all-caps label can be right.

## 4. Pillar review

Check each pillar. Skip none, but write "no issues" where that is true.

1. Direction: one idea is visible; the screen could not be mistaken for a different product; one signature element appears once; the signature is the single highest-crafted thing on the page — hand-built or a real capability, never a placeholder; the three refusals are honoured.
2. Hierarchy: the first three things seen match the job; one primary action per region; grouping by proximity holds; the type setting carries drama — display at least 3× body with weights reaching both ends of the family, not one even scale.
3. Color: roles follow the token set; the accent covers about 10% or less; semantic colors match across screens; the dark theme is a ladder, not an inversion; no meaning is carried by color alone.
4. Typography: at most two families plus a mono face; one scale ratio; prose measure 45 to 75 characters; tabular numerals in numeric columns; no text under 12px; no all-caps except short labels.
5. Space and density: spacing from one scale (GOV.UK's is a 5px-unit scale, units 0-9, responsive above 640px — design-system.service.gov.uk/styles/spacing); density fits how often the screen is used; no equal gaps everywhere; no card inside a card.
6. Shape and detail: radii from one scale and nested correctly; at most three elevation levels, tinted; one icon family, optically aligned beside text; no doubled borders; the composition holds one deliberate break (asymmetry, overlap or full-bleed) and one focal point the eye can find in a second — a fully even, fully aligned page is a tell.
7. Motion: each animation has a purpose from `layout-and-motion.md`; durations sit in their tiers; only transform and opacity animate; reduced motion is handled; nothing flashes.
8. States and copy: every state from the matrix exists; the break test passes; errors say what happened and what to do; action names match their results; no placeholder or invented data.
9. Accessibility floor: text and UI contrast; visible focus; labelled controls; keyboard order; target sizes; the layout survives 200% zoom (WCAG 1.4.4) and 320 CSS pixels of width (1.4.10); text spacing does not clip (1.4.12). The mechanical subset is now checked by `page_audit.py`: 1.4.3 contrast pairs, 2.5.8 target size (24x24 CSS px; inline links in paragraphs come back uncertain under the Inline exception — judge those by eye), and the 4.1.2/1.1.1 name subset (unnamed buttons, links, images and form fields). Spacing under 1.4.12 stays a manual check, as does focus visibility and keyboard order.
10. Platform conventions: the window's platform wins over the framework — native accelerator keys, materials and control metrics are honoured or deliberately broken (checklist in `native-feel.md`).

## 5. Severity

- Blocking: fails a floor. Contrast below the minimum, no visible focus, unlabelled controls, clipping with realistic data, lost user input, or a state that hides an error.
- Important: a visible inconsistency, a generic default in a prominent place, a missing state, or a motion problem that distracts.
- Polish: refinement that improves the screen but does not fix a defect.

## 6. Output format

Group findings by severity. Each finding is one line:

```
Blocking
- [Accessibility floor] settings.css:211 - focus outline removed on .toggle with no replacement; add a 2px focus ring at 3:1 against the surface.

Important
- [Typography] panel.css:88 - 11px labels in a data table; raise to 12px minimum and check the row height still fits.

Polish
- [Shape] cards.css:40 - four different radii on sibling cards; use the nearest step from the scale.
```

After the list, give:

- A Visual section in the format from `visual-review.md`, with the captures you looked at and the states you skipped.
- Top three changes, ordered by how much they would move the design.
- What was not checked, and why (for example, no browser available, or no dark-theme capture).

Do not list praise. Do not list more than about 30 findings; if there are more, say so and group them by file.

## 7. After a change: close the loop

When you apply a fix, do not report it as done from the diff alone. Capture the same views again to a second directory, then compare:

```
python scripts/image_diff.py shots/wide-1440x900-light@1.png shots2/wide-1440x900-light@1.png
```

- The changed region should cover what you claim to have changed. If it does not, the change did not reach the render.
- If the diff is empty, the claim is false. Say so.
- Look at the new capture too. A diff proves something changed; only your eyes prove it changed for the better.

## 8. Before reporting

Read the findings once more against the ten pillars. Remove any finding you cannot support with a location and evidence. Keep blocking findings; they are not optional. If a visual claim has no capture behind it, delete the claim.
