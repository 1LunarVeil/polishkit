# Anti-slop: tells, reasons and questions

A "tell" is a choice that shows up on almost every generated interface because nobody made it for the brief. This list is not a ban list. A flagged default is fine once it has been chosen, and the question in each row is how to make that choice.

The rule ID column matches `scripts/slop_scan.py`. Rows without a rule ID are judgement calls the scanner cannot see. Severities follow the floors: only accessibility-floor violations are blocking, craft defects are important, taste tells are review — a decision, not a defect.

| Tell | Why it reads as a default | Ask instead | Rule |
|---|---|---|---|
| Inter, Roboto, Arial or Open Sans as the main face | the statistically safest choice | Which face says something about this subject? Would a system stack do the job? | TYPE-DEFAULT-PRIMARY |
| Purple-to-blue gradient accent | the most common generated accent | What hue comes from the subject's own world? One flat accent may be enough. | COLOR-PURPLE-GRADIENT |
| Warm cream background with a terracotta accent | a widely copied "warm" recipe | What does warmth mean here: paper, wood, or nothing at all? | |
| Near-black with one acid-green or vermilion accent | a widely copied "edgy" recipe | Does the product need night use or glare control? | |
| Hero, three feature cards, call to action | a template, not a structure | What must the first screen do, in one sentence? | |
| Equal cards in a grid, one radius, one shadow | no hierarchy is encoded | Which item matters most? Make it larger, or drop the card. | |
| The same soft grey shadow under every card | the default elevation | How many elevation levels does this product need? | COLOR-GREY-SHADOW |
| Fade and slide up on every section | a generic entrance | Which single moment should happen on load? | MOTION-GENERIC-ENTRANCE |
| `transition: all` | every property animates, often by accident | Which properties actually change? | MOTION-ALL |
| All-caps eyebrow label above every heading | template chrome | Does the label tell the reader anything the heading does not? | TYPE-CAPS |
| Middle-dot metadata, "A · B · C" | template chrome | Are all those fields needed? Give each a label. | COPY-MIDDOT-META |
| "WORD — fragment" labels with a spaced em dash | template chrome | Is this a name or a sentence? Write it as one of the two. | |
| An arrow after every button or link | template chrome | Does the control need an arrow, or a plain verb? | COPY-ARROW-CTA |
| "Submit", "Oops", "Something went wrong" | says nothing about the result | Name the action. Say what happened and what to do. | COPY-SUBMIT, COPY-GENERIC-ERROR |
| 01, 02, 03 markers on content with no sequence | structure without a sequence | Is there really an order? | |
| One headline word in italic or another color | emphasis for its own sake | Which single element deserves the emphasis? | |
| Monospace for every small label | a technical flavour by default | Is this value code-like? Then mono; if not, sans. | |
| Emoji as icons | inconsistent, unlabeled, platform-dependent | One icon family, labelled controls | EMOJI-ICON |
| Text under 12px, gray on gray | low-effort contrast | Run `wcag.py` on the pair. | TYPE-TINY |
| Raw hex, px or rgba values inside components | bypasses the tokens | Move the value into the token file. | RAW-LEAK (token_lint) |
| Lorem ipsum or invented metrics | placeholder left in | Use real data, or sample data that is labelled as sample. | COPY-LOREM |
| Pure `#000` surfaces | a harsh default | A tinted near-black, unless the brief is brutalist. | COLOR-PURE-BLACK |
| One duration for every transition | no motion decisions were made | Set a tier for each interaction. | MOTION-UNIFORM |
| Lift and shadow on every hover | a generic interaction | Change color or border only. | HOVER-LIFT |
| Glassmorphism, neon glow or bento grids for any product | trend picks | Does the trend help the job, or only the picture? | |
| Layout-property transitions | jank and surprise | Animate transform or opacity. | MOTION-LAYOUT |

## Structural tells the scanner cannot see

- The same section rhythm on every page: hero, features, testimonial, call to action. Vary the structure per page, so two briefs never share a template.
- Stat rows built from a large number, a small label and a gradient accent, used as the default treatment.
- Everything centred and symmetric, with equal padding everywhere.
- Copy that could belong to any product.

## Two tests

- Self-similarity test: strip the product nouns from the screen. If the layout, palette and type still read the same, the design is a template.
- Refusal test: check the three refusals from the brief. Each one should be visibly avoided.

