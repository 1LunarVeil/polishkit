# PolishKit

一个用于"让视觉决策有依据"的 agent 技能：先写 brief，再定方向，最后用可以跑的工具验证。它与官方 `frontend-design` 技能配合使用——后者提供立场（选定方向、不做没人选过的默认值），本技能提供决策规则、先例数据和检查手段。

支持 Claude Code、ZCode、Cursor、OpenAI Codex、VS Code Copilot，以及任何读取 Agent Skills 格式（`<技能名>/SKILL.md`）的 agent。需要 Python 3.9 或更高版本；不依赖第三方包，脚本不联网。截图功能使用机器上已安装的 Chromium 内核浏览器。

## 它是干什么的

让 agent"把这个做得好看点"，通常得到两种失败：长得像所有页面的平均值，或者悄悄踩了没人检查过的底线。本技能两边都管，并且要求 agent **看见结果再宣称完成**。

具体来说，它改变 agent 处理界面的四件事：

1. **先写 brief 再动手。** 主体、受众、密度，以及"绝不能像"的三条。然后是带理由的方向，不是情绪板。
2. **给数字，不给形容词。** 九个方向及算过的起始配色；间距、字号、动效刻度；状态矩阵；无障碍底线。
3. **给 agent 自查的工具。** 对比度、先例查询、痕迹扫描，以及"渲染→截图→修改→再截图"的回路。
4. **让结论可被证伪。** 如果说改动移动了某个区块，diff 必须覆盖那个区块；如果没有截图，就必须写"未做视觉验证"，而不是描述一个自己没见过的页面。

## 能做什么

| 能力 | 用什么 |
|---|---|
| 为新的或平淡的界面定视觉方向 | `SKILL.md` 步骤 1–4、`references/principles.md`、`references/directions.md` |
| 选出通过对比度的配色，含暗色主题 | `references/color-and-type.md` + `scripts/wcag.py`（hex、rgb、oklch） |
| 按产品类型查先例 | `scripts/design_lookup.py`，基于八个数据集，配色默认取对比度修正后的衍生数据集（原样数据保留） |
| 取目标桌面平台的清单 | `design_lookup.py --platform macos|windows|desktop`：窗口镶边、平台单位、控件尺寸、材质与快捷键（来自 `references/native-feel.md`），与 web UX 规则并列 |
| 找出源码里的通用"AI 味"和工程缺陷 | `scripts/slop_scan.py`，20 项检查（17 条行规则 + 焦点、reduced-motion、裸色值三项跨行检查），按严重度分级，有阻断项时退出码 1 |
| 按多种尺寸与缩放抓真实渲染 | `scripts/visual_capture.py`，等画面稳定，报告 console 错误与空白帧 |
| 审计渲染页面里每一对可见文字 | `scripts/page_audit.py`：可测的给判定，渐变/图片/遮挡显式归入 `uncertain` |
| 审计键盘路径与焦点环的实际渲染 | `scripts/keyboard_audit.py`：真实 Tab 走查、键盘陷阱、`tabindex="-1"` 控件、遮挡焦点、仅在 hover 失效的对比度，以及焦点环对它**所环绕控件**的像素对比度（2.1.1、2.1.2、2.4.7、2.4.11、1.4.11；2.4.13 作 AAA 参考） |
| 证明布局能撑住用户的文本间距覆盖 | `scripts/text_spacing.py`：注入 WCAG 1.4.12 的四项值，报告被裁切的卡片、`max-height` 盒子、丢掉文字的省略号标签，以及只在覆盖后才重叠的文字块 |
| 证明布局在 320 CSS px 下能回流 | `scripts/reflow.py`：在三个宽度下加载页面，报告横向滚动（1.4.10）及其成因元素，遵守二维版面例外，并给出 1.4.4 的文字缩放读数 |
| 按渲染结果审计中文断行 | `scripts/cjk_breaks.py`：逐行遍历，报告 clreq §6.1.1 禁则违规（收尾标点起行、起始括号收行），以及通常导致它们的 `word-break: break-all` |
| 读出一页如何分配注意力，再自己裁决 | `scripts/expression_audit.py`：首屏最响的元素、它所在列的填充率、字号阶梯与文字密度——只报数字与由此引出的问题，从不给分。带内有图像时报为 uncertain，因为矩形分不清照片与空洞 |
| 证明一次改动到底改到了哪 | `scripts/image_diff.py`，零依赖解 PNG，输出变化区域与比例 |
| 评审既有界面并给出分级结论 | `references/critique.md`（十个维度）与 `/design-review` |
| 跑完全部机械检查并给出合并结论 | `/polish-audit`：源码检查 + 两项渲染审计，阻断/重要/待复核/不确定/未检查分列 |
| 跨多页对比三项渲染审计 | `tools/crosscheck.py URL...`：一张表列出每条条款的失败数与不确定数，一眼看出"某维度干净但另一维度未测量"的页面 |
| 在桌面或 WebView 应用里套用这些规则 | `references/desktop-app.md` |

