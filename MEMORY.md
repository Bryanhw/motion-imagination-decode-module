# MEMORY.md

> **当前状态、已定决策、下一步**。每个会话结束时更新本文件；
> 长期规则见 `AGENTS.md`，项目细节见 `agent_docs/`。
> **最后更新：2026-10-16**

## 一句话现状

项目处于**立项完成、工程起步**阶段。里程碑 ①（10/13 文档）已交付，里程碑 ② 🔄 进行中；
仓库内已有**本团队的可运行解码链路**（`bci-decoder/`，16 项测试通过、已产出模型与输出文件），
**归属已拍板（2026-10-15）：属于团队成果，计入项目进度**。
**仍未完成**：LSL、脑控弹球（`bci-decoder/game/` 尚未创建）、校准流程、Docker（**WebSocket 输出已于 2026-10-16 端到端跑通**）。

## 里程碑状态

| # | 日期 | 目标 | 状态 |
|---|---|---|---|
| ① | 10/13 · W7 | 立项与 MVP 规格（文档） | ✅ 文档已交付（`MVP规格说明书` **v1.1**、`项目章程`、`需求确认记录`） |
| ② | 10/27 · W9 | **可运行 MVP**（F1–F5 + 延迟实测） | 🔄 进行中（解码链路**已跑通**、`pytest` **16/16**；**WebSocket 输出已端到端跑通**，2026-10-16；弹球游戏 / 校准流程未完成） |
| ③ | 11/10 · W11 | 真实基线（`moabb` + BCI IV 2a，Kappa > 0.3）+ 用户反馈 | ⏳ 未开始 |
| ④ | 12/01 · W14 | Beta（校准流程、黎曼、LSL、稳定性） | ⏳ 未开始 |
| ⑤ | 12/08 · W15 | Demo Day | ⏳ 未开始 |
| ⑥ | 12/15 · W16 | 反思与归档（Docker、交付说明） | ⏳ 未开始 |

## 已定决策（不要重复讨论）

| 主题 | 决策 |
|---|---|
| 交付边界 | 只做**在线解码模块**（消息流），游戏画面由游戏端负责 |
| 类别 | **2 类（左手/右手）+ `idle`**，不做 4 类 |
| 滑窗 / 步长 | **2.0 s / 0.5 s**（延迟瓶颈在此，不做微调） |
| 特征 / 分类器 | 频带功率（16 维）+ **LDA**；黎曼与深度模型留到后期 |
| 伪迹 | **只标记不丢弃**，超阈值降级为 `idle` |
| 安全 | 未训练/不可信 → **恒输出 `idle`** |
| 接口契约 | 自 2026-10-13 冻结，变更走 `MVP规格说明书` 第 9 节 |
| 数据纪律 | `mock`/`synth` **只用于自检**，绝不作为算法成绩 |
| 对外口径 | **MVP 阶段不报告任何准确率数字** |
| 传输机制 | MVP 用 **WebSocket**（`ws://127.0.0.1:8765`）；LSL 留到 ④（企业集成）；降级首选 **jsonl 轮询**（零新依赖，不改玩法代码） |
| 文档体系 | 主 TechDesign 只管**解码模块**（headless、无 UI）；**游戏端独立成文**：`docs/PRD-Game-MVP.md`（game 端 PRD，2026-10-15）+ `docs/TechDesign-Game-MVP.md`（game 端设计） |
| 降级纪律 | 三级降级 A/B/C 必须**如实通报**——"准实时回放"/"键盘输入"不得说成脑控实时 |
| 成果归属 | `bci-decoder/` ＝ **本团队成果**（团队借助 AI 编码助手实现），**计入项目进度**（2026-10-15 拍板） |
| `game/` 路径 | **`bci-decoder/game/`**（2026-10-15 定案；团队可再议，改动须同步 `MVP规格说明书` 附录A 与两份 TechDesign） |
| 证据归档 | 里程碑证据统一放 `docs/evidence/W{n}_{日期}/`；合成数据自检数字**只作工程证据**，不作准确率 |

## 环境事实（已核实）

