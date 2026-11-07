# M4 基准测试语料与协议（试点：5 brief × 双条件）

> 目的：对照「frontend-design 单跑」与「frontend-design + PolishKit」的生成质量差异，产出客观指标与并排产物供人工裁决。
> 公平性控制：同一 brief、同一代理类型（general-purpose）、每 brief 派发独立子代理（新鲜上下文）、相同交付规格（单文件自包含 index.html，内联 CSS/JS，仅系统字体，无网络依赖）。
> 诚实边界（写入协议）：技能加载靠 description 自动触发，基线组的"禁用 PolishKit"靠生成指令约束，无法从技术上强制——这是业界标准做法，局限如实记录。

## 语料

| id | brief |
|---|---|
| B1 | 本地大模型启动器的设置页：模型列表、参数调节、显存监控。信息密度高，深色优先。（中文 brief） |
| B2 | Portfolio site for a landscape photographer — image-forward, quiet, lets the work breathe. |
| B3 | Daily-use analytics dashboard for a small e-commerce shop: orders, conversion, top products. |
| B4 | Booking flow for a boutique hotel — weekend-getaway audience, warm and trustworthy. |
| B5 | Landing page for a CLI-first JSON formatting tool aimed at developers. |

## 双条件

- **baseline（A）**：仅使用 `frontend-design` 技能；明确禁止加载或遵循 PolishKit / frontend-aesthetics 或任何其他设计技能。
- **treatment（B）**：`frontend-design` + PolishKit——明确指示生成代理遵循 PolishKit 的工作流（brief → 先例 → 方向 → token → 构建 → 验证），产出 token 块与验证段落。

## 指标（客观、可脚本化）

1. `page_audit`：渲染页对比度审计——pass / fail / uncertain 计数（经本地 http.server 提供）。
2. `slop_scan`：blocking / important / review / polish 分级发现计数。
3. 状态覆盖：index.html 中 loading / empty / error / skeleton / disabled / aria- 标记的存在性（grep 计数）。
4. `visual_capture`：settled、distinct colors（渲染健全性）。
5. 文件大小。

## 人工 rubric（用户裁决部分）

- 每对页面并排截图（`visual_capture --matrix`），由维护者裁决方向契合度、密度处理、状态完整度、第一印象。
- 客观指标 + 人工裁决 = 基准报告；报告只陈述差异，不声称因果。