## Recipes become defaults

A recipe copied from a reference becomes the next default. Keep the reasons a reference gives, such as "a dense table needs tabular numerals", and adapt its values to this brief.

Refusing a recipe is not refusing its ingredients. The warm-editorial recipe (cream + serif + terracotta) is a tell; a serif chosen for this subject is a decision. Compliant-but-timid pages happen when a recipe is refused along with every ingredient it used — refuse the combination, then earn the ingredients back one by one with subject-specific reasons.

## Judgments worth stealing

Concrete judgments extracted from the L2 sources (batch B). Each row carries its source. These have no rule IDs: they are decisions to make before generating, not patterns to scan. Scope note for Refactoring UI: the full book is paywalled, so only its official public previews, the official site, and the authors' public article were used — every claim below was read on those pages, not recalled.

| Judgment | The rule | Source |
|---|---|---|
| Hierarchy by weight and color, not size | Two text weights are enough for UI: 400 or 500 for most text, 600 or 700 to emphasize, never below 400. Two or three text colors: dark-but-not-black for primary content, grey for secondary, lighter grey for ancillary. De-emphasize with a lighter color or a smaller size, not a lighter weight. | Refactoring UI, "7 Practical Tips for Cheating at Design", tip 1 (medium.com/refactoring-ui) |
| Grey text on a colored background | Don't lighten a grey. Reduce contrast toward the background: lower the opacity of white text, or hand-pick a shade in the background's own hue. | Refactoring UI, tip 2 and the "Don't use grey text on colored backgrounds" chapter |
| Greys defined up front | 8 to 10 grey shades picked before work starts, on a 9-step scale: 900 darkest for text, 500 the button background, 100 the lightest tint. Generating shades on the fly is how you end up with "35 slightly different blues". | Refactoring UI, official preview "Building Your Color Palette" (refactoringui.com/previews/building-your-color-palette) |
| One shadow language | Offset shadows vertically, as if lit from above, instead of inflating blur and spread. The same applies to inset shadows on wells and inputs. | Refactoring UI, tip 3, "Offset your shadows" |
| Border restraint | Before reaching for a border, try a box shadow, two different background colors, or more spacing. | Refactoring UI, tip 4, "Use fewer borders" (also the sample tactic on refactoringui.com) |
| Spacing from one chosen scale | Establish the spacing and sizing system before designing. The local scale is the one in `layout-and-motion.md` (4 to 64px); the 4/8 increments there are this plugin's, not the book's. | Refactoring UI, "Establish a spacing and sizing system" (chapter title, official site) |
| Line-height pairing | Line-height and font size are inversely proportional: 1.5 suits narrow body text, wide content may need 2, and a large headline is fine at 1. | Refactoring UI, official preview "Line-height is proportional" (refactoringui.com/previews/line-height-is-proportional) |
| Labels are a last resort | Drop the "Label: value" pair when format or context identifies the data; fold the label into the value ("12 left in stock", "3 bedrooms"). When a label is needed it is de-emphasized, unless the user scans for the label itself, as on spec sheets. | Refactoring UI, official preview "Labels are a last resort" |
| Button pyramid | One true primary action per page, solid and high contrast. Secondary actions outlined or muted. Tertiary actions styled as links. A destructive action earns red only when it is the primary action of the screen, as in a confirmation dialog. | Refactoring UI, tip 7, "Not every button needs a background color" |
| Icons at intended size | Icons drawn for 16 to 24px look chunky blown up 3 to 4x. Enclose the small icon in a tinted shape instead of scaling it. | Refactoring UI, tip 5, "Don't blow up icons that are meant to be small" |
| Muted text is a token pair | Semantic colors come as background/foreground pairs: `--muted` with `--muted-foreground`, `--primary` with `--primary-foreground`. Muted text is a token, not a lower-opacity copy of the foreground. | shadcn/ui, Theming (ui.shadcn.com/docs/theming) |
| One radius variable | The radius scale derives from a single `--radius` by fixed multipliers (0.6, 0.8, 1, 1.4, and up). Per-component radius inventions are the tell this prevents. | shadcn/ui, Theming |
| Dark mode is a token override | Dark mode overrides the same token names in one `.dark` block, keeping the background/foreground pairing; it does not re-pick colors per screen. The shadcn defaults are near-monochrome: chroma enters through one primary and the five chart slots. | shadcn/ui, Theming |
