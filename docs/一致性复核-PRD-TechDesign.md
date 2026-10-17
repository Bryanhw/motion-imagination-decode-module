# PRD ↔ TechDesign 一致性复核

> **复核日期**：2026-10-15
> **复核对象**：`docs/MVP_PRD.md`（v1.1） ↔ `docs/TechDesign-BCI-Decoder-MVP.md`（复核时 **v1.0**，已据此修至 **v1.1**）
> **核对依据**：`docs/MVP规格说明书.md`（范围与验收**唯一冻结依据**）、`REVIEW-CHECKLIST.md`、`vibe-coding-prompt-template` Part 3 产出契约、`bci-decoder/` 实际代码与依赖现状
> **复核目的**：避免 AI 助手同时拿到两份"都像权威"的文档，产生互相矛盾的实施口径

> **说明（2026-10-16）**：本文件是一份**一致性复核报告**（PRD ↔ TechDesign 是否互相矛盾），**不是需求 PRD**。
> 全项目主 PRD 见 [`MVP_PRD.md`](MVP_PRD.md)；范围与验收的最终依据见 [`MVP规格说明书.md`](MVP规格说明书.md)。
> **处置状态（2026-10-15）**：✅ **已执行完毕**——PRD 侧 4 项、TechDesign 侧 14 项全部落地（升 v1.1）；弹球端单独成文；仅剩 **1 项代码补丁**因 `bci-decoder/` 归属未拍板而**挂起**（见 §6 代码侧）。

---

## 0. 结论速览

| 维度 | 结论 |
|---|---|
| **技术内容一致性** | **基本一致**。技术栈、契约字段、窗口/步长、通道顺序、性能指标、AI 范围、命令清单均对齐，无实质算法冲突 |
| **面向读者的口径** | ~~❌ 不一致~~ → ✅ **已统一为 A**（2026-10-15 拍板）；"团队实现水平 = C" 改记入 TechDesign 的 Constraints |
| **功能覆盖** | ✅ **已补齐**：「脑控弹球」单独成文 `docs/TechDesign-Game-MVP.md`；三级降级、伪迹降级 `idle`、WebSocket 降级路径均已进主 TechDesign v1.1 |
| **TechDesign 对 Part 3 产出契约的合规** | ~~❌ 有结构性偏离~~ → ✅ **已合规**：JSON 移文末、页脚后接 Handoff Context（14 字段）、补 `aiScope`；并补"备选方案对比"与"成本明细"两节 |
| **独立风险** | ⚠️ 1 项红线风险**仍在**：`bootstrap_demo.py` 会把合成数据的交叉验证准确率打印到终端。**文档侧已加红线提示**；代码补丁待归属拍板后套用（§6 代码侧） |
| **本次已直接修正** | ✅ PRD 3 处（§3）＋ 主 TechDesign 升 **v1.1**（§6）＋ 新建 Game 文档；**均已验证** |

**后续动作（2026-10-15 已拍板后）**：User level 统一为 **A**、授权修改主 TechDesign 并升 **v1.1**、弹球端单独成文——三项**已执行完毕**（见 §6）。
**归属口径已拍板（2026-10-15）：`bci-decoder/` ＝ 本团队成果、计入项目进度**，R1 代码补丁随之解冻并已套用（见 §6 代码侧）。

---

## 1. 已一致项（无需动作）

以下逐条核对通过，**不要因为改动文档而把它们的口径改歪**。

