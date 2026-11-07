# B5 — jfmt landing page (treatment-v3: expression layer)

## Brief

- Subject: landing page for `jfmt`, a CLI-first JSON formatting tool ("gofmt, but for JSON")
- Audience: developers arriving from a README link or search; they decide in 30 seconds
- Job: let the tool prove itself on the spot — the working formatter IS the hero — plus one copyable install command
- Density: comfortable; docs-like directness, no marketing fluff
- Languages: en-US
- Refusals (carried from v1): (1) no dark acid-green hacker-terminal look; (2) no gradient SaaS hero and no three-feature-card row; (3) no fake testimonials or logo wall

## Precedents (design_lookup, re-run for v3)

`python skills/polishkit/scripts/design_lookup.py "developer cli tool json formatter" --ux --motion`
→ Developer Tool/IDE. First style is again literally "Dark Mode (OLED)" — refusal 1 verbatim, rejected on sight. Taken: "Minimalism & Swiss Style" + the "Minimal & Direct + Documentation" landing pattern (demo-first), Flat Design's 150–200ms clean transitions. Bento rejected (refusal 2).

## Direction

**Direction 9 "Raw brutalist", adapted — same direction that earned the v1 tie, now with the expression layer.** Paper #F4F1E8 / ink #000000 / visible structure stay (they are the register developers trust); what moved is the accent.

**Palette movement:** the direction-table accent #FF3B00 (generic confrontation red) → **amber phosphor #FFB000** (fill-only, with ink text 11.46:1) + **amber-ink #8A5800** for oversized stat text (5.35:1 paper / 6.04:1 white / 4.94:1 inset). Rationale: amber-phosphor terminals are real CLI heritage, it sits warm against the paper like the syntax colors' warm end, and it kills v1's awkward "accent fails as focus color" split — focus is now 3px ink (18.59:1). #FFB000 is never used as text or as a UI boundary on paper (1.62:1 — hard fail, and it never carries meaning alone).

## Token block

```css
--paper:#F4F1E8; --paper2:#F1EDE1; --ink:#000000; --muted:#565147; --inset:#ECE8DE;
--rowline:#D9D2C5;      /* decorative table row rules only (Direction-1 precedent: quiet dividers are allowed) */
--accent:#FFB000;       /* fill-only + ink text */
--amber-ink:#8A5800;    /* oversized stat text */
--key:#0072B2; --str:#1F6E43; --lit:#B42318;  /* syntax on white, AA */
--mono:Cascadia/Consolas (display + code); --sans:Segoe UI (prose); --serif:Georgia italic (one moment)
type: 13 / 16 / 22 / 28 / 60(h1) / 76(stat); motion: 80ms steps, hover = 2px move + shadow shrink (direction 9's own motif, buttons only)
```

## Expression checklist (the six items, with what was actually done)