- `bci-decoder/.venv`：**Python 3.14.7**；已装 numpy 2.5.3 / scipy 1.18.1 / scikit-learn 1.9.1 / PyYAML 6.0.3 / joblib 1.6.0 / pytest 9.1.1 / **websockets 17.2** / **pygame-ce 2.5.8**
- **未安装**：`mne`、`moabb`、`pyriemann`、`pylsl`（里程碑 ③/④ 前装好；`websockets` 已于 2026-10-16 装通并验证）
- `python -m pytest` → **16 项全部通过**（2026-10-16 复核，2.35 s；口径 = `bci-decoder/tests`；从仓库根跑会额外收集 `docs/learning/` 的 12 个学习用例，共 28。2026-10-15 的 14 项快照见 `docs/evidence/W7_1013/pytest_20261015.txt`）
- `bci-decoder/artifacts/` 内已有 `demo_lda.joblib` 与 `decoder_output.jsonl`
- 全局 `python` **没有** pytest —— 必须用 `.venv\Scripts\python.exe`
- 仓库**已是 Git 仓库**（2026-10-15）：远端 `origin` = **https://github.com/Bryanhw/motion-imagination-decode-module**（**公开仓库**），`main` 与 `origin/main` 同步；入库提交 **`7ce8d08`**（89 文件 / 12,317 行），父提交为远端原有 `4ea612c`（**快进推送，未覆盖、未强推**）；提交身份 **`Bryanhw <yhw20070910@outlook.com>`（仅仓库级 `git config`，未改全局）**；`.gitignore` 已实测生效（`.venv/`、`artifacts/`、`.pytest_cache/`、`.deepworks/`、`uploads/`、`.tools/*.pdf` 均被忽略）
- `docs/evidence/W7_1013/` **已建立**（2026-10-15，含 `README.md` 与 pytest 证据）
- 仓库根已**去噪**（2026-10-15）：非交付物集中在 **`.tools/`**（转换脚本 + PDF 产物）与 **`docs/_assets/`**（需求来源图）；根目录新增 **`.gitignore`**

## 下一步（建议顺序）

1. ~~拍板 `bci-decoder/` 的归属口径~~ ✅ **已完成**（2026-10-15：团队成果、计入进度）；~~改完旧文档表述~~ ✅ **已完成**（全库复核，残留命中均为合法的历史引述/决策记录）。
2. ~~校准文档与仓库事实的 6 处不一致~~ ✅ **已完成**（§5.2 六条已逐条处置，处置结果记于该节表格下方）。
3. ~~建 `docs/evidence/W7_1013/`~~ ✅ **已完成**；~~`git init` + 首次提交~~ ✅ **已完成**（2026-10-15：`7ce8d08` 已推送至 `origin/main`，公开仓库地址见「环境事实」）。
4. 里程碑 ② 主攻：~~**`websockets` 跑通**~~ ✅ **已完成（2026-10-16）** + **脑控弹球（先键盘版，`bci-decoder/game/` 尚未创建）** + **校准流程骨架**。

## 开放问题

- ✅ **已拍板（2026-10-15）：`bci-decoder/` ＝ 本团队成果**（团队在 AI 编码助手辅助下实现），**计入项目进度**。全库旧表述（"他人参考骨架 / 不计入进度"）**已逐处更正完毕**（`docs/Start项目落地评估.md` §5.1 方案 A）；残留命中均为合法的历史引述/决策记录。**注意**：归属更正不等于"未完成的部分已完成"（WebSocket / LSL / 弹球 / 校准 / Docker 仍未做）。
- 企业设备型号 / 通道顺序 / LSL 流名称（需书面确认）。
- ✅ **已定（2026-10-15）**：Demo 游戏端 = **Python + Pygame**（`docs/TechDesign-Game-MVP.md`）；Unity 属"企业未来客户端"分支，不在 MVP。
- ✅ **已关闭（2026-10-16）**：`websockets 17.2` 装通并端到端跑通（F5.1：解码器 `--outputs websocket` ← 客户端收消息、字段契约逐条一致）。
- 里程碑 ③ 的评测协议（用哪个数据集、什么指标口径）。
- ✅ **已拍板（2026-10-15）**：**User level 统一为 A**（A/B/C 指"交付物面向谁"，不是团队水平）；"团队实现水平 = C" 改记入 TechDesign 的 Constraints。**已核实**（2026-10-15）：`docs/项目章程.md`、`docs/需求确认记录.md` 中**并无** User level 字段，复核报告原"仍记 C"一句系未经核实的推断，已在报告中更正。
- ✅ **已授权且已执行（2026-10-15）**：`docs/TechDesign-BCI-Decoder-MVP.md` 由 v1.0 修至 **v1.1**，复核报告 §6 的 14 项全部落地（含 Part 3 结构合规）。**校验**：417 行、文末 JSON 解析通过、顺序 `正文 → 页脚 → Handoff Context → JSON`、Handoff 14 字段。
- ✅ **红线残留已修复（2026-10-15）**：`bci-decoder/scripts/bootstrap_demo.py` 已在交叉验证输出行后与 JSON 输出前各加一行合成数据警示（**禁止对外报告准确率**）。**验证**：`python -m pytest` → **14 passed**、`py_compile` 通过。文档侧另有 TechDesign v1.1 §7/§10/§12 三处红线提示。
- 【待定】PRD must-have「脑控弹球」无技术落地设计 → ✅ 已定：**单独成文** `docs/TechDesign-Game-MVP.md`（2026-10-15）。`game/` 最终路径已定案：**`bci-decoder/game/`**（依据 `MVP规格说明书` 附录 A 先 `cd bci-decoder` 再 `python game\pong.py`；**团队可再议**，改动须同步两处文档）。
- ~~【待验证】`websockets` 能否安装跑通~~ ✅ **已验证（2026-10-16）**：装通并端到端跑通；`jsonl` 轮询降级方案仍保留备用。**新增定案**：游戏端用 **`pygame-ce`**（上游 `pygame` 无 Python 3.14 wheel）。

