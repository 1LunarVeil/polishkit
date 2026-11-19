---
description: Run every mechanical polishkit check against a UI and report one merged verdict (read-only)
argument-hint: "<path, directory or URL>"
---

Run the full mechanical sweep for $ARGUMENTS and report a single verdict. This
is the objective half of a review: it measures what a rule can see and states
plainly what it cannot. Do not present its result as an aesthetic judgement.

1. Read the skill's `references/critique.md` for severity wording and
   `references/visual-review.md` for the capture protocol.

2. Source checks. Run from the skill's base directory and record each exit code:

   ```
   python scripts/slop_scan.py <source paths>
   python scripts/token_lint.py <token file and source paths>
   ```

   slop_scan exit 1 means blocking findings. token_lint reports
   definition-site contrast, `RAW-LEAK`, missing semantic roles and off-scale
   values.

3. Rendered checks, when the UI can be served on loopback. Both audits need a
   browser and say so if none is found — never substitute a guess:

   ```
   python scripts/visual_capture.py <URL> --out shots --matrix --dark
   python scripts/page_audit.py <URL>
   python scripts/keyboard_audit.py <URL>
   python scripts/text_spacing.py <URL>
   ```

   `page_audit` covers 1.4.3 contrast pairs, 2.5.8 target size and the
   4.1.2/1.1.1 name subset. `keyboard_audit` covers 2.1.1 reach, 2.1.2 traps,
   2.4.7 / 1.4.11 focus visibility and indicator contrast, 2.4.11 obscured
   focus, and 1.4.3 in the focused and hovered states. `text_spacing` covers
   1.4.12. Look at the captured images too; a passing audit is not a visual
   review.

4. Report, in this order:

   - **Blocking** — any slop_scan blocking finding, any `page_audit` FAIL, any
     `keyboard_audit` FAIL, a console error, a blank or unsettled capture, an
     unreachable browser or a rejected URL.
   - **Important** — token_lint important findings, audit findings whose
     severity is important.
   - **Review** — `keyboard_audit` REVIEW lines (traps inside dialogs, positive
     tabindex, hover/focus collisions, reading-order deviation) and
     token_lint review findings.
   - **Uncertain** — every `uncertain:*` line from either audit, with its
     evidence, and the reason it cannot be measured (gradient, image, texture,
     page-restored focus). These need a person looking at a capture.
   - **Not checked** — states the tools skip, stops walked but not photographed
     (`keyboard_audit --measure`), and anything needing a manual pass
     (reduced motion, text spacing, zoom reflow).

5. Every line names its file or element and the number behind it. Do not edit
   files; offer fixes and wait.
