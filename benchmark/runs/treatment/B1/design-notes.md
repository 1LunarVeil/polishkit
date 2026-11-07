# B1 — 本地大模型启动器设置页（treatment-v3：expression 层）

## Brief

- 主题：本地大模型启动器「烛龙」的设置页——模型列表、推理参数调节、显存监控
- 受众：在自己电脑上跑 LLM 的技术用户；桌面 WebView；长会话、常在夜间使用
- 任务：一屏内完成「看显存余量 → 挑模型 → 调参数 → 加载/卸载」（v3 把显存带提到页首，正是为了这个顺序）
- 密度：compact——基准字号 14px（dense desktop 下限），行高约 32px，mono 下限 12px
- 语言：zh-CN 界面；模型名/路径/数值为拉丁技术串（mono + tabular-nums）
- Refusals：
  1. 不像营销落地页（无 hero 光晕文案区、无三卡片特性区、无渐变文字）
  2. 不用默认蓝 SaaS 配色 / AI 紫（design_lookup 的浅蓝 palette 被明确拒绝）
  3. 不做等距 bento 卡片网格，也不给仪表盘加装饰性铺陈（expression.md 刻意不采用：数据密集屏的表现预算全部给数据本身）

## Precedents（design_lookup，两次实跑）

- `design_lookup.py "local llm launcher settings vram monitoring dark" --ux --motion --charts` → 误匹配 Local Events & Discovery（关键词漂移），弃用。
- 重跑 `design_lookup.py "ai model runner dashboard gpu monitoring" --ux --motion --charts` → 匹配 Analytics Dashboard。取：Data-Dense Dashboard 风格（clarity > aesthetics、行 hover 高亮、数据加载态）；其 light 蓝 palette（#1E40AF/#F8FAFC）按 refusal 2 整体拒绝；Dark Mode (OLED) 风格佐证深色优先 + 可见 focus。

## 方向

**Direction 6「Night-first ops」（references/directions.md），palette 向主题移动。** 理由：brief 深色优先，主体是长会话 + 监控。v1（treatment）原样采用了方向表的 #7AA2FF 冷蓝 accent——正是「方向表 hex 原封不动 = 没人看主题」的 tell。v3 的移动：烛龙 = 火烛，把中性色从冷蓝灰挪向烛光暖灰（#E6E9EF→#EAE6DE、新增巨数烛白 #F5EBDC），accent 从冷蓝 #7AA2FF 挪向**余烬橙 #E8946A**（表面 7.37:1 AAA，填充上配 #1A0F08 深褐墨 7.95:1）。表面阶梯（base/surface/raised）保留自方向表作深度系统。

## Token 块

```css
--base:#0F1115; --surface:#161A21; --raised:#1E232C; --hover:#1C212B; --sel:#202634; --band:#1D222B;
--line:#262C38;      /* 仅装饰分隔（顶栏底一条） */
--ctl:#5E6A80;       /* 控件唯一边界，3.20:1 vs surface */
--text:#EAE6DE;      /* 烛白 15.18/14.02/12.67 on 阶梯 */
--bright:#F5EBDC;    /* 巨数 13.53 on band */
--muted:#A39D92;     /* 6.48/7.01/5.85/5.99/5.62 — AA 全过 */
--accent:#E8946A;    /* 余烬：文字 6.72–7.45，填充 */
--on-accent:#1A0F08; /* 7.95 on ember */
--ok:#5EE0A0; --warn:#F5C25B; --err:#FF7A7A; --sky:#6FB5D6; --sys:#566072; --track:#0B0D11;
--mono:"Cascadia Mono","Cascadia Code",Consolas,ui-monospace;
--sans:"Segoe UI","Microsoft YaHei","PingFang SC",system-ui;
/* 字阶 12 / 14 / 16 / 20 / 88（巨数），巨数 weight 300 ↔ 标题/按钮 700 */
```

## 表现层清单（逐项：做了什么）

1. **字阶戏剧 — display ≥3× body、双端字重**：显示时刻就是数据本身——GPU 0 已用显存 **12.9** 以 88px Segoe UI Light（300）、tabular、tracking −0.02em、line-height 1.0 直立在全幅带上，是 14px 正文的 6.3×；单位 / 16.0 GB 20px mono。字重两端：300（巨数、GPU1 次级数 30px）↔ 700（品牌、面板题、按钮、stamp）。正文 1.55 行距 × 紧排巨数的反差即节奏。
2. **恰好一处不对称、一处全幅/叠压**：全幅 = 显存带（edge-to-edge，对面是内收面板）；不对称 = 带内左缘竖排标签「显存监控 · 每 5 秒刷新」（mono、0.42em 字距）+ 巨数左锚、留白聚在巨数右侧。叠压 = 「81% 已用」印章斜盖在巨数右下角。
3. **唯一焦点、两杠杆可指**：12.9 —— scale（88px vs 14/12.5px 全页其余）+ isolation（带上半部整片安静）+ contrast（全页最亮最暖的 #F5EBDC）。其余读数明显更小更暗，一秒落点。
4. **hero 级表面 nonzero 质感**：带体 = 竖向微渐变（#1D222B→#151920）+ 左上余烬径向 tint（7.5%）+ feTurbulence 颗粒层（5% 矩形，综合 ≈2.5%）——无死平。
5. **软化骨架**：v1 的「每个面板/每行都有 hairline」全部撤掉——面板无框（表面阶梯 + 留白分层），模型行仅 hover 底色与选中 inset 条，hairline 只剩分配明细表的功能性行线（1 条规则内）。**唯一有机分隔**：带体底缘的余烬波浪线（SVG path，把显存带「流」进下方工作区）。**唯一旋转强调**：「81% 已用」stamp（−1.8°），不做第二处。
6. **签名元素**：显存带本身——88px 实时巨数 + 分配 ribbon（余烬=权重 / 天蓝=KV / 灰=系统）+ GPU1 次级读数 + 40 点利用率 sparkline（2s 内容更新，reduced-motion 下静止）+ 分配明细表。拆掉它页面就退回 v1 的通用三栏仪表盘。
7. **数据即表现（刻意不采用条款的正面执行）**：除巨数与字重纪律外无装饰——无旋转正文、无渐变文字、无第二处构图破格。