| 项 | PRD 位置 | TechDesign 位置 | 核对结果 |
|---|---|---|---|
| 技术栈与版本（Python 3.14.7 / NumPy 2.5.3 / SciPy 1.18.1 / scikit-learn 1.9.1） | Technical Considerations | §2 L68–70 | ✅ 一致 |
| 特征方案：频带功率（mu 8–13 / beta 13–30）× 8 通道 = **16 维** + LDA | Technical Considerations | §4.3 L145–146 | ✅ 一致 |
| 滑窗 **2.0 s** / 步长 **0.5 s** | Budget & Constraints | §4.3 L144 | ✅ 与冻结契约一致 |
| 采样率 250 Hz、8 通道、顺序 `C3,Cz,C4,CP3,CP4,P3,P4,Oz` | Technical Considerations | §4.1 L117–118 | ✅ 一致，且 TechDesign 附加了"顺序即语义"警告 |
| 单次计算 p95 **< 50 ms** | Must-Have 验收 | §8 L228 | ✅ 一致 |
| 输出契约 9 字段 + 不变式（`label_id == -1 ⟺ idle`；`probs` 长 2 和为 1） | 接口契约摘要 | §4.2 L126–136 | ✅ 一致，未增删字段 |
| **产品内无 AI**（确定性信号处理，无深度学习/LLM/GPU） | AI / Automation Scope | §9 L239 | ✅ 一致 |
| `mock` / `synth` 只作工程自检，**不得用于评测** | 红线 R-1 | §8 L232 | ✅ 一致 |
| `websockets` 尚未安装（F5 的关键依赖） | 风险与降级 | §2 L74/79、§10 L249 | ✅ 一致，双方均如实标注未验证（**2026-10-16 更新：已装通并端到端验证，两侧文档已同步更正**） |
| 命令清单（`pytest` / `cli run` / `cli benchmark` / `cli show-config` / `bootstrap_demo.py`） | Next Steps | §6 L180–189 | ✅ 一致；TechDesign 更完整（含 benchmark、show-config） |
| 模型产物落 `artifacts/`，**不入库** | 目录纪律 | §3 L104、§7 L215 | ✅ 一致 |
| 里程碑 ③ 伪在线回放一致性偏差 **< 5%** | 成功指标（增长指标） | §10 L250 | ✅ 一致 |
| Windows PowerShell 5.1、**不用 `&&`** | Budget & Constraints | §6 L178 | ✅ 一致 |
| 100 ms 块长建议 | — | §4.1 L119 | ✅ 与冻结契约建议一致 |

---

## 2. 不一致项（需修）

按严重度排序。**P1 = 会导致实施口径分裂；P2 = 内容缺口；P3 = 措辞/完整性。**

### P1-1　User level 口径冲突（**需你拍板**）

| 文档 | 声明 |
|---|---|
| `MVP_PRD.md` | **A**（零基础 vibe coder）— 上一轮你已确认采用 A |
| `TechDesign-BCI-Decoder-MVP.md` L260 | **C**（somewhere in between） |
| ~~`docs/项目章程.md`、`docs/需求确认记录.md`~~ | **—**（2026-10-15 核实：两文件**并无** User level 字段，原判定系未经核实的推断，已更正） |

**影响**：TechDesign 是 Part 4（AI 施工）的直接输入。若它自报 C，AI 助手会按 C 的深度写代码与注释，与 PRD 的 A 口径（"零基础也能读懂、能讲清"）冲突。

**注意**：这里还有一个易被忽略的语义陷阱——`A/B/C` 在本项目中其实被当作**两种不同含义**用过：
1. **交付物面向谁**（A = 零基础也能用/看懂）；
2. **团队自身技术水平**（C = 中间态）。

这两个含义混在同一字段里，是冲突的根源。**建议明确区分**，例如：产品与文档的可读性按 **A** 要求，团队实现能力按 **C** 记录（写进 `Decisions` 或 `Constraints`）。

### P1-2　F4「脑控弹球」在 TechDesign 中没有落地设计

- PRD 把「脑控弹球游戏 Demo（键盘可玩 → 解码可玩）」列为 **must-have**。
- TechDesign §3 目录树（L86–107）**只有 `bci-decoder/`**，没有任何游戏端代码位置、技术选型或实现要点。
- TechDesign §6 验收五步第 5 步（L203）写"启动 WebSocket + 脑控弹球"，但**只给了解码侧命令**，没有游戏启动命令。
- §10 里程碑②只写"弹球 Demo 打通"，`已知技术债` 列"游戏端技术栈未定"。

**结论**：弹球是 must-have，却在技术设计里处于"提及但未设计"状态，**Part 4 拿到它无法开工**。这是本次复核发现的最大实质缺口。

> ✅ **已处置（2026-10-15）**：按团队决定**单独成文**，新建 [`TechDesign-Game-MVP.md`](TechDesign-Game-MVP.md)（v1.0）。该文档含：F4.1–F4.4/A7/A8 验收表、三个候选技术栈对比与取舍、WebSocket 对接契约（含 `label_id ⟺ idle`、`probs` 定长、`confidence` 在 `idle` 时的语义陷阱）、**2 条/秒控制率对玩法的硬约束**、Look & Feel 承接、目录与命令清单、B/C 级降级、测试与红线、Handoff Context 与文末 JSON。
> **待办**：主 TechDesign 需补一行指向该文档（见 §6）。

