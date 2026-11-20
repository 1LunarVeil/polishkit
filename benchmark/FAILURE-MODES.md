# 失败模式库

> 从三条件基准的**实际失败**中提炼，不是预设的分类。每条都给出真实样本、可测的判据、
> 修复方向，以及它在哪个条件里实际出现过。数据来源：`RESULTS.md`，测量环境见
> `ENVIRONMENT.json`。
>
> 用法：评审时先用工具跑，再把命中项对照这张表——**表描述的是"什么样的页面会失败"，
> 不是"什么样的页面好看"**。

## 一、地板类（工具直接判 FAIL）

### F1 对齐线性布局没做窄屏重排

- **判据**：`reflow.py` 的 `OVERFLOW` 或 `WIDER` — 320 CSS px 下文档横向滚动，或元素越过视口。
- **真实样本**：bare B1「at 320 CSS px the document is 280px wider than the viewport (600 vs 320)」；
  30 处 `WIDER`（如 `input#modelSearch is 169px wide and ends at x=418`）。
- **根因**：桌面网格用固定列宽，最窄断点设在 900+ px。
- **修法**：加 520px 级断点，折叠固定轨道；表格进横向滚动容器（1.4.10 明示例外）。
- **出现**：bare 21 处、baseline 28 处、treatment 原始 34 处。**三者都中，说明这是最普遍的失败。**

### F2 固定宽度容器

- **判据**：`reflow.py` 的 `FIXED-W` — `width` 是 px 字面量且大于视口。
- **真实样本**：12 处「`div.card` has a fixed width of 402.234px at a 320px viewport」。
- **根因**：卡片/面板写了 `width: 400px` 而非 `max-width`。
- **修法**：改 `max-width`，或宽度用 `%`/`ch`/`clamp()`。

### F3 焦点环不可见

- **判据**：`keyboard_audit.py` 的 `NO-FOCUS`（两态帧完全相同）或 `LOW-CONTRAST`
  （变化低于 3:1，或环对周围颜色低于 3:1）。
- **真实样本**：16 处「focused and unfocused frames are identical; the control shows no focus
  indicator at all」（bare + baseline）。
- **根因**：`outline: none` 无替代；或环色与控件填充同色（treatment 原始 B3 的柱状图，
  环用 `--accent` 而柱体填充也是 `--accent`，实测 1.01:1）。
- **修法**：`outline: 3px solid` + `outline-offset: 2px`，颜色不能等于控件填充。
- **注意**：`outline: auto` **计算值恒报 1px**，`box-shadow` 与 `::after` 环在计算样式里
  没有 outline——**只有像素测量能发现**。

### F4 键盘陷阱

- **判据**：`keyboard_audit.py` 的 `TRAP` — Tab 循环在页面的严格子集里。
- **真实样本**：1 处「focus cycles among 4 of 7 tabbables (a["Getting here"], a["Rooms"],
  a["The house"], input#checkin); the page never reaches its own end」。
- **根因**：keydown 处理器无条件 `preventDefault()` 并把焦点弹回。
- **修法**：只在真正的模态上下文里循环；提供 Escape 出口。
- **注意**：对话框内的循环是**预期行为**，工具报 review 不报 FAIL。

### F5 文本间距被裁切

- **判据**：`text_spacing.py` 的 `CLIP` / `TRUNCATION` / `FIXED`。
- **真实样本**：4 处「`span.q` (clipped by `div.m-name`) hides its own text once the spacing is
  applied: content needs 211x19, the box gives ...」；4 处 truncation。
- **根因**：`white-space: nowrap` + `text-overflow: ellipsis` + 固定高度。
- **修法**：允许换行，或给容器留出 1.5× 行高的余量。
- **出现**：treatment 原始 11 处、baseline 8 处，bare 0（页面太简单，没触发）。

### F6 CJK 禁则被破坏

- **判据**：`cjk_breaks.py` 的 `LINE-START`（行首是收尾标点/括号）或 `LINE-END`（行尾是起始括号）。
- **真实样本**：1 处（baseline B4）。
- **根因**：`word-break: break-all` 关掉浏览器禁则；或行内元素边界让 `「` 与后文成为独立断点。
- **修法**：移除 `break-all`；引述段包进 `white-space: nowrap` 的 span。

### F7 文字对比度不足

- **判据**：`page_audit.py` 的 1.4.3 — 低于 4.5:1（大字号 3:1）。
- **真实样本**：bare 48 处、baseline 105 处、treatment 0。
- **根因**：浅灰文字压浅底；渐变上叠字；品牌色当正文色。
- **注意**：**fail 数要与页面野心一起读**。bare 的 48 少于 baseline 的 105，因为裸模型页面
  更小更保守（99KB vs 138KB），不是更守规矩。

## 二、结构类（工具判 review，需要判断）

### F8 首屏注意力分配失衡

- **判据**：`expression_audit.py` 的 `ATTENTION` / `LADDER` — 最响元素所在列填充低、
  下方空白大、字号阶梯断层。
- **真实样本**：treatment B3「`div#big-fig` at 70px (£1,847), 11 other text items in its band,
  40.4% of its column filled, 62px of blank」。
- **根因**：单个数字被放大到视觉主导，而页面的工作内容（图表、列表）被推到折叠线以下。
- **修法**：压缩 hero 垂直节奏，让工作内容进首屏；不是缩小数字本身。
- **注意**：**带内有图像时工具报 uncertain**——摄影页的空白是构图，仪表盘的空白是荒漠，
  几何相同、意图相反，只有人能分辨。

### F9 字号阶梯断层

- **判据**：`expression_audit.py` 的 `LADDER` — 相邻字号比超过 1.8 且列填充低。
- **真实样本**：B3 的 `70 → 22px`。
- **根因**：只有"巨数"和"正文"两级，中间没有 30–50px 的过渡层。
- **修法**：补中间档（小标题、区段标题），而不是缩小巨数。

### F10 一个根因产生一打重复发现

- **判据**：不是页面缺陷，是**评审方法**缺陷——同一个未重排的容器产生几十条同形 finding。
- **真实样本**：B1 的 hero 容器五个后代都在 x=386，原始报 106 条 WIDER。
- **修法**：工具层按共享右边缘分组（已实现），报告只列代表并注明「and N more」。

## 三、刻意不建模的

- **审美高下**：`expression_audit` 只报数字与提问，不下结论。字阶比 4.75–6.74× 是"有戏剧性"
  还是"过冲"，由维护者裁决（已裁定不算过冲）。
- **文案质量**：错误信息是否说清"发生了什么、该怎么办"——需要读，不能量。
- **状态设计**：空/错误/加载态是否像状态而非坏页——需要看截图。
- **reduced-motion 是否真的尊重**：`prefers-reduced-motion` 需要真实系统设置，
  静态检查只能看有没有写媒体查询。

## 版本

- 建立于 2.2.10（2026-11-20），数据来自三条件 × 5 页的实测。
- 每条判据都指向具体工具与检查名，工具变更时本表要跟着改。
