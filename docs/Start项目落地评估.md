# 对照 vibe-coding-prompt-template「Start a project」的改进评估

> **评估对象**：本仓库 —— 翔宇医疗校企合作项目（脑控游戏 · 运动想象在线解码模块）
> **对照基准**：GitHub `KhazP/vibe-coding-prompt-template` 的 **Start a project** 五步流程，及其
> `docs/workflow/golden-path-checklist.md`（黄金路径清单）与 `docs/workflow/document-contract.md`（文档契约）
> **评估日期**：2026-10-15
> **评估范围**：**仅 Start a project 阶段（Step 1–4 的文档与 agent 配置）**，不含 Step 5「编码」。
> 本文件只做"对照与改进"，**不改动**任何现有冻结文档。

---

## 1. 该工作流在此处要求什么

| 步骤 | 名称 | 要求的产出 | 落盘位置 |
|---|---|---|---|
| Step 1 | Research | 研究结论（含竞品、MVP 范围、风险、带日期的来源） | `docs/research-[AppName].md` |
| Step 2 | Define the MVP | PRD（含 **Handoff Context** + **JSON 元数据**） | `docs/PRD-[AppName]-MVP.md` |
| Step 3 | Choose technical approach | 技术设计（stack / commands / 数据模型 / 部署 / 验证） | `docs/TechDesign-[AppName]-MVP.md` |
| Step 4 | Set up coding assistant | agent 指令文件 | `AGENTS.md`、`MEMORY.md`、`REVIEW-CHECKLIST.md`、`agent_docs/*` |
| Step 5 | Build | 可运行代码 | 项目根（**本次不做**） |

本仓库统一取 **AppName = `BCI-Decoder`**（两份契约文档的应用名必须一致）。

---

## 2. 现状映射：你们已有的文件

| 工作流要求 | 本仓库现有对应物 | 判定 |
|---|---|---|
| research 文档 | `脑机接口运动想象解码项目规划.md`、`开源项目参考清单.md` | 内容充足，**缺契约命名与来源日期标注** |
| PRD | `MVP规格说明书.md`（v1.0 已冻结） | 内容非常扎实，**缺契约命名 / Handoff Context / JSON 元数据 / AI 范围** |
| TechDesign | `在线解码模块设计说明.md`、`详细技术路线.md` | 内容充足，**缺命令段 / 部署段 / 契约命名 / JSON 元数据** |
| `AGENTS.md` | 无 | **缺** |
| `MEMORY.md` | 无 | **缺** |
| `REVIEW-CHECKLIST.md` | 无 | **缺** |
| `agent_docs/` | 无 | **缺** |

> **结论**：你们的**规划文档质量高于多数同类项目**（范围分界、验收口径、降级方案都很清楚）。
> 真正缺的是工作流最强调的**"给 AI 助手看的那一层"**：`AGENTS.md` / `MEMORY.md` / `REVIEW-CHECKLIST.md` / `agent_docs/`。
> 没有这一层，AI 助手每次都要重新读 11 份中文长文档，既慢又容易读错源。

---

## 3. 缺口清单（逐条对照黄金路径 checklist）

| # | 黄金路径要求 | 现状 | 结论 |
|---|---|---|---|
| 1 | Research 含竞品、MVP 范围、风险、**带日期的来源** | 有规划与开源清单，但未标注"哪条已核实/哪条未核实"、无日期 | ⚠️ 已补 `research-BCI-Decoder.md` |
| 2 | PRD 说清"面向谁 / v1 必做 / 不在范围" | `MVP规格说明书` 第 1–2 节已完全满足 | ✅ 内容达标 |
| 3 | TechDesign 列 stack、**commands**、数据模型、部署、验证步骤 | 缺"命令清单"与"部署"两节；数据模型与验证有其他文档覆盖 | ⚠️ 已补 |
| 4 | **AI 范围显式声明**（none / 简单 AI 功能 / 内部 agent / MCP / 本地模型 / builder 辅助） | **两份主文档都没写** | ❌ 已补（PRD §7、TechDesign §9） |
| 5 | `AGENTS.md` 要短，指向 `agent_docs/` 而非复制全部内容 | 无 | ❌ 已补 |
| 6 | `agent_docs/tech_stack.md` 含**确切的** setup / dev / test / build 命令 | 命令散落在 3 份文档的附录里 | ❌ 已补 |
| 7 | `agent_docs/testing.md` 说明"完工前需要什么证据" | `MVP规格说明书` 6.3 有测试口径，但未独立成 agent 可读文件 | ⚠️ 已补 |
| 8 | 工具适配文件**只为所选工具生成** | 你们用 DeepWorks（`AGENTS.md` 体系）→ 只需 `AGENTS.md`，**不需要** `.cursor/`、`CLAUDE.md`、`.github/copilot-instructions.md` | ✅ 已按此处理 |

---

## 4. 本次新增的文件（全部为**新增**，未改动任何现有文档）