### P1-3　数据源/降级路径不完全对应

- PRD「风险与降级」写：WebSocket 打不通时降级为 **jsonl 文件轮询 或 本地 TCP**（L152）。
- TechDesign 只在 §8 写"依赖缺失风险"，**没有这条具体降级路径的实现设计**（哪个模块、怎么切换、`configs/*.yaml` 里怎么配）。

### P2-1　三级降级方案（A/B/C 级）未进入 TechDesign

`docs/MVP规格说明书.md` §11.2（L554–565）定义了 A/B/C 三级降级，明确"B 级砍 `jsonl` 落盘/控制消息等，C 级砍全部 WebSocket、改文件读取"。PRD 已在 Launch Strategy 收录，**TechDesign 完全未提**。

**影响**：降级决策直接改变技术范围（C 级不需要 WebSocket），而 TechDesign 把 WebSocket 当成 F5 默认路径，两者在"时间不够"时会对不上。

### P2-2　伪迹超阈值 → 降级 `idle` 未落地

- PRD F3 要求：信号质量异常/不可信时输出 `idle`。
- TechDesign §4.3 配置为 `artifact: { method: ptp, threshold_uv: 150, action: mark }`，**只有"标记"**；§5.3 只讲"未训练 → idle"。
- 冻结契约的 `state` 字段（`running` / `stabilizing`）也未在 TechDesign 说明何时取何值。

**影响**："信号差 → 不动"这条安全链在技术设计里缺了中间一环。

### P2-3　TechDesign 对 Part 3 产出契约的结构性偏离

Part 3 明确规定：**正文与页脚 → Handoff Context → 最后一块 JSON 元数据**。当前文档：

| 契约要求 | TechDesign 现状 | 判定 |
|---|---|---|
| JSON 元数据是**文末最后一块** | JSON 在**文首**（L12–31），文末是斜体页脚（L285） | ❌ |
| Handoff Context 在**页脚之后** | Handoff（L256–281）在页脚（L285）**之前** | ❌ |
| Handoff 用 `- Key: value` 规范字段 | 用自定义 `app:/level:/platform:` 文本块 | ❌ 结构不合规 |
| Handoff 含 14 个字段，其中 **Stage / AI in product scope / Chosen stack / AI coding tool / Research status / Source files** | **6 项缺失**（`decisions` 里隐含了 stack，但没有独立字段） | ❌ |
| JSON 含 `commands.typecheck` / `commands.lint`（不适用时留空，不要凭空编造） | **两键缺失**（§6 L189 已说明"未设置"，应留空键） | ⚠️ |
| JSON 含 `aiScope` | **缺失**（§9 正文有"产品内无 AI"） | ❌ |
| JSON 的 `stack` 可省略不适用键 | 省略了 database/auth/styling ✅，但 `frontend` 值为"无（headless…）" | ✅ 可接受 |
| 必须提供 2–3 个**备选方案对比 + 利弊** | §2 是单张选型表，无备选对比 | ❌ |
| 必须含 **成本明细**（估算标注、指向官方价格页） | 只有 Handoff 的 `budget: ￥0`，无成本表 | ❌ |
| AI 协助策略（哪个工具做哪件事） | §9 仅 3 条要点，无工具分工 | ⚠️ 偏弱 |
| 命令/验证描述诚实 | §6 明确写"lint/typecheck 未设置" ✅ | ✅ |
| 页脚含 `Last Updated` / `Next Review` | 无日期页脚 | ⚠️ |

> **注意**：这些偏离是"格式契约"问题，不影响技术内容正确性；但 Part 3 的 `vibeworkflow` CLI 与 Part 4 会按契约解析，建议修。

### P3-1　游戏端技术栈措辞漂移（三处不一致）

| 位置 | 措辞 |
|---|---|
| PRD Open Questions | "Unity 还是**自研 Python**" |
| TechDesign §10 L249 | "游戏端技术栈未定" |
| TechDesign Handoff L279 | "**Unity / Pygame**" |

**根因（比"措辞不统一"更深一层）**：项目文档把**两个不同的问题**混成了一句话——

| 问题 | 事实 |
|---|---|
| **① 我们自己的 Demo 用什么？** | **不是待定**：`MVP规格说明书` 附录A L600 已写 `python game\pong.py`，`大一学生学习路线图.md` L30/L204/L250 已定 **Pygame**、责任人黄凯森 |
| **② 企业未来客户端用什么？** | 若企业做客户端大概率是 **Unity** → 那时才需要 LSL4Unity vs WebSocket 的取舍。**不在 MVP 范围** |

