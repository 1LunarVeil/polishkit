---
description: Review a UI for visual quality, accessibility and generic-default tells (read-only)
argument-hint: "<path, directory, URL or screenshot>"
---

Review this UI with the polishkit critique procedure: $ARGUMENTS

1. Read the skill's `references/critique.md` and follow its steps in order.
2. Render and capture: follow the skill's `references/visual-review.md`. Use `scripts/visual_capture.py` (it waits for a settled frame) or the agent's own browser tool. Capture default, narrow and 150%-scale views, plus empty, loading and error states. Over CDP, add `--dark` (real `prefers-color-scheme` emulation) and `--hover`/`--focus`/`--element`/`--full-page` for the states plain screenshots cannot reach; the JSON states which engine ran. Look at the images.
3. Run the skill's `scripts/slop_scan.py` and `scripts/token_lint.py` over the UI source paths. Run its `scripts/wcag.py` on the text and UI pairs in the token file. When the page can be served, run `scripts/page_audit.py` on it: it separates measurable contrast verdicts from uncertain ones.
4. Report findings grouped as blocking, important and polish. Each finding gives its location, its evidence and its fix. Include the Visual section with the captures you looked at, then the three changes that would move the design most, and what was not checked.
5. If no browser could be reached, say "not visually verified", name the skipped states, and make no claims about rendering. Do not present a code-only review as a visual one.
6. Do not edit files. Offer to apply the fixes and wait for the answer.
