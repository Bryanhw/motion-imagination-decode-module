# Deep Research Request · BCI-Decoder

> **本文件是 Part 1（Deep Research Prompt Builder）的产出物：一份"研究请求"，不是研究结果。**
> 生成日期：2026-10-15　|　目标读者技术等级：**A（零基础 / vibe-coder）**
> 使用方式：把本文件**完整**交给一个具备联网检索能力的研究工具（或让 AI 助手联网执行），
> 它会产出一份**独立**的发现文件 `research-BCI-Decoder.md`（本项目的最终归档位置：`docs/research-BCI-Decoder.md`）。
>
> ✅ **状态更新（2026-10-15，请求方归档后补记）**：本请求**已执行完毕**。
> 产出的 findings 已与初版 `docs/research-BCI-Decoder.md` **合并为唯一副本** `docs/research-BCI-Decoder.md`
> （研究状态：**Partial research**）。本请求文件与 findings 分开保存，两者同处 `docs/`。

---

## Deep Research Request: BCI-Decoder

<context>
我正在为一个**校企合作项目**（翔宇医疗 × 某高校智能医学工程专业学生团队）准备研究材料。
我是团队中**非技术背景**的成员，需要**最容易懂、能直接照着做**的结论，而不是论文式推导。

**项目一句话**：把脑电（EEG）中的"运动想象意图"实时解码成**可被游戏直接调用的 JSON 消息流**。

**已经确定的事实（不需要重新研究，可直接采信）**：

- 交付物是一条在线解码**模块**（一个黑盒），不是算法论文，也不是游戏画面。
- 输入：多通道 EEG 数据块，形状 `(n_channels, n_samples)`，单位 µV，**250 Hz、8 通道**，
  通道顺序固定为 `C3, Cz, C4, CP3, CP4, P3, P4, Oz`（**顺序即语义**，重排会稳定地得到相反结果）。
- 输出：一行一个 JSON，字段已**冻结**：`t_data / t_wall / label / label_id / confidence / probs /
  state / compute_ms / window_seconds`；`label ∈ {left, right, idle}`；`label_id == -1` 当且仅当 `label == "idle"`。
- 类别固定 **2 类（左手 / 右手）+ `idle`**；**滑窗 2.0 s、步长 0.5 s**；单次计算耗时 p95 必须 **< 50 ms**；
  端到端响应目标 **≤ 3 s**。
- 运行环境：**Windows 普通笔记本（无独立显卡）**，Python；**全部依赖必须开源免费**。
- 团队 4 名**大一**学生；周期 10 周（**2026-10-13 → 2026-12-15**），**MVP 硬节点 10/27 不可延**。
- 产品内**不使用大模型**；AI 只用于辅助团队写代码、写测试、写文档。

**明确不在本次研究范围（请不要花篇幅）**：

- 医疗诊断、临床合规、采集硬件选型
- 深度学习模型（EEGNet 等）与 GPU 方案
- 商业化、融资、定价策略（这是校企合作项目，不对外收费）
- 4 类运动想象
</context>

<instructions>

### 需要回答的关键问题（按重要性排序）

**1. 延迟为什么是瓶颈，而且瓶颈在哪里？**（本项目最核心的问题）

- 端到端响应时间怎么拆成"**窗口累积**"和"**单次计算**"两部分？各自大概是什么量级、占比多少？
- 为什么在 2.0 s 滑窗下，把分类器从 LDA 换成深度网络、或者上 GPU，对**端到端延迟几乎没有帮助**？
- 行业里缩短端到端延迟有哪些通行做法？每种做法的**代价**是什么（准确率、画面抖动、用户耐心）？
- 有可复现的公开案例、实测数据或官方文档支持上面的结论吗？（请给出处）

**2. 同类方案到底做到了哪一步？**

- `mne-lsl`、`mne-realtime`、`EEG-ExPy`、`timeflux`、`brainflow`、`LSL4Unity` 各自解决什么问题？**不解决**什么问题？
- "把解码结果封装成**游戏可直接调用的稳定黑盒模块**"这一层，为什么这些框架没有直接提供？