**建议统一为**：「本团队 Demo = Python + Pygame（已定）；企业未来客户端可能是 Unity，届时再评估 LSL4Unity（`research-BCI-Decoder.md` §6：其许可证来源冲突未定论、主分支 2023-07-31，采用前须读 LICENSE 正文）」。已在新文档 §4.1 按此拆开表述。

### P3-2　PRD 有、TechDesign 无的细节（可接受，但建议补一句指向）

| 项 | PRD/冻结依据 | TechDesign |
|---|---|---|
| 调度抖动 **< 10 ms** | PRD N3 | 无 |
| 证据归档目录 `docs/evidence/W{n}_{日期}/` | `MVP规格说明书` §11.1 L552、PRD A11 | 无（§8 只写"长跑脚本"） |
| **不采集真实患者数据**（伦理未走完） | `MVP规格说明书` §11.3 L574 | 无 |
| nice-to-have：演示页、证据归档脚本 | PRD Nice to Have | 无（§8 提到长跑脚本） |

### P3-3　JSON 元数据中的 `dev` 命令与正文不完全一致

- 元数据 `commands.dev` = `python -m bci_decoder.cli run --config configs/demo_online.yaml`
- §6 正文 dev = 同命令 **+ `--chunks 200`**

建议统一（元数据里保留不带 `--chunks` 的通用形式亦可，但要与正文说明对齐）。

---

## 3. 本次已直接修正（PRD 侧）

均已改完并验证。

| # | 位置 | 原内容 | 改为 | 依据 |
|---|---|---|---|---|
| 1 | PRD L160（Nice to Have） | 契约里已定义 `start / stop / **reset**` 等控制消息 | 冻结契约里只定义了 `{"cmd":"start"}` / `{"cmd":"stop"}` 两条（F5.2，P2） | `MVP规格说明书` §4.4 L236–245：控制消息**只有** `start` / `stop` |
| 2 | PRD L510（JSON `niceToHave`） | 控制消息最小实现（start / stop / **reset**） | 控制消息最小实现（start / stop） | 同上 |
| 3 | PRD L515（JSON `notInMvp`） | 模型训练产物保存 / 加载（里程碑 ③） | 模型训练产物保存 / 加载（里程碑 ③；**MVP 只用一次性生成的演示模型**） | `MVP规格说明书` L85–86：模型保存/加载归 ③，但"MVP 用预置演示模型"；TechDesign §6 build 步骤即生成该模型 |

> **验证记录**：修正后 `docs/MVP_PRD.md` 共 533 行；文末 JSON 代码块 **1 个**、可正常解析；顶层键仍为 **10 个**（`schemaVersion, documentType, appName, oneLiner, targetUsers, phase, mustHave, niceToHave, notInMvp, successMetrics`，顺序未变）；全文 `reset` 匹配数 **0**。

---

## 4. 独立风险（不属于两文档比对的范畴，但必须记下）

### R1 ⚠️ 红线风险：`bootstrap_demo.py` 会把**合成数据的交叉验证准确率**打印到终端

`bci-decoder/scripts/bootstrap_demo.py`（L90–96）在结束时输出：

```json
{ "n_trials": ..., "n_features": 16, "cv_accuracy": <数字>, "model_path": ..., "classes": [...] }
```

该数字来自**合成数据**，按红线 R-1 与 `AGENTS.md` 硬性约束第 5 条，**交叉验证 100% 是必然结果，绝不可用于评估算法性能或对外报告**。脚本本身没有针对这个数字的警告。

**处置状态（2026-10-15）**：
1. ⏳ **未做**——`cv_accuracy` 输出旁加显式警示（补丁见 §6 代码侧；本项已被链路能力确认可用、无阻塞，故**不是因为没时间**，而是**归属未拍板**）；
2. ✅ **已做**——主 TechDesign v1.1 §7 的 `build` 命令行与 §10 测试纪律处，均已写入"合成数据准确率**禁止对外引用**"红线提示；
3. ✅ **已固化**——v1.1 §7 / §10 / §12 三处均写明"答辩与文档中不得出现该数字"。

> **残留风险等级**：**中**。文档侧已封住"被误引用"的路径，但只要有人直接在终端跑 `bootstrap_demo.py`，屏幕上仍会出现一个接近 100% 的准确率数字——**演示前应确认演示脚本不展示该输出**。

