# CJK typography (中文排版)

Scope: Chinese-heavy UIs and mixed CJK/Latin text. The Latin rules stay in `color-and-type.md`. Sources: W3C《中文排版需求》clreq, cited by clause (https://www.w3.org/TR/clreq/); Better Web Type for the vertical-rhythm anchor (https://betterwebtype.com/rhythm-in-web-typography/). clreq gives layout *requirements*; it does not give UI-specific numbers except where noted, and this file says so instead of inventing them.

## 中英混排 (mixed scripts)

- clreq §2.1.3: "汉字与西文字母、阿拉伯数字间使用不多于四分之一个汉字宽的字距或空白。但西文出现在行首或行尾时，则毋须加入空白。" Rendered spacing is the browser's job: `text-autospace: normal` where supported (support is still evolving — treat it as progressive enhancement, and let `page_audit`'s uncertain class absorb layout differences). Do not hand-insert hair spaces into source copy: hand-spaced strings break i18n, search and the break test.
- Pick one convention per product for numbers in Chinese copy (第 3 版 vs 第3版) and write it into the copy guide; both are compatible with the ≤¼-em rule.
- The stack order in `color-and-type.md` (Latin face first, CJK fallbacks after) is deliberate: Latin glyphs come from the first face, CJK falls through to YaHei/PingFang. Reversing it degrades Latin rendering.

## 标点 (punctuation)

- Quote forms: 横排用弯引号 " " ' ', 直排用直角引号 「『 (clreq §2.1.2).
- Regional position: 大陆的标点多位于字面末端（跟随文字），港台多位于字面正中 (clreq §2.1.2). It changes perceived spacing — never mix regional conventions inside one product.
- 行首行尾禁则 (clreq §3.1.6 and §6.1.1): 点号（、，。：；！？）与结束引号、括号、书名号不得起行；起始引号、括号、书名号不得收行。Browsers do this by default for CJK runs (`line-break: auto`); `word-break: break-all` on CJK prose disables it — that is a tell, not a fix. clreq also records three processing tiers: 基本处理, GB 法 (stricter, per GB/T 15834—2011), and the MediaWiki line-end squeeze common in 港台报刊.
- 悬挂与挤压: `text-spacing-trim` (Chromium) is the CSS lever for 标点挤压; support is partial, so capture and look rather than assume.
- 连用标点: 问号与叹号连用占一个字位置，最多连用三次 (clreq §5.1.1.3, citing GB/T 15834—2011).

## 行高与节奏 (line height and rhythm)

- The 1.6–1.75 CJK body range in `color-and-type.md` stays: clreq does not hand out a UI line-height number. The one hard anchor is §5.5.3.2 — where annotation (ruby) exists, paragraphs need line spacing of at least 1.5× the base character size, and spacing must not change when annotations appear.
- Vertical rhythm (Better Web Type): "use the line height as a base unit for every size, margin and padding on the site" — heading line-height an even multiple of the base line-height, heading bottom margin noticeably smaller than its top margin. CJK inherits this unchanged; the 8px grid and a 1.75 line-height must be reconciled by choosing sizes that land on the grid, not by tracking.
- CJK letter-spacing: no tracking on CJK body text — 汉字 are equilateral squares and tracking breaks the grid; the avoid-rule "Letter-spacing added to body text" in `color-and-type.md` applies doubly here. Display-heavy headlines may take small positive tracking only when the brief asks.

## 字重与字体栈 (weights and stacks)

- System weight availability is uneven: Microsoft YaHei ships Light/Regular/Bold (the UI variant likewise), so a 500 or 600 on Windows renders snapped or synthetic — verify the deployment before designing a five-weight scale. PingFang SC carries more steps; Noto Sans SC carries a full range when self-hosted and subset.
- Synthetic bold smears CJK stroke endings — a tell. If the design needs 600, the font must provide it: subset Noto Sans SC (per the "do not bundle a full CJK font" rule in `color-and-type.md`) or accept a two-weight system.

## 与现有规则的关系

- Extends `color-and-type.md` (stacks, line-height, "Do not use italic for Chinese or Japanese text") and `components-and-states.md` (the break test).
- The "All-caps Chinese text" avoid-rule stands as written: caps carry no meaning in Chinese, and clreq adds no counterweight.
- CJK measure 30–40 full-width characters (`color-and-type.md`) remains a heuristic — clreq does not give a UI measure number; test on a real paragraph.

## 测试要点 (break test additions)

- A long CJK run with no spaces (shows word-break damage).
- Mixed runs: CJK+Latin+digits in both spacing conventions (第 3 版 / 第3版).
- A punctuation-heavy run (……？！）「」) across a line boundary — the 禁则 must hold.
- CJK text inside the 320px reflow viewport (WCAG 1.4.10) and in the dark theme — punctuation trimming and autospace visibly change layout between engines.

## 刻意不采用

- 直排 (vertical text): clreq covers it thoroughly; no current target renders vertical UI text. Deferred until a brief asks.
- The full 禁则 character table: it lives in clreq §3.1.6's punctuation table, browsers implement it, and reproducing it here would rot.
- 纵中横排 (text-combine-upright): same reason as vertical text.
