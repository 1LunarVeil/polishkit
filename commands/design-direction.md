---
description: Propose and lock a visual direction for a UI brief before building it
argument-hint: "<brief or product description>"
---

Set the visual direction for this brief with the polishkit skill: $ARGUMENTS

1. Read the project's brief or contract first (DESIGN.md, PRODUCT.md, token files, contract documents). If one exists, it governs, and this step's output must not contradict it.
2. Write the brief in the format of the skill's `references/principles.md`. Fill unknowns with stated assumptions instead of asking questions, unless the user is clearly available and the choice is about taste.
3. Run `python scripts/design_lookup.py "<keywords — Chinese or English>" --ux --motion` from the skill's base directory; add `--charts` when the product displays data. Note what the data suggests, and what it gets wrong for this brief.
4. Propose two directions from the skill's `references/directions.md`, or one custom direction. For each, give the palette roles, the type pairing, the shape language, the motion character and the signature element. Check every text pair you propose with the skill's `scripts/wcag.py`.
5. Recommend one. Say why it fits the brief and why the other does not. Name the three refusals.
6. Do not write component code in this step unless asked. End with the token block the build should start from.