**3. 使用者对现有方案的抱怨是什么？**

- 在 GitHub Issues、技术论坛、Reddit 等公开渠道，实时 BCI 开发最常被吐槽的痛点有哪些？
- 哪些痛点与本项目直接相关（延迟、输出抖动、文档质量、上手成本、Windows 支持、安装依赖）？
- 请把"官方说法"和"用户吐槽"分开标注。

**4. 零基础团队的最小可行做法是什么？**

- 做一条"在线解码链路"，**第一批必须先做对**的事情有哪些（因果滤波、通道顺序、状态机、安全降级）？
- 每一件事**做错会出现什么症状**？（例如"离线能跑、在线失效"这类可观察现象）
- 有没有面向初学者的分步教程、示例仓库或课程？（优先给能直接跑起来的）

**5. 零基础在 Windows 上该用什么工具链？**

- Python 环境、代码编辑器、依赖安装、版本控制，各自有哪些**免费且对新手友好**的选择？
- 常见新手陷阱有哪些？（PowerShell 与 cmd 的差异、虚拟环境、中文编码、代理与镜像源等）

**6. 游戏端怎么对接最简单？**

- **WebSocket** 与 **LSL** 两条路线，对"两周内先跑通"分别意味着多大工作量？
- 如果游戏端选 **Unity**，需要哪些现成组件？如果选 **Python 自研**，又需要什么？
- 两条路线各自的失败模式与兜底方案是什么？

**7. 零基础团队可以用哪些 AI 工具加速开发？**

- 辅助**写代码 / 写测试 / 写文档**的免费或低成本 AI 工具，分别适合什么任务？
- 使用 AI 辅助开发时有哪些**数据边界**与**代码审查**上的注意事项？
  （例如：不要把企业未公开的设备资料、真实受试者数据贴进对话）

**8. 如果目标达不成，有哪些降级路线？**

- 常见失败模式（依赖装不上、游戏与算法不同步、现场演示失败、合法数据集下载不了）
  分别有什么**现成的兜底方案**？

### 研究重点（请把主要篇幅给这一条）

**在线解码链路与延迟**：端到端延迟的构成与瓶颈定位、可用与不可用的优化手段及其代价，
以及"**先定游戏节奏 → 再倒推窗口长度 → 最后在窗口内优化准确率**"这一设计顺序有没有公开依据。

其余方向（游戏对接、工具链、降级方案）作为**支撑材料**即可，不必展开成独立长章节。

### 必须交付的成果

1. **同类方案对照表** —— 功能、语言、上手难度、许可证、维护活跃度、官方链接、访问日期
2. **零基础技术栈推荐** —— Windows + 全免费，附"为什么选它"与替代方案
3. **功能优先级清单** —— 必做 vs 可延后，并说明判断依据
4. **开发路线图** —— 含里程碑切分与 AI 辅助开发策略
5. **成本拆分** —— 本项目预期为 ￥0，请**逐项核实**是否真的全部免费（含许可证条款细节）
6. **延迟专题结论** —— 拆解公式 + 量级 + 公开来源 + 与"换模型 / 上 GPU 无用"这一判断是否一致
7. **AI 适配判断** —— 本项目产品内是否需要 AI（预期：不需要），以及 AI 辅助开发的可用工具
8. **AI 安全与证据**（只写涉及 AI 的部分）—— 数据边界、供应商数据留存与训练设置（需核实）、
   评测方式、运行记录（遥测）、人工确认环节
9. **风险与降级清单** —— 每个风险配一个**可执行**的兜底动作

</instructions>

<output_format>

- 用**简体中文**、**大白话**写；专业名词第一次出现时用一句话解释；假设读者**没有编程经验**
- 每条重要结论都要给出**来源 URL 与访问日期**；打不开的来源要如实说明
- 对比一律用 Markdown 表格
- 明确区分三类信息：**官方文档的事实** / **社区经验（可能片面）** / **推测**
- 遇到不同来源互相矛盾，要**明确指出**，不要悄悄选一个
- 每条主要推荐都要写清"**优点 / 缺点 / 什么情况下不该选它**"
- **不要编造**引用、访问日期、当前价格或研究结果；查不到就写"未找到可靠来源"
- 产出**独立**的发现文件 `research-BCI-Decoder.md`（本项目最终位置：`docs/research-BCI-Decoder.md`），
  与这份研究请求**分开保存**