| 文件 | 对应步骤 | 作用 |
|---|---|---|
| `docs/Start项目落地评估.md` | — | 本文件（改进评估） |
| `docs/research-BCI-Decoder.md` | Step 1 | 研究结论汇总 + 核实状态标注 |
| `docs/PRD-BCI-Decoder-MVP.md` | Step 2 | 契约版 PRD（含 Handoff Context + JSON 元数据） |
| `docs/TechDesign-BCI-Decoder-MVP.md` | Step 3 | 契约版技术设计（含命令清单 + JSON 元数据） |
| `AGENTS.md` | Step 4 | AI 助手的长期规则入口 |
| `MEMORY.md` | Step 4 | 当前进度 / 决策 / 下一步 |
| `REVIEW-CHECKLIST.md` | Step 4 | 实现期与验收期的检查清单 |
| `agent_docs/project_brief.md` | Step 4 | 项目速览（给 agent 的"一页纸"） |
| `agent_docs/tech_stack.md` | Step 4 | 技术栈与**确切命令** |
| `agent_docs/testing.md` | Step 4 | 证据与测试纪律 |

> 新增文件与既有文档的关系：**既有文档仍是内容最完整的"详版"**；
> 新增的契约文档是"工作流可解析的那一层"，二者不冲突、不重复关键表格。

---

## 5. 必须由团队拍板的一致性问题（比"缺文件"更重要）

> 以下不是格式问题，而是**评审时会被追问、且会导致 AI 助手判断错误**的实质问题。

### 5.1 `bci-decoder/` 的归属口径自相矛盾【最高优先级】

> ✅ **已拍板（2026-10-15）：采用方案 A —— `bci-decoder/` ＝ 本团队成果（团队借助 AI 编码助手实现），计入项目进度。**
> 以下为**拍板前的评估记录，原样保留作为决策依据**；各文档的相关表述已于 2026-10-15 逐处更正。

- 《项目章程》第 11 节、《MVP 规格说明书》第 15/637 行、《在线解码模块设计说明》第 253–291 行 均声明：
  **`bci-decoder/` 是"他人编写的参考骨架"，不属于本团队成果、不计入进度。**
- 但仓库内的事实是：它是一个**完整可运行实现**，包含自己的 `.venv`（Python 3.14.7）、
  `artifacts/demo_lda.joblib`（已训练模型）、`artifacts/decoder_output.jsonl`（已产出解码结果），
  且 `python -m pytest` **14 项全部通过**（本次核实，2026-10-15）。

**两套口径并存 → 必须二选一：**

| 方案 | 做法 | 影响 |
|---|---|---|
| **A. 认作团队成果** | 更新《章程》/《规格说明书》的进度口径，把 M1 标记为 🔄，并按"自己写、自己调通"补测试与实验记录 | 进度口径变诚实，但需补 LSL/WebSocket 的真实运行证据 |
| **B. 明确为参考资料** | 保留"参考骨架"定性，**另建 `app/`**（或 `src/`）目录写团队自己的实现 | 需要真正的从零实现工作量，MVP 时间会紧张 |

> **不选也是一种选择**：现状会让 AI 助手（和评审）无法判断"这条链路的测试通过，算不算你们的进度"。
> **建议**：若 `bci-decoder/` 确为团队（或团队借助 AI）产出，选 A 并同步修正文档；若确为外部示例，选 B。

### 5.2 其它事实性不一致（均可直接核对）

| # | 文档说法 | 仓库事实（2026-10-15 核实） | 建议 |
|---|---|---|---|
| 1 | 《在线解码模块设计说明》7 节："模型训练产物落盘 ⏳ 未开始（`artifacts/` 写入被拒）" | `bci-decoder/artifacts/demo_lda.joblib` **已存在** | 该行已过期，需更新 |
| 2 | 《MVP 规格说明书》8 节："Python 3.10+ ⏳ 待确认" | venv 实际为 **Python 3.14.7** | 统一版本口径（`requirements.txt` 也应声明） |
| 3 | 《项目章程》5.2："Git 首次提交在 10/13 完成" | `D:\校企合作项目\.git` **不存在**，当前不是 Git 仓库 | 尽快 `git init` 并首次提交 |
| 4 | 《MVP 规格说明书》10.2/10.3：《`docs/evidence/W7_1013/` 目录建立》 | `docs/evidence/` **不存在** | 建目录结构，否则评审证据无处归档 |
| 5 | 各文档附录的命令块用 ```bash``` + `&&` | 团队实际在 **Windows PowerShell 5.1** 下执行，`&&` 不可用 | 统一为 PowerShell 写法（`;` 或分步） |
| 6 | 依赖：`websockets`（F5 必须） | venv 内**未安装**（与文档"从未装成功"一致） | 第 1 周优先验证，备好降级方案 |