### R2　既知不一致（不在本次范围，避免重复登记）

TechDesign §2 L68 写"文档口径为 3.10+，当前环境 3.14.7"，与 `docs/Start项目落地评估.md` 已登记的 6 处"文档-仓库不一致"属同一批，此处不重复计入本次结论。

### R3　若游戏端由本团队实现，TechDesign 需要一节"游戏端设计简报"　✅ **已处置**

PRD 的 Look & Feel 四词（已确认为产品调性）原没有承接处：主 TechDesign 明确"无 UI（headless）"，F4 因此悬空。

**处置结果**：已新建 `docs/TechDesign-Game-MVP.md`（v1.0），承接 Look & Feel、玩法、输入源切换（keyboard / ws / jsonl）、与解码端的对接契约（含 2 条/秒控制率的硬约束）、命令与验收；主 TechDesign v1.1 头部与验收五步第 5 步均已加指向。
**结论**：R3 **已闭环**，F4 不再悬空。
**仍需注意**：`game/` 的最终路径（仓库根 vs `bci-decoder/game/`）与【阻塞项】`bci-decoder/` 归属口径同源，需一并拍板。

---

## 5. 待你拍板的问题

1. **User level 统一为哪个？**
   - 选项 A：两文档都改成 **A**（与 PRD 一致，TechDesign 需补术语解释与新手路径）
   - 选项 B：保留差异但**写清两种含义**（产品可读性 = A；团队能力 = C）
   - 选项 C：两文档都改成 **C**（需回改 PRD，且与"零基础也能讲清"的诉求相悖）

2. **TechDesign 是否授权修改？** 它是 Part 3 的产出物，本次只复核未改。若授权，建议按 §6 清单一次性改完并升版 v1.1。

3. ~~**P1-2（弹球无设计）怎么处理？**~~ ✅ **已于 2026-10-15 拍板：单独成文**，见 `docs/TechDesign-Game-MVP.md`。

---

## 6. 修复清单（可勾选）

### PRD 侧
- [x] 控制消息 `reset` → `start / stop`（L160、L510）
- [x] `notInMvp` 模型条文补充"MVP 只用一次性生成的演示模型"（L515）
- [x] 控制消息措辞改精确：契约**定义了 4 条**（`start`/`stop`/`calibrate`/`load_subject`），MVP **只需响应 `start` / `stop`**，其余忽略并记日志（L160）
- [x] User level：PRD 已是 **A**，无需改动；"团队实现水平 = C" 改记入 TechDesign 的 Constraints，不再占用 level 字段

### TechDesign 侧（**已授权并执行 → v1.1**）
- [x] **P1-1** `User level` 统一为 **A**（团队实现水平 C 移入 Constraints）
- [x] **P1-2** 补 F4 弹球落地设计 → **单独成文** `docs/TechDesign-Game-MVP.md`（v1.0）
- [x] **P1-2 收尾** 主 TechDesign 头部加指向 Game 文档；验收五步第 5 步补游戏端命令 `python game\pong.py --input ws`
- [x] **P1-3** 新增 **§9 降级策略**：WebSocket 首选降级 `jsonl` 轮询（零新依赖）、备选本地 TCP，且不改玩法代码
- [x] **P2-1** 收录 A/B/C 三级降级（引 `MVP规格说明书` §11.2）
- [x] **P2-2** 新增 **§5.4** `state` 取值规则 + **§5.5** 伪迹降级链（含"可疑窗口绝不产生新方向"）
- [x] **P2-3** 结构合规：JSON 移到**文末最后一块**；页脚后接 `## Handoff Context`（**14 字段**，规范 `- Key: value`）；JSON 补 `aiScope` 与空的 `typecheck` / `lint`
- [x] **P2-3** 新增 **§3 备选方案对比**（算法路线 3 候选 + 传输机制 3 候选，各含利弊与结论）与 **§11 成本明细**（估算已标注、非报价）
- [x] **P3-1** 统一游戏端措辞：**Demo = Python + Pygame（已定）**；Unity 属"企业未来客户端"分支（不在 MVP）
- [x] **P3-2** 补 N3 调度抖动 < 10 ms、`docs/evidence/W{n}_{日期}/` 归档、不采真实患者数据、nice-to-have 指向
- [x] **P3-3** 统一 `dev` 命令（元数据与正文一致，均为 `--chunks 200`）
- [x] **R1** §7 `build` 步骤与 §10 测试纪律处新增"合成数据准确率禁止对外引用"红线提示
- [x] **新增** §13 风险表（7 条，含 `websockets` 未验证、通道顺序、`state` 被滥用）