## 做不到什么

直说，免得用户自己踩到。

- **它不生成设计。** 它给模型规则、数据和检查；设计仍由模型完成。
- **它不判断美丑。** 它量对比度、抓模式、给你看前后两张图。好不好看仍由人决定。
- **它不是回归门禁。** `image_diff.py` 从不因"有差异"而失败：一次有意的重做可以改变每一个像素。它回答"改没改"，不回答"是不是变好了"。
- **它不带浏览器。** 截图需要机器上已装 Chrome、Edge 或 Chromium，且按绝对路径解析；没有就以退出码 2 结束并说明。
- **它不点击界面。** CDP 引擎抓得到 hover、焦点、暗色、元素与整页状态（`--hover`/`--focus`/`--dark`/`--element`/`--full-page`），`keyboard_audit.py` 会真实按 Tab 走查键盘路径——但从不点击：展开的菜单与多步流程仍需驱动型工具（如 Playwright）。过渡中间帧是刻意不抓的：截图等画面稳定再拍。
- **配色数据只是起点。** 它以两种形式交付：`colors.csv`（ui-ux-pro-max 原样数据，192 行里 173 行边框低于 3:1、30 行主色填充、1 行文字配对不达标）与 `palettes-corrected.csv`（衍生数据集，查询工具默认使用，全部不达标配对已调整到达标）。推导方式与再生成见 `data/PROVENANCE.md`。

## 引用与来源

本插件改写并综合了他人的工作，这里如实列出。

- **Anthropic 的 `frontend-design`** 提供了本技能所依托的立场，"截图自检"那句话是视觉回路的来源。
- **ui-ux-pro-max-skill**（Next Level Builder，MIT）提供八个 CSV 数据集，原样收录并在 `THIRD_PARTY_NOTICES.md`、`skills/polishkit/data/PROVENANCE.md` 中署名。
- **claude-dev-kit**（pillip，MIT）是"截图脚本 + 像素差异验收"的先例；本仓库的实现是独立写的。
- **buildwithclaude**、"4 design skills"那篇博文、**AI UX Playground** 目录与 **Learning AI** 章节提供了框架与流程思路，均为改写而非照抄。
- 逐条说明（包括刻意拒绝的内容及原因）见 `skills/polishkit/references/sources.md`。

`frontend-design` 是本插件要配合使用的对象，不是被替代的对象。

## 与 ui-ux-pro-max 的区别

八个 CSV 数据集收录自 ui-ux-pro-max-skill，数据重叠是设计使然，数据之外的东西不重叠：