- 发现文件开头**必须**先给出研究状态，三选一并如实选择：
  **Research status: Researched with sources / Partial research / Not researched — unverified hypotheses**
- 如果**无法联网检索**，请明确说明，只给出**标注清楚**的假设与待答问题，
  并记录哪些决策仍然需要"带来源的研究"才能定
- 发现文件结尾**必须**附上下方**已填写**的 Handoff Context，供下一步（Part 2 生成 PRD）在**全新对话**中使用；
  **用户给定的约束必须原样保留**，并区分"已确认的决定"与"研究建议"
- 保存发现文件之后，在文档之外告诉用户：
  "Save research-BCI-Decoder.md. Next, paste the complete part2-prd-mvp.md prompt into a chat and attach these findings. You may use a new chat; no earlier conversation is required."

### Handoff Context（发现文件结尾必须包含；已知项已预填，未确定项请填写）

```text
## Handoff Context
<!-- Machine-readable summary for the next workflow step. Do not delete; the next prompt in the workflow reads this block. -->
- Stage: research
- App name: BCI-Decoder
- User level: A  (A = vibe coder, B = developer, C = in-between)
  注：请求方按零基础（A）口径提出；团队实际情况为大一学生、边学边做（既有 PRD 记为 C）。请保持本字段为 A，并在正文中说明该差异。
- Target platform: desktop  (Windows 普通笔记本，无独立显卡；交付物为 Python 模块，游戏端技术栈待定)
- Budget: 全免费优先（￥0，全部依赖须开源）
- Timeline: 10 周（2026-10-13 → 2026-12-15）；MVP 硬节点 10/27，不可延
- AI in product scope: no  (产品内不含任何 LLM / 深度学习；AI 仅用于辅助开发)
- Research status: [填写：Researched with sources / Partial research / Not researched — unverified hypotheses，并说明局限]
- Constraints: 类别 2 类（左手/右手）+ idle；滑窗 2.0 s、步长 0.5 s；250 Hz / 8 通道；通道顺序 C3,Cz,C4,CP3,CP4,P3,P4,Oz 不可变更；单次计算耗时 p95 < 50 ms；未训练或不可信时恒输出 idle；MVP 阶段不对外报告任何准确率
- Decisions: 只做在线解码模块（游戏画面归游戏端）；特征用频带功率(16 维) + LDA；伪迹只标记不丢弃、超阈值降级为 idle；输出多通道 console + jsonl + websocket；接口契约自 2026-10-13 冻结
- Open questions: bci-decoder/ 归属 ✅ 已拍板为团队成果（2026-10-15）；企业设备型号 / 通道顺序 / LSL 流名称待书面确认；游戏端用 Unity 还是自研 Python；websockets 依赖能否安装并跑通；真实评测协议（数据集与指标口径）
- Source files: docs/research-request-BCI-Decoder.md → docs/research-BCI-Decoder.md
```

</output_format>

---

## 附：如何使用本请求（此段不属于研究请求正文）

1. **保存**本文件为 `research-request-BCI-Decoder.md`（本项目归档位置：`docs/research-request-BCI-Decoder.md`）。
2. **执行**：打开带联网能力的 AI 工具，确认已开启联网/深度研究，粘贴上方**完整正文**。
3. **核对结果**：检查它的研究状态标注、来源链接与访问日期、以及仍未解决的问题。
4. **保存发现**：另存为 `research-BCI-Decoder.md`（本项目归档位置：`docs/research-BCI-Decoder.md`），保留结尾的 Handoff Context。
5. **进入下一步**：用 `part2-prd-mvp.md`，附上发现文件（不是本请求文件）。
