# PolishKit 基准：三条件对照（5 brief 试点）

> 目的：用可度量的证据回答"这个插件到底起什么作用"。同 5 个 brief（中英混合、无设计暗示、语料见 `briefs.md`）、同交付规格（单文件自包含 index.html、内联 CSS/JS、仅系统字体、无网络请求）、每 brief 独立生成。三条件：
>
> - **bare**：裸模型——不加载任何设计技能（明确禁止 frontend-design 与 PolishKit）
> - **baseline**：模型 + `frontend-design` 官方技能（明确禁止 PolishKit）
> - **treatment**：模型 + `frontend-design` + PolishKit（完整工作流：brief → 先例 → 方向 → token → 构建 → 验证）
>
> 诚实边界：技能加载靠 description 触发，禁用靠生成指令约束（业界标准做法，无法技术强制）；试点规模 5、单一底模、每条件单次运行。

## 客观度量（page_audit / slop_scan / visual_capture 独立复跑）

| 指标 | bare（裸模型） | baseline（+frontend-design） | treatment（+PolishKit） |
|---|---|---|---|
| 渲染页对比度 fail | **48** | 101 | **0** |
| 靶标尺寸 fail | 27 | 34 | 17 |
| 无可访问名称元素 | **8** | 0 | 0 |
| slop_scan 发现 | 54（27 important） | 88（45 important） | **2（review）** |
| 零状态标记页 | 1 | 2 | **0** |
| 永不稳定渲染页 | 1 | 3 | **0** |

## 关键发现

1. **裸模型自然收敛到 AI-slop 配方**：bare B4 的生成自述是 "cream and terracotta palette, serif headings"——未经引导的模型恰好落在 AI-slop 校准清单的第一条（暖奶油+赤陶+衬线）上。这证明了反 slop 立场与扫描器不是无病呻吟。
2. **fail 数要结合野心解读**：bare 的 fail（48）比 baseline（101）少——不是裸模型更守规矩，而是更保守：页面更小（总量 99KB vs 138KB）、用色更安全，可失败的表面积就小。baseline 的 101 fail 来自更大胆的用色——野心制造违反，违反暴露缺地板。
3. **地板与表达是两件事**：baseline（frontend-design）页面的表达力强但地板破损（101 fail、45 项 important 发现、3 页渲染永不稳定）；裸模型守规矩但平庸；PolishKit 条件两者兼得——0 fail、全状态、全稳定，且表达力经表现层清单（`skills/polishkit/references/expression.md`：字阶戏剧、构图张力、焦点工程、质感）达到与 baseline 不同的成熟风格。

## 人工裁决（维护者）

- 对照 bare 组后确认：**审美插件确确实实大幅提高了前端的下限表现**（bare 仅 B5 相对较好）。
- baseline 与 treatment 的风格定性：**baseline 像"精致乖巧的漂亮孩子"，PolishKit 条件像"性格张狂、敢于书写的孩子"**——两种都成立的艺术人格，总体追平。
- 分页：B1/B5 设计很好；B4 总体还好；B3 曾有两处缺陷（旋转标签遮挡关键数字、中段画幅空），已按裁决外科修复并复验（153 对全过、0 findings）。

## 工作流可审计痕迹

treatment 每页附带 `design-notes.md`：brief 与三拒绝、方向及调色板向题材移动的记录（海雾纸/面粉纸/蜂蜜亚麻——方向表是地板不是设计）、token 块、wcag/slop_scan/visual_capture 真实输出、打磨循环记录。

## 局限（如实）

- 试点规模 5 brief、单一底模、每条件单次运行。
- treatment 工作流包含自查环节（wcag/slop_scan 修复）——这是插件设计的工作方式，本基准测的是"装上插件后 agent 的行为"，不是"纯天赋差"。
- 渲染页审计对叠字于手绘画作的文字如实转 `uncertain`（WCAG 公式不可测），该部分由截图人工确认。

## 产物索引

- 页面：`runs/{bare,baseline,treatment}/B1..B5/index.html`
- 度量截图：`measure/`
- 语料与协议：`briefs.md`