1. **Type drama — display ≥ 3× body, both weight ends.** h1 in Cascadia 700 at 60px (3.75× the 16px body), tracking −0.03em, line-height 1.05 against body 1.55. Weights reach both ends: 700 (h1, wordmark, buttons, dt, table headers) against **300** — the Numbers section's real figure "164" set at 76px in Segoe UI Light, tabular, −0.02em: oversized content as ornament, real information wearing display clothes. The one serif moment is the kicker `“gofmt, but for JSON.”` in Georgia italic (the Go ancestry, cited).
2. **Exactly one asymmetry, one full-bleed/overlap moment.** Asymmetry: the hero is left-anchored — narrow prose column and install block hang left while the void concentrates right of the ragged 60px display line; nothing balances them above the terminal. Full-bleed: the playground terminal is a plate that **bleeds 26px off the right viewport edge** (its right border genuinely cut, `overflow-x:hidden`); the output text runs to the cut. Same left-mass asymmetry repeats in Numbers (giant 164 + void right) so the page has one tension, not several.
3. **Exactly one focal point, two levers.** The terminal: scale (the largest object on the page, ~700×460) + contrast (white field, 2px ink border, 8px ink offset shadow — the highest-contrast object against paper) + isolation (paper void around it). The display line steps aside in weight-vs-mass; everything else is quieter.
4. **Texture on hero-scale fields.** The paper itself is the hero-scale field: warm tint gradient (#F4F1E8→#F1EDE1) + feTurbulence grain (~3%) over the whole page, plus grain inside the terminal head inset. No dead-flat field anywhere.
5. **Softened skeleton.** v1 ruled everything with 2px ink borders (top bar, why-box, every table cell). v3: top bar keeps only space (no rule); the why section drops its box and inner rules entirely (a 230px mono dt column + space does the work); the bench table keeps only functional row rules (1px #D9D2C5) under a 2px ink header rule; the terminal and install rows keep their 2px ink borders — controls that look like controls. **One organic divider:** the pour line — a single gently falling SVG wire with one amber node, the byte stream feeding the Numbers section. **One rotated accent:** the "byte-stable" stamp (−2°, amber fill, ink border) sitting over the terminal's top edge.
6. **Signature.** The working formatter demo, kept real and presented harder: line-number gutter in the output pane (real line count, non-selectable), byte sizes on both panes, indent/sort/compact controls, live status "formatted 15 lines in 0.1 ms", V8 parse errors rewritten as "line X, column Y", Ctrl+Enter, empty state that restores the sample, 100 MB-class guard with "Working, N KB…". Remove it and the page is a generic brutalist zine — it stays the most-crafted thing.

## Render → look → fix (what I saw and changed)

- First capture: strongest hero so far, but **the term-head controls were cut by the bleed** — the classic `margin:calc(50% - 50vw)` trick resolved `50%` against the grid column, overshooting ~340px past the viewport, clipping the indent select mid-option. Fix: viewport-relative formula `calc((1124px - 100vw)/2 - 26px)` (+ media fallbacks); added 44px right padding to the head and pane labels so controls/size readouts stay inside the visible plate.
- Second capture: head controls fully readable; the Format row was still a sliver below the fold. Fix: code line-height 1.55→1.45, pane min-heights 224/210 — third capture shows the complete signature in the first viewport: display line, install, stamp, gutter output, Format button and live status all above the fold at 1280×800.
- Full-page review: why rows, pour line, giant 164, row-ruled table and install rows all read; the partial "measuring, run takes a while" row ships as the honest partial state (completes on the live page after ~2.2s).

## Verification (real tool outputs)

- `wcag.py` (all shipped pairs): #000000 on paper 18.59 / white 21.0 / inset 17.16 · #565147 on paper 6.98 / white 7.88 / inset 6.44 · #8A5800 on paper 5.35 / white 6.04 / inset 4.94 · #000000 on #FFB000 11.46 (fills: Copy/Format/stamp) · syntax on white #0072B2 5.19 / #1F6E43 6.23 / #B42318 6.57 · focus 3px ink on paper 18.59 (≥3 UI). #FFB000 as text/graphic on paper = 1.62 → never shipped as text; used fill-only. All text ≥4.5; UI/graphic pairs ≥3.
- `slop_scan.py index.html` — **0 blocking, 0 important, 2 review, 0 polish (exit 0)**. The two HOVER-LIFT findings are the direction-9 hover ("moves the element 2 to 4px and shrinks its offset shadow") applied to exactly the two button classes and nothing else — the same deliberate, documented exception v1 recorded.
- Inline JS verified with `node --check` (extracted script): OK. Tokenizer logic unchanged from v1 (v1 round-trip tested); v3 adds only the post-highlight line-gutter split (JSON strings cannot contain raw newlines, so spans never break).
- `visual_capture.py` over `http://127.0.0.1:8611/B5/index.html?freeze`: hero 1280×800 and full-page 1265×2317 — `settled: true`, `blank: false`, `console_errors: []`. `?freeze` boots the demo instantly and holds the 100 MB bench row in its partial state for stable frames; the default page boots at 400ms and completes the row at ~2.2s.

## States covered (and where they live)

- Loading: demo boots with a 400ms skeleton, then the live demo (capture shows the post-boot working state).
- Empty: empty input → output pane explains and Format restores the sample.
- Error: invalid JSON → status "1 parse error" + diagnostics line with line/column and next step.
- Disabled: Copy buttons disable 1.2s with "Copied"; Format disables as "Working, N KB…" on large inputs.
- Partial data: 100 MB bench row ships as "measuring, run takes a while / —" and completes after the page settles.
- Focus/keyboard: Ctrl+Enter formats; 3px ink focus outline distinct from the hover move; reduced-motion kills the button transitions; status line is aria-live.

## Not verified (honest boundary)

- Hover/tooltip and error states beyond code review (the capture loop covered the default render); the demo is a faithful JS re-implementation, not the Rust binary; the benchmark table is static sample data labeled one-machine; the GitHub link is a plain hyperlink to a fictional repository (no request is made); dark theme intentionally absent (refusal 1).