- ui-ux-pro-max 带一个 CLI 引擎和更大的目录（图标、Google Fonts、落地页与 React 性能内容）。本插件只收录八个设计数据集，重写了查询（按名称加权匹配），并补上三样 ui-ux-pro-max 没有的东西：对报告的每条配色自动做 WCAG 对比度检查、带 CI 退出码的分级“AI 味”扫描器，以及证明改动真正落到屏幕上的渲染-截图-对比回路。
- 两者同时安装时，两个技能可能同时触发、先例查询跑两遍。不会冲突——名称、命令、数据路径互不相干——但其中一个是冗余的，只装本插件就够了。

## 安装

### 通用：任何支持 Agent Skills 的 agent

复制技能目录，确保 `SKILL.md` 的上一级目录名与技能名一致：

```
git clone https://github.com/1LunarVeil/polishkit
cp -r polishkit/skills/polishkit ~/.claude/skills/
```

| Agent | 项目级 | 用户级 |
|---|---|---|
| Claude Code | `.claude/skills/polishkit/` | `~/.claude/skills/polishkit/` |
| Cursor | `.cursor/skills/polishkit/` 或 `.agents/skills/...` | `~/.cursor/skills/...` 或 `~/.agents/skills/...` |
| OpenAI Codex | `.codex/skills/polishkit/` | `~/.codex/skills/polishkit/` |
| VS Code Copilot | `.github/skills/polishkit/` | `~/.copilot/skills/polishkit/` |

目录名必须与 frontmatter 的 `name` 一致。最常见的安装失败是多套了一层目录，导致 `SKILL.md` 藏进了子目录。

多个 agent 会共享部分目录：Claude Code 与 Copilot 都会读 `.claude/skills/`，Cursor、Copilot、Codex 都能读 `.agents/skills/`。因此装进 `~/.agents/skills/` 可以一次覆盖同一台机器上的多个 agent。

也可以用 `skills` CLI 从仓库直接安装：

```
npx skills add 1LunarVeil/polishkit --skill polishkit
```

### Claude Code 插件

```
/plugin marketplace add 1LunarVeil/polishkit
/plugin install polishkit@polishkit
```

### ZCode 插件

在插件市场中把本仓库目录（或本地 clone 的目录）添加为市场源，然后安装 **PolishKit**。清单在 `.zcode-plugin/plugin.json`。

### 不安装也能用

只需要一次任务时，把 `skills/polishkit/SKILL.md` 和该任务用到的 reference 文件一起给 agent。脚本可选，但建议使用。

## 怎么用

技能会按 description 自动触发，也可以直接点名。常用提示：

- "做设置页。先写 brief 和三条'绝不能像'，给两个方向，选一个，列出 token 块。"
- "评审这个界面：找出通用默认值痕迹和踩到的无障碍底线。"
- "现在的界面很平淡，在不破坏 token 契约的前提下重做视觉。"

装了命令后可用：

- `/design-direction 本地大模型启动器的深色优先 dashboard`
- `/design-review src/pages/settings`

一次合格的回复应包含：简短的 brief、带理由的方向、token 块，以及"验证"一节（列出执行过的命令和结果）。

## 工具

在 `skills/polishkit/` 目录下运行：

```
python skills/polishkit/scripts/wcag.py "#1f2937" "#ffffff" "#556070" "#f6f7f9"
python skills/polishkit/scripts/design_lookup.py "saas dashboard" --ux --motion
python skills/polishkit/scripts/slop_scan.py path/to/frontend/src
python skills/polishkit/scripts/visual_capture.py http://127.0.0.1:5173 --out shots --matrix
python skills/polishkit/scripts/image_diff.py shots/wide-1440x900-light@1.png shots2/wide-1440x900-light@1.png
```