> **v1.1 校验记录**：417 行；`json` 代码块 **1 个**且位于文末、解析通过（顶层 6 键 + `stack` 3 键 + `commands` 6 键）；结构顺序 `正文 → 页脚 → Handoff Context → JSON` 正确；Handoff 字段 **14 个**。

### 代码侧（**未执行——受【阻塞项】限制**）
- [ ] **R1** `bci-decoder/scripts/bootstrap_demo.py`：给 `cv_accuracy` 加显式警示。
  **为什么可以改**：归属口径已拍板为**团队成果**（2026-10-15，见 `docs/Start项目落地评估.md` §5.1 方案 A）——代码是团队自己的，补丁已套用（见 §6 代码侧）。
  **待拍板后可直接套用的补丁**（在 L90 `print(json.dumps({...}))` 之前插入两行）：

  ```python
  print("⚠️ 注意：以下 cv_accuracy 来自【合成数据】，只用于自检链路是否贯通，")
  print("   不是算法性能，禁止用于评估或对外报告（真实基线见里程碑 ③）。")
  ```

  **验证方式**：`bci-decoder\.venv\Scripts\python.exe -m pytest`（应全绿），再跑一次 `python scripts/bootstrap_demo.py` 确认警示与原有输出共存。
  **临时缓解（已生效）**：主 TechDesign v1.1 §7 与 §10 已写入"该数字禁止对外引用"的红线提示，走 B 级降级路径（§9）也无需该数字。

---

## 7. 复核范围与未覆盖

**已覆盖**：两份主文档的**技术内容、范围、口径、产出契约格式**逐项比对；并用冻结契约（`MVP规格说明书`）与仓库实际代码（`bootstrap_demo.py`、依赖现状）作为事实裁定依据。

**未覆盖**（明确声明，避免误以为已核）：
- `bci-decoder/` 代码实现与文档的一致性（另属 `docs/Start项目落地评估.md` §5 的范畴，已有 6 处登记）；
- `agent_docs/`、`docs/在线解码模块设计说明.md`、`docs/详细技术路线.md` 与两份主文档的细节一致性（它们是"详版"，本次只按"冲突时以详版为准"引用其结论）；
- `docs/research-BCI-Decoder.md` 的研究结论是否已被 PRD 完整吸收；
- `bci-decoder/ 归属口径` ✅ **已拍板（2026-10-15）：团队成果、计入进度** —— 本复核结论可用于进度宣称，**但仅限已核实部分**（链路跑通 + 17/17 测试，2026-10-16 更新）。

---

## 附录：关键证据行号

| 事实 | 出处 |
|---|---|
| 控制消息只有 `start` / `stop` | `docs/MVP规格说明书.md` L236–245（F5.2，P2） |
| `state` 字段与状态机 | `docs/MVP规格说明书.md` L214、L254–258 |
| 模型保存/加载归 ③，MVP 用预置演示模型 | `docs/MVP规格说明书.md` L85–86 |
| 证据目录 `docs/evidence/W{n}_{日期}/` | `docs/MVP规格说明书.md` §11.1 L552 |
| 三级降级 A/B/C | `docs/MVP规格说明书.md` §11.2 L554–565 |
| 明确不做（含不采真实患者数据） | `docs/MVP规格说明书.md` §11.3 L567–574 |
| PRD 的降级路径（jsonl 轮询 / 本地 TCP） | `docs/MVP_PRD.md` L152 |
| TechDesign 的 `artifact.action: mark` | `docs/TechDesign-BCI-Decoder-MVP.md` §4.3 L143 |
| TechDesign 的 build = 训练并保存模型 | `docs/TechDesign-BCI-Decoder-MVP.md` §6 L184 |
| 合成数据 CV 准确率被打印 | `bci-decoder/scripts/bootstrap_demo.py` L90–96 |
| Part 3 的 Handoff/JSON 契约 | `vibe-coding-prompt-template` `part3-tech-design-mvp.md`（"Document Output and Order"、"Handoff Context (Required)"、"Machine-Readable Summary"） |

---

*复核人：DeepWorks（AI 助手）｜复核方式：逐项比对 + 冻结契约裁定 + 仓库事实抽查*
