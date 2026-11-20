# PolishKit 基准：三条件对照

> 这份报告回答一个问题：**装上 PolishKit 之后，模型产出的页面在可测量维度上到底有什么不同。**
> 它以 2.0 的三条件试点为骨架，在 2.2.10 的工具集上**重新测量全部产物**，并补上 2.0 时
> 尚不存在的四个检查维度。环境指纹见 `ENVIRONMENT.json`。

## 方法

- **语料**：5 个 brief（中英混合，见 `briefs.md`），覆盖仪表盘、作品集、电商、预订、开发者落地页。
- **三条件**：
  - **bare** — 裸模型，明确禁止加载任何设计技能
  - **baseline** — 模型 + `frontend-design` 官方技能，禁止 PolishKit
  - **treatment** — 模型 + `frontend-design` + PolishKit 完整工作流
- **交付规格**：单文件自包含 `index.html`，内联 CSS/JS，仅系统字体，无网络请求。
- **公平性**：同一 brief、同一代理类型、每个 brief 独立子代理（新鲜上下文）。
- **测量**：全部产物经本地 `http.server` 提供，用 `skills/polishkit/scripts/` 下的审计脚本测量。
  每个数字都是脚本输出，不是估计。

## 环境

测量环境记录在 `ENVIRONMENT.json`：Chrome 157.0.8103.79、Python 3.11.9、Windows 26200/AMD64，
外加十四个工具的 SHA-256 摘要。**任何一项变化都可能移动数字**，所以本报告的数字只在同一
指纹下可比。`python tools/benchmark_env.py --diff` 可核对。

## 七项指标（全部实测）

| 指标 | bare | baseline | treatment |
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

加粗的四行是 2.0 报告没有的：键盘、文本间距、回流、CJK 断行。它们分别由 2.1、2.2、2.2.4、
2.2.6 引入。**2.0 说"0 fail"，那是在三个维度上说的；加上这四个维度，treatment 的原始产物
仍有 48 处真实缺陷**（见下节）。

## treatment 的两代产物

基准产物在 2.1–2.2.9 之间被修复过四轮。为避免把修复后的页面当作模型当年的产出，两代都测量：

| 指标 | 2.0 原始 treatment | 2.2.10 修复后 |
|---|---|---|
| 对比度 fail | 0 | 0 |
| 键盘 fail | **2** | 0 |
| 文本间距 fail | **11** | 0 |
| 回流 fail | **34** | 0 |
| CJK 断行 fail | **1** | 0 |

原始产物的 48 处缺陷都是真实的、当时工具看不见的：B1 的模型名在字距放大后丢一整行、
B3 图表柱子的焦点环与柱体同色（1.01:1）、B3 在 320px 下文档宽 639px、B5 的导航被裁掉
且无滚动条可揭示。**它们能存在，正是因为 2.0 的工具只检查了对比度和 slop。**

修复只处理已确证的可访问性缺陷，不改设计意图（悬垂卡片、显式巨数、brutalist 偏移全部保留），
每处 CSS 都注明依据与实测数字。`benchmark/runs/treatment/` 是修复后的版本。

## 关键发现

1. **裸模型自然收敛到 AI-slop 配方。** bare B4 的自述是 "cream and terracotta palette, serif
   headings"——未经引导的模型落在了反 slop 清单的第一条上。
2. **fail 数要结合野心解读。** bare 的对比度 fail（48）少于 baseline（105），不是裸模型更守规矩，
   而是页面更小更保守（总量 99KB vs 138KB），可失败的表面积小。baseline 的 105 来自更大胆的用色。
3. **地板与表达是两件事。** baseline 表达强但地板破（105 对比度、45 slop important、12 键盘、
   28 回流）；bare 守规矩但平庸；treatment 两者兼得。
4. **uncertain 不是 pass。** treatment 的 182 个 uncertain 集中在 B2 的摄影页和 B5 的纹理带上
   ——文字叠在手绘画作或纹理上，WCAG 公式测不了。这部分只能靠截图人工确认，**报告不把它当作通过**。
5. **完整地板只在 treatment 上成立。** 七个指标里，只有 treatment 在六个可测维度上同时为零。

## 人工裁决（维护者，2.0）

- 对照 bare 组：**审美插件确实大幅提高了前端下限**（bare 仅 B5 相对较好）。
- 风格定性：baseline 像"精致乖巧的漂亮孩子"，PolishKit 条件像"性格张狂、敢于书写的孩子"——
  两种都成立的艺术人格，总体追平。
- 分页：B1/B5 很好；B4 还好；B3 曾有两处缺陷（旋转标签遮挡关键数字、中段画幅空），已修复。
- 表达层字阶比实测 4.75–6.74×（`expression_audit.py`），维护者判定**不算过冲**。

## 局限（如实）

- **n=5、单次运行、单一底模**。没有方差估计，因此不能声称差异的统计显著性。
- **技能加载靠 description 触发**，禁用在 baseline/bare 靠指令约束，无法技术强制。
- **treatment 工作流含自查环节**——本基准测的是"装上插件后 agent 的行为"，不是纯天赋差。
- **对比度 101 → 105 的漂移**：baseline 页面从未改动，测两次结果一致，说明是环境差异
  （2.0 记录时的浏览器构建不同）。这正是 `ENVIRONMENT.json` 要解决的问题，但 2.0 当时的
  环境已无法追溯。
- **uncertain 占 treatment 的多数**：纹理与图像上的文字测不了，本报告不声称这些文字通过对比度。

## 复现

```bash
python tools/benchmark_env.py --diff        # 确认环境与记录一致
cd benchmark/runs/bare && python -m http.server 8001 &
# 对每个 8001/B1..B5 运行 page_audit / keyboard_audit / text_spacing / reflow / cjk_breaks
```

三个条件分别用 `runs/{bare,baseline,treatment}/`。

## 产物索引

- 页面：`runs/{bare,baseline,treatment}/B1..B5/index.html`
- 语料与协议：`briefs.md`
- 环境指纹：`ENVIRONMENT.json`
- 度量截图：`measure/`