- `wcag.py FG BG ...` 输出每对颜色的对比度，并给出 AA 正文（4.5:1）、大字号与 UI（3:1）、AAA 正文（7:1）的判定。支持 `#hex`、`rgb()`、`oklch()`；超出 sRGB 的 OKLCH 会像浏览器一样被裁切。`--apca` 追加草案版 APCA Lc 值，标注为补充信息；WCAG 判定仍是唯一门禁。
- `design_lookup.py "<关键词>"` 返回匹配的产品类型、样式、经过检查的配色、字体组合和推理规则，默认读取对比度修正后的衍生配色数据集（`--original-palette` 切回原样数据）。中文关键词经 `data/zh-keywords.csv` 映射；仍不达标的配色对附带调整建议值，并明确标注"仅建议，未应用"。加 `--ux`、`--motion`、`--charts` 追加更多段落。
- `slop_scan.py PATH ...` 把发现分为 `blocking`、`important`、`review`、`polish`，支持行级 `/* slop-ignore: RULE-ID */` 与项目级 `.sloprc`，另有 `--changed` 只扫 git 变更文件。存在阻断级发现时退出码为 1，可用于 CI；加 `--json` 输出机器可读结果。
- `token_lint.py PATH ...` 审计 token 文件：定义处的配色对对比度、裸值泄漏（带"该用 var(--token)"建议）、缺失语义角色、未使用 token、偏离刻度的值。
- `visual_capture.py URL --out DIR` 抓单张，或加 `--matrix` 抓标准矩阵（1440×900、1440×900@150%、1100×720、390×844）。CDP 引擎下 `--dark` 真实模拟 `prefers-color-scheme`，`--full-page`、`--element`、`--hover`、`--focus` 抓普通截图够不到的状态；任何 CDP 失败自动降级旧引擎，JSON 里如实标注本次用的引擎。它会反复抓直到连续两帧完全相同，避免把半渲染的空壳当成设计。退出码 2 表示找不到浏览器，3 表示 URL 被拒绝（仅 http/https、不以 `-` 开头、私网地址需显式加 `--allow-private`）。
- `page_audit.py URL` 遍历渲染页面，审计每一对可见文字：可测的给 pass/fail，渐变、图片、混合模式、遮挡这类算不准的显式归入 `uncertain`，绝不冒充判定。
- `keyboard_audit.py URL` 真实按下 Tab 逐站走查，每站各抓一张聚焦态与一张未聚焦态截图。报告：键盘无法到达的控件（2.1.1，含交互元素上的 `tabindex="-1"`）、键盘陷阱（2.1.2；模态对话框内部的循环算 review 不算失败）、缺失或不可感知的焦点环——对比度是对**它所环绕的控件**量的（2.4.7 / 1.4.11）、被作者内容盖住的焦点（2.4.11）、以及只在聚焦或 hover 态才失效的文字对比度（1.4.3）。2.4.13 的面积与同像素读数作为 AAA 证据打印，永不参与退出码。`--measure N` 限制拍多少站，报告会点名"走过但未拍"的站；退出码 1 表示有可测的键盘或焦点失败。
- `text_spacing.py URL` 注入 WCAG 1.4.12 的四项用户覆盖并比对两态：行高 1.5×、段间距 2×、字间距 0.12×、词间距 0.16×。报告被裁切的盒子（含"裁切容器其实是祖先"这一常见情形）、覆盖后需要更多空间的 `max-height` 块、再丢掉一个字宽的省略号标签，以及只在覆盖后才交叠的兄弟文字块。页面不必自带这些值，但必须撑得住。有可测失败时退出码 1。
- `color_sim.py COLOR ...` 模拟红色盲、绿色盲、蓝黄色盲（Machado 2009）；`--check FG BG` 报告配色对的对比度在模拟后是否崩塌。
- `image_diff.py A.png B.png` 用标准库解 PNG，输出变化像素数、比例和包围盒；传入两个目录则跑基线报告；加 `--stats` 只看单张统计。

Windows 上若 `python` 不可用，改用 `py -3`。

## 视觉回路

代码评审看不到：页面在某个窗口尺寸下渲染成空壳、内容只铺满上方三分之二、动效被拍在中间帧。回路是：