> **处置结果（2026-10-15 复核）**
> - ① 已更正：`artifacts/demo_lda.joblib` 已存在，该行改为 ✅ 已完成。
> - ② 已统一：Python 口径写为 **3.14.7**，并在 `bci-decoder/requirements.txt` 顶部声明 3.10+ 下限。
> - ③ 已更正：《项目章程》§5.2 的 Git 声明改为"**尚未完成**"（**已于同日获用户授权执行**）。
> - ③′ **已解决（2026-10-15 晚）**：用户授权后完成 `git init` + 首次提交 **`7ce8d08`**（89 文件 / 12,317 行）并推送至 `origin/main`；远端原有 `4ea612c` **保留未覆盖**（快进推送）。`项目章程` §5.2、里程碑表 ① 行、检查清单「建 Git 仓库」三处已同步改为「已完成」。
> - ④ 已完成：`docs/evidence/W7_1013/` **已建立**（含归档说明 README）。
> - ⑤ 已更正：文档围栏由 ```bash``` 改为 ```powershell```；实测**全文并不存在 `&&`**，故本条原表述（"用了 `&&`"）本身也不准确。
> - ⑥ 仍待办：`websockets` **未安装**，登记为第 1 周必验项（降级方案见 `MVP规格说明书` §11.2）。

### 5.3 目录噪音（影响 AI 助手判断）

- 仓库根散落：`tools/`（`md2docx.py`、`intro2.pdf`、`questions.pdf`、`questions2.pdf`）、
  `bci-decoder/_md2docx.py`、根目录 `.pytest_cache/`、一张 `校企合作项目详细要求.jpg`。
- 这些**不是交付物**，却会被 AI 助手和评审一并扫到。
- **建议**：把非交付物集中到 `.tools/` 或 `docs/_assets/`，并在 `.gitignore` 中排除 `.pytest_cache/`、`.venv/`、`artifacts/*.joblib`。

> **处置结果（2026-10-15 已执行）**
> - `tools/` → **`.tools/`**（整目录搬移，层级不变；`md2docx.py` 依赖的 `Path(__file__).parent.parent / "docs"` 相对定位**不受影响**）。
> - `bci-decoder/_md2docx.py` → **`.tools/_md2docx_from_bci-decoder.py`**；它与 `tools/md2docx.py` **内容不同**（13,366 B vs 14,821 B），两份都保留、不合并、不删除。
> - `校企合作项目详细要求.jpg` → **`docs/_assets/校企合作项目详细要求.jpg`**（需求来源留档）。
> - 仓库根新增 **`.gitignore`**：排除 `.venv/`、`__pycache__/`、`*.pyc`、`.pytest_cache/`、`artifacts/`、`data/`、`*.joblib`、`*.npy`、`*.onnx`、`*.jsonl`、`.deepworks/`、`.opencode-router/`、`uploads/`、`.tools/*.pdf` 等。
> - **校验**：搬移前后逐文件 **SHA256 比对，11/11 一致，无损坏**。
> - **未动**（需人工确认后才处理）：`.pytest_cache/` 缓存目录本体（可再生）、`outputs/`（本会话产物目录，另有用途）、`uploads/`（会话上传物，已加入 `.gitignore` 而非删除）。

---

## 6. 仍未满足的工作流前置项（非文档类）

- [x] **Git 仓库已初始化并推送**（2026-10-15）—— 工作流与《章程》都要求可追溯的提交记录。仓库：GitHub `Bryanhw/motion-imagination-decode-module`（公开）；提交 `7ce8d08` 已推送，`main` 与 `origin/main` 同步。
- [x] **`docs/evidence/` 已建立**（2026-10-15）—— 见 `docs/evidence/W7_1013/README.md`；六个里程碑的证据统一归档在此。
- [ ] **`vibe.project.json` 未创建** —— Step 2/3 文档已按 `PRD-*-MVP.md` / `TechDesign-*-MVP.md` 命名，
      工作流 CLI 无需清单也能自动发现；若要跑 `doctor`，让它自动生成即可（不要手写，避免 `tools` 取值不合法）。

---

## 7. 本次**没有**做（明确边界）

- ❌ **未执行 Step 5「Build」**（未写/改任何业务代码）。按你的要求，本次只做 Start a project 的文档与 agent 配置。
- ❌ **未修改任何现有文档**（`MVP规格说明书.md` 等保持冻结原样），只新增文件。
- ❌ **未安装任何依赖**（`websockets` / `mne` / `moabb` / `pyriemann` / `pylsl` 仍未安装）。
- ~~❌ **未创建 Git 仓库**（未初始化，避免在你未确认时产生提交历史）。~~ → **该条已过期（2026-10-15 晚）**：用户明确授权后已 `git init`、完成首次提交并推送（`7ce8d08` → `origin/main`）。本条保留为「当时未做」的历史记录。

---

## 8. 下一步建议

1. **先解决 §5.1 的归属口径**——它决定后续所有进度标记是否可信。
2. 用 §5.2 的六条做一次"文档事实校准"（逐条改一行即可）。
3. 按 `AGENTS.md` + `MEMORY.md` 的方式接手开发，每个里程碑结束时只更新 `MEMORY.md` 的"当前状态"段。
4. 想跑工作流 CLI 时：在项目根执行 `npx vibeworkflow`，让它生成 `vibe.project.json` 并跑 `doctor`。

---

*本文件为流程评估产出，不改变任何现有文档效力；范围与验收口径仍以《MVP 规格说明书》为准。*