## 最近变更

| 日期 | 变更 |
|---|---|
| 2026-10-15 | 按 vibe-coding-prompt-template 的 "Start a project" 流程补齐 agent 层：新增 `AGENTS.md`、`MEMORY.md`、`REVIEW-CHECKLIST.md`、`agent_docs/*`，以及 `docs/research-BCI-Decoder.md`、`docs/PRD-BCI-Decoder-MVP.md`、`docs/TechDesign-BCI-Decoder-MVP.md`、`docs/Start项目落地评估.md`。**未改动任何现有文档、未写业务代码。** |
| 2026-10-15 | 按 vibe-coding-prompt-template **Part 1（Deep Research Prompt Builder）** 流程生成研究请求：`outputs/research-request-BCI-Decoder.md`（A 零基础口径、聚焦"在线解码链路与延迟"、全免费优先、AI 仅用于辅助开发）。**该文件是研究请求，不是研究结果**；未改动现有文档、未写业务代码。 |
| 2026-10-15 | 执行上述研究请求，产出研究发现：`outputs/research-BCI-Decoder.md`（联网检索，全部来源访问日期 2026-10-15）。研究状态：**Partial research**。三条可核实结论：①**在线因果滤波有官方依据**（SciPy `filtfilt` 零相位；`sosfilt` 单次前向 + `zi` 可跨块保状态；MNE-LSL 在线滤波官方即"IIR causal filter"）；②**延迟结构**官方可核实机制为分块推送 `interval = chunk_size / sfreq` + `acquisition_delay`（StreamLSL 默认 0.001 s）+ 回调阻塞会推迟采集；③**"换模型/上 GPU 对端到端延迟帮助有限"未找到公开依据**，对外措辞需收敛为"当前 2.0 s 窗口下计算耗时为毫秒级"。**未改动任何现有文档、未写业务代码。** |
| 2026-10-15 | **合并两份 findings**（初版 `docs/research-BCI-Decoder.md` + 联网检索版 `outputs/research-BCI-Decoder.md`）为**一份**：真身 `docs/research-BCI-Decoder.md`（43,987 字节 / 610 行），交付副本 `outputs/research-BCI-Decoder.md`（内容一致，仅身份说明块不同）。**统一保持 A（零基础）口径**。合并新增/救回：`T_response ≈ T_accumulate + T_compute` 分解式与"先定游戏节奏→倒推窗口"顺序原则；**脑机盲演示失败风险**（约 15%–30%，`[未核实·引自团队既有文档]`）；深度学习工具箱 5 项（braindecode/arl-eegmodels/torcheeg/ATCNet/FBCNet，**降级为 `[既有核实·本轮未复核]`**）；传统平台（BCI2000/OpenViBE/EEGLAB）与商业同类（Emotiv/g.tec/BrainCo 等）；`bcmi-labs/BrainFlowsIntoVRChat` **404 不要引用**警示；数据集补充 OpenBMI/PhysioNet；风险表补充伦理审查与抖动治理。**未写业务代码。** |
| 2026-10-15 | 按用户要求**只保留 `docs/`**：删除交付副本 `outputs/research-BCI-Decoder.md`（删除前已校验 `docs/` 真身存在且为 43,987 字节，副本内容与真身一致，**无信息丢失**）；同步修正 `docs/research-BCI-Decoder.md` 头部与结尾的失效引用。**findings 唯一副本现为 `docs/research-BCI-Decoder.md`。** `outputs/` 仅余 `research-request-BCI-Decoder.md`（研究请求，docs/ 无对应版本，**保留**）。**未写业务代码。** |
| 2026-10-15 | 按用户要求（A 方案）将研究请求 **从 `outputs/` 移入 `docs/`**：`docs/research-request-BCI-Decoder.md`（11,355 字节；移动前后 SHA256 一致，**无损坏**）。**`outputs/` 现已清空**；findings 与研究请求同处 `docs/`，两者分开保存。同步修正两文件内的过时路径引用：请求文件头部旧警告（"不要把两份内容随意合并"）改为"请求已执行完毕、findings 已合并为唯一副本"；请求文件与 findings 的 `Source files:` 路径均补 `docs/` 前缀；请求文件附录第 1、4 步补归档路径。**未写业务代码。** |
| 2026-10-15 | 按 **vibe-coding-prompt-template Part 2（PRD-MVP）** 流程，以 **A（零基础）口径规范化重写** `docs/PRD-BCI-Decoder-MVP.md`（v1.0 → **v1.1**，34,373 字节 / 362 行）。补齐 Part 2 产出契约要求的章节：Product Overview、用户画像（企业集成工程师 + 团队演示者）与用户故事、用户旅程四阶段、Nice to Have、Look & Feel + 游戏线框图、Technical Considerations、AI / Automation Scope、Quality Standards、Budget & Constraints、Open Questions & Assumptions、Launch Strategy、Definition of Done、Next Steps；**完整保留旧版有效内容**（F1–F5 必做功能、N1–N8 非功能需求、A1–A11 验收标准、红线 R-1–R-5、接口契约摘要、风险与降级、里程碑、变更控制）。机器可读块改为模板规范形态：**文末** `## Handoff Context`（12 字段：Stage/App name/User level/Target platform/Budget/Timeline/AI in product scope/Research status/Constraints/Decisions/Open questions/Source files）+ **最后** 10 键 JSON 元数据（`schemaVersion/documentType/appName/oneLiner/targetUsers/phase/mustHave/niceToHave/notInMvp/successMetrics`），已用 `ConvertFrom-Json` 校验解析通过；占位符扫描无残留。**口径差异（有意）**：PRD 用 A（本次用户确认），工作区既有《项目章程》《需求确认记录》仍记 C。**未写业务代码。** |
| 2026-10-15 | 用户确认 PRD v1.1 无需修正，其中 **Look & Feel 四个关键词（干净 · 跟手 · 可复现 · 诚实）确认保留、不替换**。据此清除 `docs/PRD-BCI-Decoder-MVP.md` 中 3 处"待确认"悬置标注（Design Vibe 小节、Open Questions 小节、Handoff Context 的 Open questions 行），改为已确认表述。PRD 现无未决的文档级待确认项，仅剩 Handoff 中列出的项目级开放问题。**未写业务代码。** |
| 2026-10-15 | 应要求复核 `docs/TechDesign-BCI-Decoder-MVP.md`（v1.0）与 PRD v1.1 的一致性，产出 `docs/PRD-TechDesign-一致性复核.md`。结论：**技术内容基本一致**（栈/版本、16 维特征、窗口步长、通道顺序、p95<50 ms、9 字段契约、产品内无 AI、mock/synth 纪律、`websockets` 未装、命令清单、里程碑③伪在线 <5% 均对齐）；**3 类不一致待处理**：① User level PRD=A vs TechDesign=C（**需拍板，且 A/B/C 被混用了"交付物面向谁"与"团队自身水平"两种含义**）；② PRD must-have「脑控弹球」在 TechDesign 只有提及、**无落地设计**（目录树无游戏端、无启动命令）；③ 三级降级（`MVP规格说明书`§11.2）、伪迹→`idle` 降级、WebSocket 降级路径（jsonl 轮询/本地 TCP）未进 TechDesign。另发现 TechDesign 对 **Part 3 产出契约有结构性偏离**：JSON 在文首而非文末、Handoff 在页脚之前且字段非规范（缺 Stage/AI in product scope/Chosen stack/AI coding tool/Research status/Source files 六项）、JSON 缺 `aiScope` 与空的 `typecheck`/`lint`、缺"备选方案对比"与"成本明细"两节。**已顺手修正 PRD 自身 3 处错误**（控制消息 `reset` 系我上轮误加，冻结契约只有 `start`/`stop`；`notInMvp` 模型条文补"MVP 只用一次性生成的演示模型"），修正后 PRD 533 行、文末 JSON 仍 10 键且解析通过、全文 `reset` 归零。**独立风险**：`bci-decoder/scripts/bootstrap_demo.py` L90–96 会把**合成数据的交叉验证准确率**打印到终端，脚本无警示——触碰红线 R-1，建议加警示并在 TechDesign §6/§8 注明"禁止对外引用"。**未改 TechDesign、未写业务代码。** |
| 2026-10-15 | 弹球端**单独成文**：新建 `docs/TechDesign-Game-MVP.md`（v1.0，383 行）。按 Part 3 规范结构（正文 → 页脚 → `## Handoff Context` 14 字段 → 文末 JSON，已校验顺序与键名）。内容：F4.1–F4.4/A7/A8 验收表、**三个候选技术栈对比（Python+Pygame 采用 / Unity+LSL4Unity 不采用 / Web 前端不采用）及放弃理由**、WebSocket 对接契约（`ws://127.0.0.1:8765`、9 字段用法、**`label_id ⟺ idle` 与 `probs` 定长、以及"用 `confidence` 调速会让 idle 动起来"的语义陷阱**）、**控制率仅 2 条/秒对玩法的硬约束**（禁快节奏、挡板位移量、离散→连续插值但不改语义、窗口 2.0 s 冻结）、Look & Feel 4 词与 4 条视觉原则的落法、`game/` 模块划分（`input_source` 可切 keyboard/ws/jsonl —— 使"键盘版先行"不是额外工作）、命令清单（typecheck/lint/build 留空不编造）、B/C 级降级、测试与红线、风险、里程碑、AI 边界（产品内 none）、开放问题。**关键澄清**：文档里"游戏端技术栈待定"混了两个问题——①本团队 Demo 早已由 `MVP规格说明书` 附录A L600 与学习路线图锁定为 **Python+Pygame（不是待定）**；②Unity 仅属"企业未来客户端"分支，不在 MVP。另修正 PRD 一处措辞：契约定义了 `start/stop/calibrate/load_subject` **四条**，MVP **只需响应 `start`/`stop`**，其余忽略并记日志。复核报告已回填处置结论。**仍未改主 TechDesign（待授权）。** |
| 2026-10-15 | **主 TechDesign 升 v1.1**（用户授权，v1.0 → 417 行）。**Part 3 结构合规**：JSON 元数据由文首移到**文末最后一块**、`Handoff Context` 移到页脚之后并规范为 `- Key: value` **14 字段**（原缺 Stage / AI in product scope / Chosen stack / AI coding tool / Research status / Source files）、补 `aiScope` 与空的 `typecheck`/`lint`、加 `Last Updated`/`Next Review` 页脚。**新增两节**：§3 备选方案对比（算法路线 **频带功率+LDA 采用 / EEGNet 不采用 / 黎曼延后④**；传输 **WebSocket 采用 / LSL 延后④ / jsonl 轮询作降级**，含 LSL4Unity 许可证冲突警示）、§11 成本明细（新增货币支出 **￥0**，估算已标注、非报价）。**内容修复**：User level C→**A**（团队水平移入 Constraints）、头部指向 `TechDesign-Game-MVP.md` 且验收第 5 步补 `python game\pong.py --input ws`、新增 §9 降级策略（B 级首选 jsonl 轮询，零新依赖且不改玩法代码）、§5.4 `state` 取值规则（仅 `stabilizing`/`running`，只表达稳定化阶段、**不得用于改玩法**）、§5.5 伪迹降级链（**"可疑窗口绝不产生新方向"**）、§13 风险表 7 条、N3 抖动 <10 ms 与 `docs/evidence/W{n}_{日期}/` 归档口径、游戏端措辞统一为 **Python+Pygame（Demo 已定）**、`dev` 命令元数据与正文一致（均 `--chunks 200`）、`build` 步骤加**合成数据准确率禁止对外引用**红线提示。**校验**：`json` 代码块仅 1 个且在文末、`ConvertFrom-Json` 解析通过（顶层 6 键 + stack 3 键 + commands 6 键）。**R1 代码补丁未套用**：`bci-decoder/` 归属未拍板，故不擅改他人骨架代码，改为在复核报告 §6 写出可直接套用的两行警示补丁与验证命令。复核报告已全面回填处置状态。**未写业务代码。** |
| 2026-10-15 | **全库口径校准完成**（用户选定任务：校准文档-仓库不一致）。**范围**：`docs/Start项目落地评估.md` §5.1 方案 A 拍板 + §5.2 六条事实性不一致 + 由归属变更引发的全库表述修正，共 **约 15 份文档 / 80+ 处**，分 6 批补丁执行（`patch_mvp.json` 12 处、`patch_core.json` 18 处、`patch_route.json` 27 处、`patch_history.json` 20 处、`patch_misc.json` 4 处、`patch_final.json` 7 处，**全部 applied、0 skipped**）。**关键更正**：① `bci-decoder/` 归属改为团队成果；② Python 口径统一 **3.14.7**（`requirements.txt` 顶部补 3.10+ 声明）；③ 《项目章程》Git 声明改为"尚未完成"；④ 文档围栏 ```bash```→```powershell```（实测全文**并无** `&&`，原表述本身不准确）；⑤ 新建 `docs/evidence/W7_1013/`（README + pytest 证据）；⑥ `game/` 定案 **`bci-decoder/game/`**；⑦ **R1 红线补丁落地**：`bci-decoder/scripts/bootstrap_demo.py` 加两行合成数据警示，`pytest` **14 passed**（2.24 s / Python 3.14.7）；⑧ 复核报告"《项目章程》《需求确认记录》仍记 C"一句经核实不成立，已更正。**未写业务代码**（除上述 2 行警示）。|
| 2026-10-15 | **目录噪音整理**（用户选定；对应 `docs/Start项目落地评估.md` §5.3，处置结果已写回该节）。`tools/` → **`.tools/`**（整目录搬移、层级不变；`md2docx.py` 的 `Path(__file__).parent.parent/"docs"` 相对定位**经运行验证仍正确**）；`bci-decoder/_md2docx.py` → **`.tools/_md2docx_from_bci-decoder.py`**（与 `tools/md2docx.py` 内容不同：13,366 B vs 14,821 B，**两份都保留**、不合并不删除）；`校企合作项目详细要求.jpg` → **`docs/_assets/`**；根目录新增 **`.gitignore`**（排除 `.venv/`、`__pycache__/`、`*.pyc`、`.pytest_cache/`、`artifacts/`、`data/`、`*.joblib|*.npy|*.onnx|*.jsonl`、`.deepworks/`、`.opencode-router/`、`uploads/`、`.tools/*.pdf`、`.tools/check_*.json`）；脚本文档串内的旧用法路径同步更正为 `.tools/md2docx.py`。**校验**：搬移前后逐文件 **SHA256 11/11 一致**、4 个脚本 `py_compile` 通过。**未删除任何文件**——`.pytest_cache/` 目录本体保留（可再生产，删除待人工确认）。**未写业务代码。** |
| 2026-10-15 | **游戏端 PRD 成文**：新建 `docs/PRD-Game-MVP.md`（v1.0，446 行 / 29,513 字节），与 `docs/TechDesign-Game-MVP.md` 成对。按 **Part 2（PRD-MVP）产出契约**：17 个 h2 与兄弟 PRD `PRD-BCI-Decoder-MVP.md` 完全同序（Product Overview → Who It's For → The Problem We're Solving → User Journey → MVP Features → Out of Scope → How We'll Know It's Working → Look & Feel → Technical Considerations → AI / Automation Scope → Quality Standards → Budget & Constraints → Open Questions & Assumptions → Launch Strategy → Definition of Done → Next Steps），页脚 `Document created` / `Status: Draft — Ready for Technical Design` → `## Handoff Context` **12 字段** → **文末 10 键 JSON**。**内容全部取自已核实事实源**（`MVP规格说明书` §2.1/§3.1 F4.1–F4.4、F5.3、§4.2 字段、§4.4 控制消息、§4.5 状态机、§6.1 A7/A8、§6.3 测试口径、§10.1 里程碑表、§11.2 降级、附录A 第 5 步；`TechDesign-Game-MVP.md` 的栈/线框图/命令；`PRD-BCI-Decoder-MVP.md` 的 Look & Feel 与成功指标）。**明确化一处边界**：`confidence` 仅在 `label ∈ {left,right}` 时参与调速，`idle` 时挡板速度恒为 0（源自 TechDesign §6 语义陷阱的落实，非新增需求）。**校验**（`.deepworks/tmp/check_game_prd.py`，45 项全绿）：JSON 文末唯一且 10 键同序可解析、`appName=BCI-Decoder-Game`、h2 与兄弟 PRD 同序、Handoff 12 字段与兄弟 PRD 一致、**线框图与 `TechDesign-Game-MVP.md` 逐字一致**、字段串与冻结契约逐字一致、3 条命令与 TechDesign 的 JSON 元数据一致、无占位符、**无准确率数字**（全文唯一百分号为红线句「交叉验证 100%（必然结果）」）。**未写业务代码。** |
| 2026-10-15 | **接入 Git 远端并完成首次推送**（用户指定仓库名 `motion-imagination-decode-module`）。① `git init -b main`，仓库根 = 工作区根目录；② **关闭 `core.autocrlf`**（系统默认 `true`，会在提交/检出时改写行尾字节）→ 设为 `false`，保持仓库现有字节原样；③ `git remote add origin` → **https://github.com/Bryanhw/motion-imagination-decode-module**；④ 远端**已有 1 个提交**（`4ea612c Initial commit`，仅 `README.md`）→ 先 `git fetch` 再 `git checkout -B main origin/main` **把对方提交接为父提交**，之后在它之上提交，**避免覆盖他人内容与强推**；⑤ 提交身份 `Bryanhw <yhw20070910@outlook.com>`（**仅仓库级** `git config`，未动全局）；⑥ 推送前做**隐私与体积体检**：邮箱 / 手机号 / 密钥扫描 **0 命中**；最大文件为 `docs/` 三个正式 PDF 交付件（1.1 / 0.8 / 0.7 MB）。**结果**：**`7ce8d08`（89 文件 / 12,317 行）已推送**，输出 `4ea612c..7ce8d08 main -> main`，退出码 0，工作区干净、`main` 与 `origin/main` 同步。**同步更正三处已失真口径**：`项目章程` §5.2 仓库行 / 里程碑表 ① 行 / 检查清单「建 Git 仓库」项，`Start项目落地评估.md` §5.2 处置 ③ 与 ③′ / §6 前置项 / §7 边界项，`MEMORY.md` 环境事实与下一步。**未写业务代码。** |
| 2026-10-15 | **失真口径同步收尾 + 仓库首页 README**（用户选定：①"两处都更正"→实做同类残留共 6 处；②顺带清理项只选"补根 README.md"，**未选**删除 `.pytest_cache`、**未选**移出 AI 协作层；③提交方式 = **只提交不推送**）。**① 口径更正 6 处（均已核实原文行，补丁通道 6/6 OK）**：`PRD-BCI-Decoder-MVP.md` —— Handoff `Target platform`「游戏端技术栈待定」→ 已定 Python+Pygame（Unity 属企业未来客户端分支）、Handoff `Open questions`「游戏端用 Unity 还是自研 Python」→ 已关闭并注明 Unity 归属、正文「游戏端技术栈」条、Next Steps 第 4 条加 `docs/PRD-Game-MVP.md` / `docs/TechDesign-Game-MVP.md` 交叉链接；`TechDesign-Game-MVP.md` —— §16 第 1 条（`game/` 路径同文矛盾）→ ✅ 已定案 `bci-decoder/game/` 关闭、§16 第 3 条（User level）→ ✅ 全项目统一为 A 关闭、Handoff `User level` 删去"主 TechDesign 标 C 属残留差异"、Handoff `Open questions` 移除两处已关闭项并保留真正开放项（`websockets` 能否装通优先、两套"三级降级"字母冲突、Unity 企业分支、分辨率适配、`confidence` 映射曲线、`pygame` vs `pygame-ce`）；`PRD-Game-MVP.md` —— Open Questions #2/#8 标记已关闭（`game/` 路径已定案、主 PRD 失真句已同步）、Next Steps #3/#4 改为"已定案/已完成"、Handoff `User level` 与 `Open questions` 同步。**② 新增根 `README.md`**（一页项目入口：一句话 + 当前状态、目录结构与纪律、快速开始命令（含"`bci-decoder/game/` 尚未创建、命令暂不可用"警示与 PowerShell 5.1 不用 `&&`、必须用 `.venv\Scripts\python.exe`）、文档导航表、7 条红线、协作约定；覆盖远端自带通用 README）。**③ 删除仓库根重复副本 `MVP_PRD`**（22,129 B；SHA256 `0C1074620B9009B5D5CDDF460C3F730B5D6FBEFFA0730FBE4C78E4D6D7FC8FA8` 与 `docs/PRD-TechDesign-一致性复核.md` **完全相同**，删除前后 docs 副本哈希未变、**无信息丢失**）。**校验**：`.deepworks/tmp/check_game_prd.py` **45 项全绿（FAILS: none）**；三份文档 `json` 块均解析通过（PRD-BCI 534 行、TechDesign-Game 384 行、PRD-Game 446 行 / 29,455 字节）；残留扫描显示旧口径只剩**历史性引述**（`research-BCI-Decoder.md` / `research-request-BCI-Decoder.md` 研究阶段 Handoff 的 `Target platform` 与 `Open questions`、`TechDesign-Game-MVP.md` §7 对措辞漂移的说明、`PRD-Game-MVP.md` 的关闭留痕）——**未同步，属历史记录不属当前契约**。另：仓库内原有 `README.md` 为远端占位存根（仅 2 行 `# -` / `共用的脑机项目仓库`，Git 初始化时由对方 `4ea612c Initial commit` 带入），已被本页取代（用户选定"补根 README.md"，覆盖存根）。**提交**：`05d2350`（6 文件 / +535 / −13，含 `docs/PRD-Game-MVP.md` 新增）——**仅本地提交，按用户选定未推送**，`main` 领先 `origin/main` 1 个提交。**未写业务代码。** |
| 2026-10-16 | **F5.1 依赖实测与 WebSocket 端到端跑通 + 两处契约缺口修复**（用户指令「请继续」）。**① 依赖实测**：`websockets 17.2` ✅ 装通（cp314 wheel）；**上游 `pygame` 无 Python 3.14 wheel**（`pip install --dry-run --only-binary=:all: pygame` → `ERROR: Could not find a version ... (from versions: none)`），`pygame-ce 2.5.8` ✅ 装通（import 名仍为 `pygame`、`IS_CE=1`、SDL 2.32.10）→ **游戏端依赖定案 = `pygame-ce`**；两者均装入 `bci-decoder/.venv`（不入库；pip 缓存为用户既有配置 `d:\pip-cache`，同在 D 盘，用户已确认无 C 盘/全局污染）。**② 补上两处契约缺口**：文档 6 处写的 `--outputs websocket` 在 `cli.py` 中**原本不存在** → 给 `run` 子命令新增 `--outputs`（逗号/空格分隔，覆盖 `cfg.output.sinks`，不传则沿用配置）；`outputs/websocket.py` 关停改为**幂等优雅流程**（`_stop` Event + `async with websockets.serve` + `call_soon_threadsafe` + `join(3.0)` + `loop.is_closed()` 守卫），消除退出噪音（`Task was destroyed but it is pending!` / `RuntimeError: no running event loop` / `coroutine ... was never awaited`）。**③ 新增正式回归测试** `bci-decoder/tests/test_websocket_sink.py`（2 个用例：9 字段契约 + `label_id ⟺ idle`；close 幂等且关停后 emit 静默）→ **`pytest` 14/14 → 16/16**。**④ 证据**：sink 级 `verify_ws_end2end.py` **27/27 FAILS=0**；CLI 级 `verify_cli_ws.py` **21/21 FAILS=0 EXITCODE=0**（短跑退出码 0、日志 `输出通道=['websocket']`、无 Traceback；长跑客户端实收 5 条，样例 `{"t_data": 77.996, "label": "idle", "label_id": -1, "confidence": 0.6459, "probs": [0.0, 1.0], "state": "running", "compute_ms": 4.535, "window_seconds": 2.0}`）；pygame-ce headless 冒烟 120 帧无异常。**⑤ 文档口径回写 88 处**（8 批补丁：`patch_dep_verify.json` 26 + `patch_count_fix.json` 24 + `patch_ws_fact.json` 10 + `patch_ws_fact2.json` 2 + `patch_ws_fact3.json` 3 + `patch_ws_fact4.json` 1 + `patch_ws_fact5.json` 20 + `patch_ws_fact6.json` 2）：`README.md`、`AGENTS.md`、`MEMORY.md`、`agent_docs/tech_stack.md`、`MVP规格说明书.md` §0/§8/§9、`PRD-BCI-Decoder-MVP.md`、`PRD-Game-MVP.md`（Open Q #1/#7 关闭）、`TechDesign-Game-MVP.md`（§5 栈表、风险表、§16、Handoff）、`在线解码模块设计说明.md`、`详细技术路线.md`、`项目章程.md`、`项目计划书.md`、`脑机接口运动想象解码项目规划.md`、`与天津大学脑机方向技术交流问题清单.md`、`PRD-TechDesign-一致性复核.md` —— 统一为 `websockets` ✅ 已验证、`pygame-ce` 定案、`pip install pygame-ce websockets`、测试计数 **16/16**。**未写业务代码**（除上述 CLI/输出通道修复与新增测试）。**提交**：`a7610f5`（21 文件 / +236 / −91，含 `bci-decoder/tests/test_websocket_sink.py` 新增）——**仅本地提交，按用户选定未推送**（`main` 领先 `origin/main` 3 个提交）。 |
| 2026-10-16 | **依赖写入 `requirements.txt`（用户拍板「两个都加」）**：`websockets>=17.2` 由注释占位行提升为**必需依赖**（原 `# websockets>=12.0` 已取消注释并更新版本）；新增游戏端必需依赖 `pygame-ce>=2.5.8`（附注「勿装上游 `pygame`，无 Python 3.14 wheel」）。理由：他人重装环境时不可缺，且 F5.1 / F4 均已实装验证。**提交**：`3d880a2`（2 文件 / +5 / −1）——**仅本地提交，按用户选定未推送**。 |