1. **渲染。** 启动应用，或把构建好的前端以静态方式挂在回环地址上。多数界面在没有后端时仍能渲染外壳与空态。
2. **截图。** `visual_capture.py --matrix`，然后**看图**。
3. **修改。**
4. **再截一次**到另一个目录，两两跑 `image_diff.py`。变化区域与你声称改动的区域不符，声称就是错的。然后再看一次图：diff 只证明"变了"，不证明"变好了"。

为什么要等稳定帧：在真实应用上，固定等 4 秒时 1440×900 抓到的是半渲染空壳（204 色），延长等待后同一页面完整（837 色）；390 宽度重试 3 次才稳定。文件大小也靠不住——空壳是 12 KB 的 PNG，按大小算是"非空"的。细节见 `references/visual-review.md`。

## 目录结构

```
skills/polishkit/
  SKILL.md                  工作流、底线、品味规则、"选择测试"
  references/
    principles.md           决策顺序与 brief 模板
    directions.md           九个方向及其已验证的起始 token
    color-and-type.md       配色、暗色主题、对比度、字号比例、字体、中日韩文
    layout-and-motion.md    间距、密度、圆角、层次、动效
    components-and-states.md  状态矩阵、文案规则、极限数据测试
    desktop-app.md          WebView 与桌面应用规则
    anti-slop.md            通用痕迹、为什么像默认值、该问什么
    critique.md             评审流程、十个维度、严重度、输出格式
    visual-review.md        渲染、截图、读图、再对比
    sources.md              每条规则的来源，以及刻意未采用的内容
  scripts/                  wcag、design_lookup、slop_scan、token_lint、visual_capture、
                            image_diff、page_audit、keyboard_audit、text_spacing、reflow、
                            cjk_breaks、expression_audit、
                            color_sim、cdp
  data/                     ui-ux-pro-max 的八个 MIT CSV 文件（另有自有的 zh-keywords.csv）
commands/                   可选的斜杠命令
tests/                      仅用标准库的单元测试与夹具
```

## 验证

```
python -B -m unittest discover -s tests -v
```

测试覆盖：对比度算法对公开参考值的校验、草案 APCA 实现对"引用源码推导锚点"的复现、OKLCH 与 sRGB 一致、Machado 模拟矩阵（灰度不变性、红→橄榄锚点）、产品名加权匹配、每条扫描规则与 token 检查对"缺陷夹具"的命中、多行标签与抑制机制、PNG 解码与精确 diff 几何（用生成的夹具）、尺寸不一致与非 PNG 的处理、解压炸弹与超大尺寸的拒绝、截图工具的 URL 校验（选项式字符串、非 http 协议、私网与链路本地地址、显式放行）、WebSocket/CDP 协议层的字节级测试（握手向量、帧布局、分片、上限、回环门禁），以及键盘审计的判定逻辑与像素算术（分桶归属、走查结束原因、手工构造帧上的焦点环测量）。测试不需要网络，也不需要浏览器；PNG 夹具由 `tests/make_fixtures.py` 生成。

## 已知边界

- 扫描器只发现能用规则描述的模式，不判断"好不好看"。每条发现都需要人工确认。例如 `outline: none` 只有在没有替代焦点样式时才是问题。
- 配色只是起点。查询默认读取衍生数据集：原数据里不达标的配对（192 行中 173 行边框低于 3:1、30 行主色填充、1 行文字配对）已做最小幅度调整至达标；`--original-palette` 随时切回原样数值。修正是向黑白方向的灰度调整，不是重新设计——用之前照样要复核 UI 配对。
- 截图经 CDP 可达 hover、焦点、元素裁剪与整页状态；降级后的旧引擎只抓稳态画面，JSON 里始终标明本次用的引擎。展开菜单、过渡中间帧仍需驱动型浏览器工具。
- `keyboard_audit.py` 需要浏览器，且只拍有限站数（`--measure`）；超出的站会被走过但不拍，报告会说明。它不模拟 `prefers-reduced-motion` 或 forced-colors。页面若在 `blur()` 后自动夺回焦点，该站以 uncertain 报告而非下判定——因为第二帧并非未聚焦帧。
- `image_diff.py` 不是回归门禁，且只解码非隔行 8 位 PNG；其他 PNG 变体会被报告为不支持，而不是错误比较。
- 机器上没有浏览器时，视觉这一步跑不了。此时技能要求评审写"未做视觉验证"，而不是描述一个没见过的页面。
- 时长、密度、断点的阈值来自经验的启发式，不是标准。属于 WCAG 的条目在 `references/sources.md` 里单独标注。
- 本技能没有与"只用 `frontend-design`"做过对照基准。可验证的部分（对比度、扫描命中、diff 几何）有测试；"界面是否变得更美"不是这些测试能回答的。