## Render → look → fix（实际所见与所改）

- 第 1 次渲染（band 在页尾）：首屏 800px 只见两面板，**最弱决策 = 签名带在折叠线以下**，违背 brief「一屏内看显存余量」。修复：带提到页首（topbar → band → 两面板 → footer），波浪分隔移到带底缘。
- 第 2 次渲染：g-cap 是 flex 容器，文本节点被拆成三个 flex 子项，「GPU 0 NVIDIA RTX 4080（PCIe 4.0 x16）」断成三行碎块；「刷新」按钮悬在标题行外。修复：说明文字包进单一 span；刷新按钮移入「GPU 0 占用分配」行右端（.r-head）。
- 同轮 floor 修正：禁用按钮原为 opacity .5（标签对比跌破可读），改为去 opacity、以边框/光标表达禁用（muted on surface 6.48）。deepseek 行 meta 收短（「校验分片 5/8」→「分片 5/8」）保持两行内。
- 第 3 次渲染（hero2/fullpage）：巨数、stamp、ribbon、sparkline、波浪线全部成立；首屏 = 带 + 明细表 + 两面板头部，正好覆盖 brief 的一屏任务。截图判读以此为最终。

## wcag.py（全部出货对，实跑）

- #EAE6DE on #0F1115/#161A21/#1E232C：15.18 / 14.02 / 12.67（AAA）
- #F5EBDC on #1D222B：13.53；on #1E232C 13.36（巨数/烛白）
- #A39D92 on #161A21/#0F1115/#1E232C/#1C212B/#202634：6.48 / 7.01 / 5.85 / 5.99 / 5.62（AA 全过）
- accent #E8946A on #161A21 6.72、on #0F1115 7.27、on #151920 7.45、on chip 底 #2A2628 6.31（AA）
- #1A0F08 on #E8946A 7.95（主按钮/预设/stamp 填充）
- 状态色 on #161A21：#5EE0A0 10.50 / #F5C25B 10.59 / #FF7A7A 6.91；on 选中底 #202634：9.18 / 5.99；on hover 底 #1C212B：9.71 / 6.39（AA）
- warn 横幅 #EAE6DE on tint 叠底 ≈#333230：10.29
- UI 对：#5E6A80 vs #161A21 3.20（控件唯一边界）；数据段 #E8946A 7.49 / #6FB5D6 8.57 / #566072 3.07 on #0B0D11（graphic ≥3）
- #7E8798 on #161A21 4.82（禁用标签，保留余量）

## slop_scan.py（实跑）

- 首轮：0 blocking, 0 important, **7 review**（.prog width 过渡属 layout 属性；stamp 通用黑影；5 处中点连接元数据）。
- 修复：进度条过渡改 opacity；stamp 阴影改暖调 rgba(26,12,5,.5)；中点元数据改括号/顿号分组（g-cap、g-free、g1-name、g1-meta、JS meta1）。
- 复扫：**0 blocking, 0 important, 0 review, 0 polish（exit 0）**。

## visual_capture.py（实跑，CDP）

- `http://127.0.0.1:8611/B1/index.html?freeze`：hero 1280×800 `settled: true`、`blank: false`、`console_errors: []`；full-page 1265×1410（内容更新定时器导致 fullpage 帧判定 unsettled，画面完整非空白，已人工判读）。`?freeze` 仅冻结 2s 实时 tick（sparkline/tok-s）供稳定截帧；默认打开页面仍为活数据。

## 状态覆盖（默认首帧 = 工作数据）

loading（deepseek 行内进度条 + progressbar role；刷新按钮「刷新中…」禁用）、empty（搜索无结果 + 清空提示）、error（mistral 校验失败行：原因 + 重新下载动作）、disabled（phi-3.5-mini 加载禁用附原因；mlock 开关禁用；运行中按钮禁用）、partial（扫描中行；sparkline 前 40 点为采样窗口）、aria（progressbar/switch/status/note/sr-only caption）、hover 与 focus-visible 分离（hover 底色 vs focus 2px 余烬轮廓）、prefers-reduced-motion（脉动/过渡全关，sparkline 停止滚动）。

## 未验证（诚实边界）

- 键盘全循环与真实后端行为（单文件模拟数据）；`page_audit` 未跑（协议在 runner 外）；1600% 缩放与窄断点只做了 CSS 声明未逐一截图。