## 兼容性说明

- `SKILL.md` 的 frontmatter 带有 `description`，因为 agent 靠它决定是否加载技能。早期一些设计技能没有写 description，结果永远不会被自动选中。
- 脚本要求 Python 3.9 以上，只用标准库，在所有平台输出 UTF-8。
- 任何脚本都不联网；截图工具只访问你传入的 URL，并先校验协议与地址。
- 除截图输出目录外不写磁盘，因此可以在评审不受信任的仓库时安全运行。

## 基准

`benchmark/` 内置 5 brief × 三条件的试点，用插件自己的审计脚本度量：**裸模型**（无任何设计指导）vs **frontend-design** 单跑 vs **frontend-design + PolishKit**。下面两张表由 `tools/benchmark_tables.py --write` 从 `benchmark/RESULTS.md` 生成，CI 校验漂移。

<!-- benchmark:generated:start tools/benchmark_tables.py --write; do not edit -->
| 指标 | bare | frontend-design | + PolishKit |
|---|---|---|---|
| 渲染页对比度 fail（WCAG 1.4.3） | **48** | 105 | **0** |
| 对比度 uncertain（渐变/图像/遮挡，不可测） | 12 | 103 | 182 |
| 靶标尺寸 fail（2.5.8） | 13 | 21 | 11 |
| 无可访问名称元素（4.1.2） | 0 | 0 | 0 |
| **键盘可达性 / 焦点 fail（2.1.1 / 2.4.7 / 1.4.11 / 2.4.11）** | **5** | **12** | **0** |
| **文本间距 fail（1.4.12）** | 0 | **8** | **0** |
| **回流 fail（1.4.10，320 CSS px）** | **21** | **28** | **0** |
| **CJK 断行 fail（clreq §6.1.1）** | 0 | **1** | **0** |
| slop_scan important 发现 | 30 | 45 | **1** |

| 指标 | 2.0 原始 treatment | 2.2.10 修复后 |
|---|---|---|
| 对比度 fail | 0 | 0 |
| 键盘 fail | **2** | 0 |
| 文本间距 fail | **11** | 0 |
| 回流 fail | **34** | 0 |
| CJK 断行 fail | **1** | 0 |
<!-- benchmark:generated:end --><!-- benchmark:generated:end -->

读这些零时要带上报告的前提：n=5、单次运行、单一底模。测量、修复与复测用的是本插件同一套工具——单人维护没有独立评审方——所以这些数字是"地板守住了"的证据，不是独立审计。treatment 列是修复后的一代；2.0 原始产物在四个当时测不了的维度上有 48 处真实缺陷（第二张表）。

裸模型条件自己的输出恰好收敛到立场警告的那条 AI-slop 配方（暖奶油 + 赤陶 + 衬线，无人引导）。完整表格、协议与如实局限：`benchmark/RESULTS.md`。维护者并排看的裁决（终审与建工具是同一人）：地板守住，审美以更张狂的风格追平。

## 许可

插件自身的代码与文档采用 MIT，见 `LICENSE`。数据文件由 Next Level Builder 以 MIT 授权，见 `THIRD_PARTY_NOTICES.md`。
