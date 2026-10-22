# Research · BCI-Decoder（在线解码链路与延迟专题）

> **合并版 findings**（2026-10-15 由两份 findings 合并而成，已去重并保留双方独有内容）
>
> - **本文件是本 findings 的唯一副本**，位于文档管线位置 `docs/`，与 `MVP_PRD.md`、`TechDesign-BCI-Decoder-MVP.md` 并列。
> - 原交付副本 `outputs/research-BCI-Decoder.md` 已于 2026-10-15 按用户要求**删除**（两份相同内容重复维护会产生分歧）；**本文件即最终版**。
> - 被合并的两份来源：`docs/research-BCI-Decoder.md`（初版）+ `outputs/research-BCI-Decoder.md`（联网检索版，**该副本已删除**）。
> - **口径：A（零基础 / vibe coder）**——全文按零基础可执行的标准写。
>
> **执行方式**：联网检索（官方文档站、GitHub 仓库与 API）。
> **全部来源的访问日期**：**2026-10-15**（另有少数条目沿用团队先前的核实记录，会逐处标明）。

---

**Research status: Partial research**

判定理由（如实说明局限）：

| 项 | 状态 |
|---|---|
| 同类框架的定位、许可证、活跃度 | ✅ 已核实（本轮实际抓取官方仓库/文档） |
| 在线必须用因果滤波 | ✅ 已核实（SciPy / MNE-LSL 官方文档原文） |
| 延迟由"窗口累积 + 采集间隔 + 计算"构成 | ✅ 已核实（MNE-LSL 官方文档），但**官方未给出显式公式**，`T_response` 分解式属本项目归纳 |
| "换模型 / 上 GPU 对端到端延迟帮助有限" | ❌ **未找到公开依据**——本轮最大缺口（见 §4.5） |
| 零基础工具链与许可证 | ⚠️ 部分核实（个别条款未读到，见 §13） |
| 价格与免费额度 | ⚠️ 极易过时，以官方当前页面为准 |
| 深度学习工具箱、商业同类、传统平台 | ⚠️ 沿用团队既有核实记录，**本轮未复核** |
| 用户抱怨 / 社区口碑 | ❌ 未取得系统性证据 |

---

## 0. 怎么读这份文件（标注约定）

- `[官方]` = 官方文档 / 官方仓库页面原文（本轮实际抓取）
- `[项目内]` = 来自本工作区自己文档与代码的事实。**不是公开来源，不得对外引用为行业结论**
- `[既有核实·本轮未复核]` = 团队先前经 GitHub API / 官方站点核对过存在性，**本轮未再次复核**，采用前请自行打开页面确认
- `[社区]` = 社区描述
- `[推断]` = 基于上述事实的合理推断，**不是**引用
- `[未核实]` = 没查到，或页面打不开

> **两条红线（贯穿全文）**
> 1. 本文件**不含任何算法准确率数字**，也不替代真实数据集实验。项目 MVP 阶段**不对外报告准确率**。
> 2. `mock` / `synth` 数据**只用于工程自检**（交叉验证 100% 是必然结果），**绝不可**用于评估算法性能或对外报成绩。

---

## 1. 一句话结论

> **在线解码的延迟几乎全部花在"等数据攒够一个窗口"，而不是花在算法计算上。**
> 因此提速的正道是**先定游戏节奏 → 倒推窗口长度 → 在窗口内优化准确率**，
> 而不是换更复杂的模型。**前半段有 MNE-LSL 官方文档支持；"换模型无用"这一步本轮未找到公开依据，属工程推断。**
>
> 而且——模块的"产品"就是**一段 JSON 消息流**（`label` / `confidence` / `probs` / `t_data` …）。
> **衡量成败的唯一标准是：能不能稳定驱动游戏。** 这句话决定所有取舍。

```
[EEG 设备/回放] ──LSL/文件──▶ [BCI-Decoder] ──WebSocket/JSONL──▶ [脑控游戏]
                                 滤波→特征→分类→稳定化
```

---

## 2. 逐条回答研究请求的关键问题

### 2.1 延迟为什么是瓶颈？瓶颈在哪里？

MNE-LSL 官方文档给出三个可核实的机制（本轮最有价值的证据）：

**① 数据是按"块"周期推送的，攒块本身就有等待** `[官方]`

> "data is published at regular intervals. The interval duration depends on the sampling rate and on the number of samples pushed at once, defined by the `chunk_size` argument"

官方给出关系：`interval = chunk_size / sfreq`，文档中 `chunk_size` 默认 10。
— 来源：https://mne.tools/mne-lsl/stable/generated/tutorials/00_introduction.html

**② 取数还有一个"采集间隔"参数** `[官方]`

`StreamLSL.connect(acquisition_delay=0.001, ...)` —— "Delay in seconds between 2 acquisition during which chunks of data are pulled from the StreamInlet"（默认 0.001 s）。
— 来源：https://mne.tools/mne-lsl/stable/generated/api/mne_lsl.stream.StreamLSL.html

**③ 计算会直接推迟采集** `[官方]`

> "Callback(s) are called in the same thread as the acquisition. Thus, they should be fast and non-blocking. **If the callback takes too long, the acquisition will be delayed.**"

— 同上来源。含义：计算不是"免费"的，算得慢会拖累取数；但对本项目而言，p95 < 50 ms 相对于 2.0 s 窗口仍是小量。

**④ 官方处理链顺序** `[官方]`：参考通道 → 重参考 → 滤波/陷波 → 自定义回调。
— 来源：https://mne.tools/mne-lsl/stable/resources/implementations.html

> ⚠️ **未核实**：官方文档中**没有**把端到端延迟写成 "数据累积时间 + 计算时间" 的显式公式。上面的分解式（§4.1）是从原文**归纳**所得，不是某句原话。

### 2.2 在线为什么要用因果滤波？`[官方]` 已核实

| 函数 | 官方说法 | 能否在线用 |
|---|---|---|
| `scipy.signal.filtfilt` | "applies a linear digital filter twice, once forward and once backwards. **The combined filter has zero phase**" | ❌ 零相位，用到"未来"样本 |
| `scipy.signal.sosfiltfilt` | "A forward-backward digital filter using cascaded second-order sections." | ❌ 同样是前向-后向 |
| `scipy.signal.sosfilt` | 单次前向 IIR，可传入 `zi` 作为滤波器初始状态（`zi=None` 时按初始静止处理） | ✅ 因果，`zi` 正是**跨 chunk 保持状态**的机制 |
| MNE-LSL `StreamLSL.filter` / `notch_filter` | 官方描述为 "Filter the stream with an **IIR causal filter**" / "IIR **causal** notch filter" | ✅ 官方在线实现即为因果 |

来源（均 2026-10-15 访问）：
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.filtfilt.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfilt.html
- https://mne.tools/mne-lsl/stable/generated/api/mne_lsl.stream.StreamLSL.html

**后果**：若在线套用零相位 `filtfilt`，块边界会跳变、特征剧烈抖动，"离线能跑"会变成"在线失效"。

> ✅ **结论**：项目"在线禁用 `filtfilt`、必须 `sosfilt` + 跨块保存 `zi`"的做法，**与官方文档完全一致**，不是团队自创的保守做法。（此项由初版标注的 `[未核实，属通用工程常识]` **升级为 `[官方]` 已核实**。）

### 2.3 使用者对现有方案的抱怨是什么？

`[未核实]` 本轮**没有**取得 GitHub Issues / 论坛 / Reddit 的系统性证据（检索类站点本轮多不可用，见 §13）。因此**不给出任何"用户普遍抱怨 X"的结论**。

可核实的间接信号 `[官方]`：
- `mne-realtime` 的 README 明确写着自家已被取代（"This project is discontinued in favor of MNE-LSL"）——说明这类工具迭代快、旧方案会被弃用。
- MNE-LSL 官方示例的产物是**一张准确率曲线图**，不是可被程序消费的消息（见 §3.7）。

> 待办：若需要"用户抱怨"这一节，应改用可访问的 GitHub Issues 抓取或人工浏览。

### 2.4 零基础团队的最小可行做法（第一批必须做对的事）

`[项目内] + [官方]` 交叉后，第一批必须做对的四件事：

| 优先级 | 必须做对的事 | 做错的可观察症状 | 依据 |
|---|---|---|---|
| 1 | **在线用因果滤波（`sosfilt` + 跨块 `zi`）** | 离线跑得好、在线特征剧烈抖动 / 块边界跳变 | `[官方]` SciPy 与 MNE-LSL 文档 |
| 2 | **锁死通道顺序 `C3,Cz,C4,CP3,CP4,P3,P4,Oz`** | 结果**稳定地相反**（左右颠倒），极难排查 | `[项目内]` 项目红线 |
| 3 | **未训练/不可信时恒输出 `idle`** | 给游戏发送随机左右指令，体验与安全双输 | `[项目内]` 项目红线，仓库内参考实现已验证 |
| 4 | **先跑通再优化**：用回放（replay）验证链路，再接真设备 | 直接上真设备时，分不清是算法问题还是连接问题 | `[官方]` MNE-LSL 提供 `PlayerLSL` 回放示例可参照 |

关于第 4 点，MNE-LSL 官方提供了"用 `PlayerLSL` 把离线文件当实时流播放"的**官方示例** `[官方]`：
`PlayerLSL(raw, chunk_size=200, ...)` + `player.start()`，即可在没有硬件的情况下产生一条仿真 LSL 流。
— 来源：https://mne.tools/mne-lsl/stable/generated/examples/40_decode.html

> 这与本项目 `mock` / `replay` 双数据源的设计思路**一致**，且说明"回放验证"是行业通行做法。

### 2.5 零基础在 Windows 上该用什么工具链？

详见 §5。一句话：**官方 CPython + 内置 `venv` + VS Code**；`uv` 作为进阶；**conda 需先确认合规**。

### 2.6 游戏端怎么对接最简单？

详见 §6。一句话：**LSL 有现成 Unity 集成但生态偏旧（Unity 插件主分支最后提交 2023-07-31）；WebSocket 更轻、协议全靠自研**。两条路都可行，取决于游戏端最终是不是 Unity。

### 2.7 零基础团队可以用哪些 AI 工具加速开发？

详见 §10。一句话：预算 ￥0 时，**GitHub Copilot Free 是唯一有官方明确免费额度的选项**；Cline / Continue / OpenCode 开源免费但**模型调用成本需另算**。

### 2.8 如果目标达不成，有哪些降级路线？

见 §11。

---

## 3. 同类方案对照表

### 3.1 主表（本轮实际抓取，访问日期 2026-10-15）

| 项目 | 定位 | 许可证 | 活跃度 | 它解决什么 | 它**没**解决什么 | 与本项目关系 | 链接 |
|---|---|---|---|---|---|---|---|
| **mne-lsl** | 基于 LSL 的实时脑信号流式框架 | BSD-3-Clause | release 1.14.0（2026-07-13）；JOSS 论文 2025 | 实时取流、实时分段（`EpochsStream`）、对接 MNE/sklearn | 无游戏消息契约、无 idle/置信度门控 | **最接近的积木**，契约层仍需自建 | https://github.com/mne-tools/mne-lsl |
| **mne-realtime** | MNE 实时分析（FieldTrip / LSL client） | BSD-3-Clause | **已停止维护**，release 0.3.0（2023-10-18） | 历史上提供实时取数 + `RtEpochs` | 已被 MNE-LSL 取代 | ❌ 不建议采用 | https://github.com/mne-tools/mne-realtime |
| **EEG-ExPy** | 经典 EEG 实验的 Python 实现 | BSD-3-Clause | 无正式 release；`pushed_at` 2026-10-14 | 实验设计、刺激呈现、信号处理与分析 | 非实时意图解码服务，无游戏接口 | **架构参考范本** | https://github.com/NeuroTechX/EEG-ExPy |
| **Timeflux** | 实时生物信号处理框架 | MIT | release v0.17.2（2024-12-04） | 可配置实时管线、闭环生物反馈 | 输出契约需自建 | 通用管线候选 | https://github.com/timeflux/timeflux |
| **BrainFlow** | 生物传感器统一采集 SDK | MIT | release 5.23.0（2026-09-26） | 统一采集 API + 滤波/去噪 + 多语言绑定 | 不做 MI 解码，无消息契约 | **设备抽象参考** | https://github.com/brainflow-dev/brainflow |
| **liblsl** | LSL 核心 C++ 传输库 | MIT（含 Boost 许可代码） | release v1.17.7（2026-04-22） | 局域网内时间同步的多模态流传输 | 只定义通用流元数据，不定义决策消息 | **传输层底座** | https://github.com/sccn/liblsl |
| **MOABB** | BCI 算法离线基准评测 | BSD-3-Clause | release v1.7.2（2026-09-14） | 公开数据集封装 + 算法基准/复现 | 仅离线，非实时 | **里程碑 ③ 评测口径参考** | https://github.com/NeuroTechX/moabb |
| **pyRiemann** | SPD 矩阵黎曼几何机器学习库 | BSD-3-Clause | release v0.12（2026-07-01） | MI/ERP/SSVEP 分类（MDM、TangentSpace 等） | 不负责实时取流、缓冲、因果滤波、消息封装 | 里程碑 ④ 分类器候选 | https://github.com/pyRiemann/pyRiemann |
| **LSL4Unity** | LSL 的 Unity3D 集成包 | ⚠️ **来源冲突**：GitHub 仓库字段为 `Other (NOASSERTION)`；另一路检索读到 LICENSE 正文标注 MIT（© 2021 Markus Fleck）——**未定论** | master 最近提交 2023-07-31；`pushed_at` 2024-06-27 | Unity 端收发 LSL 流 | 不做 EEG 解码 | **游戏侧**接入参考 | https://github.com/labstreaminglayer/LSL4Unity |
| **awesome-bci** | BCI 资源清单（非框架） | **未声明**（`license: null`） | master 最近提交 2026-10-08 | 索引工具/数据集/教程/论文 | 无代码能力 | 索引用 | https://github.com/NeuroTechX/awesome-bci |

> ⚠️ **明确指出的冲突**：LSL4Unity 的许可证在两路检索里结论不同（`NOASSERTION` vs MIT）。**采用前必须自己打开仓库 `LICENSE` 正文确认。**

### 3.2 算法与基准工具箱（`[既有核实·本轮未复核]`）

以下条目来自团队先前的核实记录（GitHub API 核对过仓库存在性）。**本轮检索未复核**，采用前请自行打开页面确认，尤其注意许可证与维护状态。

**本期 MVP 不使用**（项目决策为"CSP + LDA"，深度学习留到后期）；列在此处是为了**里程碑 ④ 或对外汇报时的行业视野**，不是当前技术选型。

| 项目 | 用途 | 与本项目关系 |
|---|---|---|
| [`braindecode/braindecode`](https://github.com/braindecode/braindecode) | PyTorch EEG 深度学习工具箱 | 后期探索（M4 之后） |
| [`vlawhern/arl-eegmodels`](https://github.com/vlawhern/arl-eegmodels) | EEGNet 原论文实现 | 经典轻量 MI 网络，了解即可 |
| [`torcheeg/torcheeg`](https://github.com/torcheeg/torcheeg) | PyTorch EEG 工具箱 | 与 braindecode 同类 |
| [`Altaheri/EEG-ATCNet`](https://github.com/Altaheri/EEG-ATCNet) | 注意力 + 时序卷积 MI 模型 | 学术前沿参考 |
| [`ravikiran-mane/FBCNet`](https://github.com/ravikiran-mane/FBCNet) | 滤波器组 + 深度模型，**参数小** | 若将来要上轻量网络，优先看这个 |

> **纪律提醒** `[项目内]`：这些工具箱都**不解决**"实时取流 + 因果滤波 + 缓冲 + 消息契约"。
> 把 LDA 换成它们，恰是 §4.5 说**没有公开依据**的那件事——**先别做**。

### 3.3 游戏对接

| 项目 | 用途 | 状态 |
|---|---|---|
| [`labstreaminglayer/LSL4Unity`](https://github.com/labstreaminglayer/LSL4Unity) | Unity 接收 LSL 流的标准组件 | 本轮已核实（许可待确认，见 §3.1） |
| [`NeuroTechX/awesome-bci`](https://github.com/NeuroTechX/awesome-bci) | BCI 资源总目录 | 本轮已核实 |

### 3.4 ⛔ 已失效地址（不要引用）

> ❌ `bcmi-labs/BrainFlowsIntoVRChat` —— **地址已失效（404）**。
> 这条来自团队先前核实记录 `[既有核实·本轮未复核]`，列出来是为了**避免重复踩坑**：
> 对外汇报或写文档时不要引用它。

### 3.5 传统 BCI 平台（了解思想，不作依赖）`[未核实]`

BCI2000、OpenViBE（INRIA）、EEGLAB —— 均以图形化 / 配置化为主，
嵌入现代 Python 流水线不便，**建议只借鉴其模块划分思想**（采集 / 处理 / 反馈分层），不要引入为依赖。

### 3.6 商业与临床同类（仅作定位参考）`[未核实]`

- **消费级 EEG**：Emotiv、Neurable、BrainCo 等
- **科研/临床设备**：g.tec、Brain Products、g.Nautilus 等
- **合作方** 翔宇医疗自身的康复产品线

> ⚠️ 以上均为一般行业认知，**未在本轮核实**；对外汇报前请查官方资料并标注日期。
> 价值在于：说明本项目在"设备厂商已有产品线"之外的位置——**做的是软件解码模块，不是硬件**。

### 3.7 "这一层为什么没人提供"——有依据的回答

**官方事实** `[官方]`：上述框架的官方定位里，**没有任何一个**包含"把解码结果定义成面向游戏的消息契约"：

- liblsl = 传输与时间同步层（只定义通用流元数据）
- BrainFlow = 采集 + 通用信号处理
- mne-lsl = 流式 + 分段 + 接 MNE/sklearn
- pyRiemann = 分类算法库
- MOABB = **离线**基准
- EEG-ExPy = 实验设计与分析
- Timeflux = 实时管线

**官方事实** `[官方]`：连最接近的 MNE-LSL 实时解码示例，产物也是 `ax.plot(...)` 画的 "Classification score 曲线"，**不是结构化消息**，没有 idle、置信度阈值、字段冻结等语义。
— 来源：https://mne.tools/mne-lsl/stable/generated/examples/40_decode.html

**推断** `[推断]`：`idle` 兜底、`label_id == -1` 与 idle 绑定、字段不得增删——这些都是**应用层契约**，取决于具体游戏节奏（滑窗 2.0 s / 步长 0.5 s）与风控策略。通用框架为了可复用，通常把这些留给使用方。

> **诚实说明**：**没有任何一份被访问的文档直接写"我们不提供游戏黑盒模块"**。前两条是官方事实，第三条是推断。
> 结论：这些框架提供"取流—同步—分段—分类"的**积木**，"游戏可直接调用的稳定黑盒模块"是**应用层契约 + 工程封装**的组合，需要自己写。

---

## 4. 延迟专题（本次研究重点）

### 4.1 延迟到底花在哪

```
T_response ≈ T_accumulate + T_compute
             └─ 滑窗长度 ─┘   └─ 单次计算 ─┘
```

| 项 | 量级 | 占比 | 依据 |
|---|---|---|---|
| `T_compute` p95 | 数毫秒级（参考实现测到 2.1 ms / 4.7 ms） | ≈ 0.1%–0.25% | `[项目内]` 仓库内参考实现 + 合成数据 |
| `T_accumulate` | 2000 ms（2.0 s 滑窗） | ≈ **99.8%**（构造估算） | `[项目内]` 冻结参数 |
| 分块推送间隔 | `chunk_size / sfreq`，示例 200/1024 Hz ≈ 0.195 s | 秒级以下 | `[官方]` MNE-LSL 教程 00 |
| 采集间隔 `acquisition_delay` | 官方默认 0.001 s | 毫秒级 | `[官方]` StreamLSL API |
| 单次计算红线 | p95 **< 50 ms** | — | `[项目内]` 项目验收口径 |

> ⚠️ **数字使用纪律**：2.1 ms / 4.7 ms 与 99.8% 这些数字来自**仓库内参考实现与合成数据**，
> **只能说明量级**，不是算法性能指标，**不得对外报为团队成果**。团队须用自己的代码实测——
> **团队实测已归档**（2026-10-21）：起步延迟 ≈2.1 s（`A9_启动计时`）、单次计算 p95≈0.955 ms（`A4_benchmark`，本机），
> 均在 `docs/evidence/W9_1027/01_延迟/`；对外讲延迟须分「起步/稳态」两个数，勿只甩“99.8%”。

**可以确立的结构性结论** `[官方支持]`：端到端延迟里，**"等窗口"是秒级、"算一次"是毫秒级**，差 1–2 个数量级。
因此**优化重心应在窗口与游戏节奏的匹配，而不是算法复杂度**。

**官方给的设计顺序也支持这一点** `[官方]`：MNE-LSL 官方示例的取数方式本身就体现"按块处理 + 缓冲"：
`StreamLSL(bufsize=5, ...).connect(acquisition_delay=0.1)` + `EpochsStream(..., tmin=-0.2, tmax=0.5)` —— 即**先定窗口，再谈分类**。
— 来源：https://mne.tools/mne-lsl/stable/generated/examples/40_decode.html

> **正确顺序**：先定游戏节奏 → 倒推窗口长度 → 在窗口内优化准确率。

### 4.2 窗口长度与信息量的权衡（间接依据）

`[官方/第三方]` BCI Competition IV dataset 2a（对应 MOABB `BNCI2014_001`）的单试次时间轴：
- `t = 0 s`：出现注视十字 + 提示音
- `t = 2 s`：出现箭头提示，**持续 1.25 s**
- 受试者**持续想象直到 `t = 6 s`** 注视十字消失
- 该页同时标注 "4.0 s trials" / "4s task window per trial"

— 来源：https://moabb.neurotechx.com/docs/generated/moabb.datasets.BNCI2014_001.html

`[官方]` 数据集规格：2a 为 22 通道 EEG（+3 EOG）、**250 Hz**、4 类、9 名受试者。
— 来源：https://www.bbci.de/competition/iv/

`[官方]` BCI IV 数据集 1 明确包含 idle 期：*"evaluation data is continuous EEG which contains **also periods of idle state**"*。
— 同上。**这条对本项目"2 类 + idle"的设定是有力旁证。**

**用于推断** `[推断]`：标准 MI 范式给受试者的想象时长约 **4 s**，而本项目滑窗取 **2.0 s** ——
属于"比标准范式短一半"的激进选择，用延迟换信息量。**官方文档没有直接写"窗口越短信息越少"这句话**，上述权衡是从范式时长间接推断的。

### 4.3 2.0 s / 0.5 s 这组参数意味着什么

| 维度 | 含义 |
|---|---|
| 延迟（优点） | 比标准 4 s 范式快一半，游戏"跟手"感更好 |
| 信息量（代价） | 想象时长短一半，可区分性下降（§4.2 推断） |
| 输出频率 | 每 0.5 s 一次决策 → 每秒 2 条消息，游戏端按此设计动画/节奏 |
| 抗抖动 | 0.5 s 步长 + 稳定化三重机制，避免画面抽搐 |

> `[项目内]` 这组数字已冻结，**不得擅自改动**（会破坏游戏节奏与验收口径）。
> 若要改，走 `docs/MVP规格说明书.md` 第 9 节的变更流程。

### 4.4 无模型时必须安全降级为 `idle` `[项目内，仓库内可复现]`

未训练 / 模型缺失 / 置信度不足时，一律输出 `idle`（"不动"），**绝不给游戏发送随机左右指令**。
仓库内参考实现已验证该行为，且与会话中已验证的 `label_id == -1` 约定一致。

### 4.5 ⚠️ 未找到公开依据的一项（最重要的一条）

**"把 LDA 换成深度模型、或上 GPU，对端到端延迟几乎没有帮助"——本轮未找到公开依据。**

尝试过的检索路径均失败或无命中：DuckDuckGo（传输错误）、Bing（词典/无关结果）、Semantic Scholar API（429）、arXiv API（查询词被拆解）。
因此**本文件不把这一判断当作已证实结论**。

**可以对外说的、有依据的版本**是：

> *"在 2.0 s 窗口下，单次计算耗时 p95 < 50 ms，相对于 2.0 s 的窗口累积属于毫秒级；因此**在当前参数下**延迟瓶颈是窗口，不是计算。"*

（前半句 `[项目内]` 实测，后半句 `[推断]`）

> 项目对外口径应避免把"换模型无用"说成行业定论。**MVP 阶段不报任何准确率。**

---

## 5. 零基础技术栈推荐（Windows / 无独显 / ￥0）

| 用途 | 推荐 | 免费? | 许可证 | 为什么 | 什么时候别选它 |
|---|---|---|---|---|---|
| Python 本体 | **官方 CPython** | 是 | PSF License v2 | 官方主线、文档最全、教程最多 | 需要频繁切换多个 Python/依赖版本时略繁琐 |
| 虚拟环境 | **`venv`（标准库自带）** | 是 | 随 Python（PSF） | 随 Python 一起来，零额外安装 | 依赖极重、需要复现复杂科学计算环境时较慢 |
| 进阶环境管理 | `uv` | 是 | MIT | 装包快、一个工具管环境 | 团队还没搞懂 `venv` 就上 `uv`，出错更难自查 |
| 编辑器 | **VS Code + Python 扩展** | 是 | 源码仓库 MIT；⚠️ 官方发行版另有 Microsoft 产品许可，**条款未核实** | 图形界面、调试友好、对新手最直观 | — |
| 终端 | Windows PowerShell 5.1（系统自带） | 是 | 随系统 | 团队既有文档与命令均以它为基准 | 注意**不支持 `&&`**，用 `;` 或 `if ($?) { }` |
| 环境管理（谨慎） | Miniconda / Anaconda | 软件本身免费 | ⚠️ **Anaconda Repository 受 Anaconda Terms of Service 约束**，官方安装文档说明**可能需要付费商业许可**（个人、高校、员工 < 200 人的组织有例外，页面标注 as of 2024-09） | 科学计算包预装方便 | **学校/企业合规未确认前不要用** |

来源（2026-10-15 访问）：
- https://www.python.org/downloads/ ・ https://docs.python.org/3/using/windows.html
- https://docs.python.org/3/library/venv.html
- https://docs.astral.sh/uv/ ・ https://github.com/astral-sh/uv
- https://code.visualstudio.com/ ・ https://code.visualstudio.com/docs/python/python-tutorial
- https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html
- https://learn.microsoft.com/en-us/powershell/scripting/learn/ps101/01-getting-started

> `[未核实]` Anaconda 官方 TOS 原文未能访问（返回验证页/403）。
> **本项目已有环境事实** `[项目内]`：`bci-decoder/.venv` 为 Python 3.14.7，全局 `python` **没有 pytest** ——
> 必须用 `bci-decoder\.venv\Scripts\python.exe`。这与"`venv` 就够用"的结论一致。

---

## 6. 游戏端对接：WebSocket vs LSL

| 维度 | WebSocket（Python `websockets` 库） | LSL（Lab Streaming Layer） |
|---|---|---|
| 定位 | 通用双向消息协议库 | **统一采集测量时间序列**的系统，核心为 `liblsl` |
| 许可证 | BSD-3-Clause | liblsl 为 MIT（含 Boost 许可代码） |
| Unity 侧现成组件 | 无官方组件，需自己在 C# 侧实现客户端 | **LSL4Unity**（⚠️ 许可证来源冲突；主分支最后提交 2023-07-31） |
| 多语言/多源支持 | 自己定协议 | 官方提供 Python(pylsl)、C#、Java 等绑定，跨平台 |
| 对"两周内先跑通" | **更轻**：Python 端写起来快，但协议、时间戳、重连、丢包**全要自研** | 有现成路径，但要处理 LSL 服务发现、时钟同步等问题 |
| 失败模式 | 连接断开、消息乱序/丢包、时间戳全靠自定义 | 后台 LSL 服务/网络发现问题、时钟同步问题 |
| 与已冻结契约的关系 | 契约就是自定义 JSON，**天然匹配** | 需把 JSON 塞进 LSL 流，额外一层 |

来源（2026-10-15 访问）：
- https://labstreaminglayer.readthedocs.io/ ・ https://labstreaminglayer.readthedocs.io/info/intro.html
- https://github.com/labstreaminglayer/LSL4Unity
- https://websockets.readthedocs.io/en/stable/ ・ https://websockets.readthedocs.io/en/stable/project/license.html

`[推断]`：**先做"跑通"就选 WebSocket**（少一层依赖、Python 侧最省事，且项目契约本来就是自定义 JSON）；
**若游戏端最终确定是 Unity 且要与其它设备统一时间戳，再评估 LSL + LSL4Unity**。

> ⚠️ `[未核实]` LSL4Unity 支持哪些 Unity 版本、是否兼容当前 LTS —— 本轮未取到。
> 另注意：`https://labstreaminglayer.readthedocs.io/en/latest/` 返回 404，正确入口是根站点。

---

## 7. 功能优先级清单

依据研究请求确认的 Top3（F1 + F4 + F5）与项目冻结范围：

| 分层 | 内容 | 判断依据 |
|---|---|---|
| **必做（Top3）** | **F1 在线解码链路**（mock/replay 可切换） | 链路不通则一切无从谈起；`[官方]` 回放验证是通行做法 |
| | **F4 脑控弹球 Demo**（键盘可玩 → 解码可玩） | MVP 要证明"能演示"；游戏端可并行开工降低风险 |
| | **F5 WebSocket 打通**（游戏实际订阅并驱动画面） | 这是"闭环"的唯一证据；`[推断]` WebSocket 是两周内更省事的路 |
| **强烈建议同时保留** | F2 输出接口（console + jsonl）、F3 决策稳定化（EMA + 3 次投票 + 门限） | 两者是 F1/F5 的**地基**，且契约已冻结；去掉会导致验收项无法证明 |
| **本期不做** | 真实数据准确率基线、伪在线一致性验证、校准流程、LSL 真设备、黎曼、深度学习、4 类 | `[项目内]` 已排入里程碑 ③④ 或明确不做 |

> **提醒** `[项目内]`：PRD 的验收红线 R-2 / R-4 与 F2 / F3 直接绑定。
> 即"Top3"是**叙事重点**，不是"可以砍掉 F2 / F3"。

---

## 8. 开发路线图（含 AI 辅助开发策略）

`[推断]` 基于项目已有里程碑与本轮发现给出，**不是**研究结论：

| 阶段 | 时间 | 交付 | 本轮研究带来的具体动作 |
|---|---|---|---|
| 第 1 周 | 即刻–10/20 | `websockets` 能否装通**先验证**；弹球键盘版先跑起来 | `[官方]` 学 MNE-LSL 的 `PlayerLSL` 思路，用**回放**代替真设备验证链路 |
| 第 2 周 | 10/20–10/27 | F1–F5 打通 + `cli benchmark` 出数字 + 证据归档 | 用 `sosfilt` + `zi` 跨块保状态；用 `chunk_size/sfreq` 口径解释延迟分解 |
| 里程碑 ③ | 11/10 | `moabb` + BCI IV 2a 真实基线 | `[官方]` MOABB `BNCI2014_001`：250 Hz、4 s 任务窗、含 idle 段——**用它对齐评测口径** |
| 里程碑 ④ | 12/01 | 校准流程、黎曼（`pyRiemann`）、LSL、稳定性 | `[官方]` pyRiemann v0.12 是现成候选 |
| 里程碑 ⑥ | 12/15 | Docker 与交付说明 | — |

**AI 辅助开发策略** `[推断]`：AI 用于**写测试、写文档、解释报错**（低风险、可复核）；
**不用于**替代对**因果滤波 / 通道顺序 / 契约字段**的最终判断（这三处错了会稳定产生错误结果，且极难排查）。

---

## 9. 成本拆分（逐项核实）

| 项 | 费用 | 核实情况 |
|---|---|---|
| Python / `venv` / VS Code / PowerShell | ￥0 | ✅ 官方免费；⚠️ VS Code 发行版许可条款未核实 |
| numpy / scipy / scikit-learn / PyYAML / joblib / pytest | ￥0 | ✅ `[项目内]` 均已安装且为开源许可 |
| `websockets` | ￥0 | ✅ BSD-3-Clause |
| mne-lsl / MOABB / pyRiemann / BrainFlow / liblsl / Timeflux | ￥0 | ✅ BSD-3-Clause 或 MIT（见 §3.1） |
| LSL4Unity | ￥0（但许可待确认） | ⚠️ 许可证来源冲突（`NOASSERTION` vs MIT），采用前须读 LICENSE 正文 |
| AI 编码助手 | ￥0 起 | ⚠️ **GitHub Copilot Free：每月 2000 次 completions，$0**（Pro $10/月）——**以官方当前页面为准，访问日期 2026-10-15**；Cline / Continue / OpenCode 开源免费但**模型调用成本另算** |
| conda 生态 | **可能收费** | ⚠️ Anaconda 安装文档说明 Anaconda Repository 受 TOS 约束，可能需付费商业许可（个人/高校/小组织有例外，as of 2024-09） |

**结论**：本项目的工具链**可以做到真 ￥0**，前提是**不用 conda 生态**、**不引入付费云服务**。
与项目"部署零成本（N7）"要求一致。

来源（2026-10-15 访问）：https://github.com/features/copilot ・ https://github.com/cline/cline ・ https://github.com/continuedev/continue ・ https://opencode.ai/ ・ https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html

---

## 10. AI 适配判断与 AI 安全

### 10.1 产品内是否需要 AI —— **不需要**（与项目文档一致）

`[项目内]` 项目 PRD 第 7 节已声明：交付物是**确定性信号处理链路**（滤波 → CSP 特征 → LDA → 后处理），
MVP **不含任何深度学习 / 大模型组件**，不需要 GPU。

`[官方]` 支撑：主流实时框架（mne-lsl）的官方实时解码示例用的也是 **sklearn `Pipeline([Vectorizer, StandardScaler, LogisticRegression])`** ——
即**经典轻量模型足以做在线解码演示**，不需要大模型。
— 来源：https://mne.tools/mne-lsl/stable/generated/examples/40_decode.html

**结论**：本项目的"AI"是**经典机器学习**，不是 LLM。
因此研究请求里那套 LLM 检查清单（provider 选择、结构化输出、MCP/工具、提示注入、数据留存）**大部分不适用**。

### 10.2 AI 辅助开发：可用工具

| 工具 | 免费额度 | 许可证 | 形态 | 适合什么任务 |
|---|---|---|---|---|
| **GitHub Copilot** | **Free：$0，每月 2000 次 completions**；Pro $10/月 | 未核实（商业产品） | IDE 补全/对话 | 写代码、写测试、解释报错 |
| Cline | 未标注统一额度，需自备模型 Key | Apache-2.0 | VS Code 内 agent | 多文件改动（需会看 diff） |
| Continue | 同上 | Apache-2.0 | VS Code/JetBrains 插件 | 补全 + 对话 |
| OpenCode | 未核实具体条款 | MIT | 终端 agent | 命令行工作流 |

> ⚠️ 价格与额度**极易过时**：一律**以官方当前页面为准（访问日期 2026-10-15）**。

### 10.3 AI 使用时的数据边界（三条可执行建议）

1. **不要把企业未公开的设备资料**（型号、固件、引脚/通道定义）**贴进任何 AI 对话** ——
   那是翔宇医疗的资料，泄漏风险由团队承担。
2. **不要贴真实受试者数据**（EEG 记录、姓名、健康信息）。
   项目伦理尚未走完，这类数据本就不该存在本地。
3. **AI 生成的关键代码必须人工复核后再采纳**，尤其是**因果滤波、通道顺序、契约字段**三处 ——
   这三处出错会稳定地产生错误结果且极难排查。

---

## 11. 风险与降级清单

| 风险 | 可观察信号 | 兜底动作 |
|---|---|---|
| `websockets` 装不上 / 跑不通 | `pip install` 失败或运行即崩 | 第 1 周先验证；兜底用 **jsonl 文件轮询** 或本地 TCP |
| 游戏与算法不同步 | 画面延迟明显、指令滞后 | 游戏端**并行开工**，先做完整键盘玩法，再换解码输入 |
| 窗口长度与游戏节奏不匹配 | 游戏"不跟手" | 先定节奏再定窗口（§4.1 正确顺序） |
| 在线套用离线零相位滤波 | 在线表现暴跌、特征抖动 | 从第一天用因果滤波；`replay` 伪在线回放**必测** |
| 通道顺序与设备不一致 | **稳定输出相反结果**（最难排查） | 锁死 `ch_names`；接设备前**书面确认** |
| 只追准确率、忽视抖动 | 用户挫败、画面抽搐 | 稳定化三重机制：**EMA + 连续 N 次投票 + 置信度门限** |
| 用合成数据当成绩 | 学术诚信风险 | **红线：MVP 阶段不对外报任何准确率** |
| 只有合成数据、无法证明算法 | — | 真实数字留到里程碑 ③，用 `moabb` + BCI IV 2a |
| 真设备迟迟不到位 | 设备型号/伦理未确认 | 用 MNE-LSL `PlayerLSL` 式**回放**替代真设备做演示 |
| **脑机盲**（部分人群对运动想象不敏感，团队文档记为约 15%–30%） | 单人演示失败 | 准备退路：改"专注 / 放松"控制，或换试玩者。**这是范式问题不是算法问题** |
| 涉人数据无伦理审查 | 合规风险 | 采集真人前完成审查与知情同意 |
| 现场演示失败 | 演示机环境不干净 | 提前用演示机完整走一遍"3 分钟流程" |
| 数据集合规 | 无法下载 BCI IV 2a | `[未核实]` 本轮未核实数据集许可与获取方式——**里程碑 ③ 前必须单独确认** |

> ⚠️ "脑机盲 15%–30%" 这一比例 `[未核实·引自团队既有文档]`，本轮未找到权威出处。
> 但**结论本身（存在对 MI 不敏感的人群、演示要准备退路）是稳健的工程建议**，不能因为数字出处不明就忽略。

---

## 12. 与本工作区既有文档的一致 / 冲突点

| 项 | 既有文档说法 | 本次研究 | 判定 |
|---|---|---|---|
| 在线必须因果滤波 | 因果滤波 + 跨块保状态（初版标 `[未核实]`） | ✅ SciPy / MNE-LSL 官方文档一致 | **升级为 `[官方]` 已核实** |
| 延迟瓶颈在窗口不在算法 | 算法耗时占 ~0.2% | ⚠️ 结构一致，但"换模型无用"**无公开依据** | **结论保留，措辞需收敛（§4.5）** |
| 2 类 + idle | 冻结 | ✅ `[官方]` BCI IV 数据集 1 也含 idle 段 | **得到旁证** |
| 通道顺序 C3,Cz,C4,CP3,CP4,P3,P4,Oz | 冻结 | 本轮未针对该顺序核实（项目自有约定） | 无冲突 |
| 回放验证必要性 | 项目自己设计 mock/replay | ✅ `[官方]` MNE-LSL 提供 `PlayerLSL` 回放示例 | **得到旁证** |
| 用户抱怨 / 社区口碑 | 初版有定性描述 | ❌ 本轮未取得证据 | **待补（§13）** |
| 5 个深度学习工具箱 | 初版标 `[已核实]` | 本轮未复核 | **降级为 `[既有核实·本轮未复核]`** |

---

## 13. 未核实清单与待办

### 13.1 未核实清单（诚实交代）

1. **"换模型 / 上 GPU 对端到端延迟帮助有限"的公开依据** —— 未找到（检索类站点本轮不可用）
2. MNE-LSL 官方是否把延迟写成显式公式 —— 未找到；本文的 `T_response` 分解是**归纳**所得
3. "窗口长度 vs 信息量"的官方权衡论述 —— 未找到，仅由 BCI IV 2a 范式时长间接推断
4. **LSL4Unity 的许可证条款** —— 两路结论冲突（`Other/NOASSERTION` vs MIT），须读 LICENSE 正文
5. LSL4Unity 支持的 Unity 版本 / 是否兼容当前 LTS —— 未取到
6. VS Code 官方发行版的产品许可条款 —— 未核实
7. Anaconda 官方 TOS 原文 —— 未能访问（验证页/403）
8. MOABB 官网首页 https://moabb.neurotechx.com/ —— 抓取为空，信息以 GitHub 与文档页为准
9. BCI IV 2a 原始描述 PDF（`desc_2a.pdf`）—— 返回二进制，未读出文本（已用 MOABB 页交叉确认）
10. **各类数据集（BCI IV 2a / OpenBMI / PhysioNet）的许可与获取方式** —— 本轮未核实，**里程碑 ③ 前必须单独确认**
11. GitHub Issues / 论坛的"用户抱怨"系统性证据 —— 未取得
12. Cline / Continue / OpenCode 的免费模型额度条款 —— 未明确核实
13. braindecode / arl-eegmodels / torcheeg / EEG-ATCNet / FBCNet —— **本轮未复核**（沿用团队既有核实记录）
14. 传统平台（BCI2000 / OpenViBE / EEGLAB）与商业同类（Emotiv / g.tec 等）—— 本轮未核实
15. **"脑机盲约 15%–30%"的比例出处** —— 未找到权威来源（引自团队既有文档）
16. `bcmi-labs/BrainFlowsIntoVRChat` 的 404 状态 —— 沿用团队既有记录，本轮未复核

### 13.2 待办 checklist

- [ ] 第 1 周先验证 `websockets` 能否在本机装通并跑通
- [ ] 真实数据集上的 Kappa 数字（里程碑 ③，用 `moabb` + BCI IV 2a）—— **目前一个真实准确率数字都没有**
- [ ] 因果滤波与离线的一致性偏差是否 < 5%（伪在线回放验证）
- [ ] 目标设备型号、通道顺序、LSL 流名称（**待企业书面确认**）
- [ ] 实际游戏端技术栈（Unity？其它？→ 决定用 `LSL4Unity` 还是 WebSocket）
- [ ] 打开 LSL4Unity 仓库 `LICENSE` 正文，确认许可证
- [ ] 里程碑 ③ 前确认 BCI IV 2a 的许可与获取方式
- [ ] 采集真人数据前完成伦理审查与知情同意

---

## 14. 来源清单（URL + 访问日期 2026-10-15）

**官方文档 / 官方站**
- MNE-LSL 首页：https://mne.tools/mne-lsl/stable/index.html
- MNE-LSL 教程 00（分块推送间隔）：https://mne.tools/mne-lsl/stable/generated/tutorials/00_introduction.html
- MNE-LSL 实时解码示例：https://mne.tools/mne-lsl/stable/generated/examples/40_decode.html
- MNE-LSL `StreamLSL` API（`acquisition_delay`、因果滤波、回调阻塞）：https://mne.tools/mne-lsl/stable/generated/api/mne_lsl.stream.StreamLSL.html
- MNE-LSL 实现细节（处理链顺序）：https://mne.tools/mne-lsl/stable/resources/implementations.html
- SciPy `filtfilt`：https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.filtfilt.html
- SciPy `sosfiltfilt`：https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html
- SciPy `sosfilt`：https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfilt.html
- BCI Competition IV：https://www.bbci.de/competition/iv/
- MOABB `BNCI2014_001`（BCI IV 2a）：https://moabb.neurotechx.com/docs/generated/moabb.datasets.BNCI2014_001.html
- LSL 官方文档：https://labstreaminglayer.readthedocs.io/ ・ https://labstreaminglayer.readthedocs.io/info/intro.html
- Python 官方：https://www.python.org/downloads/ ・ https://docs.python.org/3/using/windows.html ・ https://docs.python.org/3/library/venv.html
- uv：https://docs.astral.sh/uv/ ・ https://github.com/astral-sh/uv
- VS Code：https://code.visualstudio.com/ ・ https://code.visualstudio.com/docs/python/python-tutorial
- Conda 安装与许可说明：https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html
- PowerShell 入门：https://learn.microsoft.com/en-us/powershell/scripting/learn/ps101/01-getting-started
- websockets：https://websockets.readthedocs.io/en/stable/ ・ https://websockets.readthedocs.io/en/stable/project/license.html
- GitHub Copilot：https://github.com/features/copilot
- JOSS 论文（MNE-LSL）：https://joss.theoj.org/papers/10.21105/joss.08088 （DOI 10.21105/joss.08088，2025-07）

**GitHub 仓库 / API**
- https://github.com/mne-tools/mne-lsl
- https://github.com/mne-tools/mne-realtime
- https://github.com/NeuroTechX/EEG-ExPy
- https://github.com/timeflux/timeflux
- https://github.com/brainflow-dev/brainflow
- https://github.com/sccn/liblsl
- https://github.com/NeuroTechX/moabb
- https://github.com/pyRiemann/pyRiemann
- https://github.com/labstreaminglayer/LSL4Unity
- https://github.com/NeuroTechX/awesome-bci
- https://github.com/cline/cline ・ https://github.com/continuedev/continue
- https://opencode.ai/

**仅索引、本轮未复核的仓库链接**（存在性沿用团队既有核实记录，见 §3.2）
- https://github.com/braindecode/braindecode
- https://github.com/vlawhern/arl-eegmodels
- https://github.com/torcheeg/torcheeg
- https://github.com/Altaheri/EEG-ATCNet
- https://github.com/ravikiran-mane/FBCNet

**抓取受阻记录**（供复核）
- `https://mne.tools/mne-lsl/stable/api/mne_lsl.stream.StreamLSL.html` → 404（正确路径含 `/generated/`）
- `https://neurotechx.github.io/moabb/` → 404（正确首页为 `https://moabb.neurotechx.com/docs/index.html`）
- `https://labstreaminglayer.readthedocs.io/en/latest/` → 404（根站点可用）
- `https://moabb.neurotechx.com/` → 内容为空
- DuckDuckGo / Bing / Semantic Scholar / arXiv → 未产出可用结果

**团队既有文档来源**（初版引用的出处）
- `脑机接口运动想象解码项目规划.md`
- `开源项目参考清单.md`

---

## Handoff Context
<!-- Machine-readable summary for the next workflow step. Do not delete; the next prompt in the workflow reads this block. -->
- Stage: research
- App name: BCI-Decoder
- User level: A  (A = vibe coder, B = developer, C = in-between)
  注：本文件按请求方口径**统一保持 A（零基础）**。团队实际为大一学生边学边做（既有 PRD 曾记为 C），本文件不采用 C 口径。
- Target platform: desktop  (Windows 普通笔记本，无独立显卡；交付物为 Python 模块，游戏端技术栈待定)
- Budget: 全免费优先（￥0，全部依赖须开源；结论：**可以做到真 ￥0**，前提是不用 conda 生态、不引付费云服务）
- Timeline: 10 周（2026-10-13 → 2026-12-15）；MVP 硬节点 10/27，不可延
- AI in product scope: no  (产品内不含任何 LLM / 深度学习；AI 仅用于辅助开发。官方实时解码示例也用 sklearn 经典模型，佐证"不需要大模型")
- Research status: Partial research —— 框架生态、因果滤波、延迟结构、工具链与许可证已核实（官方来源，访问日期 2026-10-15）；**"换模型/上 GPU 对端到端延迟帮助有限"未找到公开依据**；用户抱怨类证据未取得；深度学习工具箱与商业同类沿用既有核实（本轮未复核）；部分许可证与数据集许可待确认（见 §13）
- Constraints: 类别 2 类（左手/右手）+ idle；滑窗 2.0 s、步长 0.5 s；250 Hz / 8 通道；通道顺序 C3,Cz,C4,CP3,CP4,P3,P4,Oz 不可变更；单次计算耗时 p95 < 50 ms；未训练或不可信时恒输出 idle；MVP 阶段不对外报告任何准确率
- Decisions: 只做在线解码模块（游戏画面归游戏端）；特征用 CSP + log-方差(4 维) + LDA（2026-10-20 切换，原频带功率 16 维，见 `MVP规格说明书` §9 v1.1.3）；伪迹只标记不丢弃、超阈值降级为 idle；输出多通道 console + jsonl + websocket；接口契约自 2026-10-13 冻结
- Open questions: bci-decoder/ 归属 ✅ 已拍板为团队成果（2026-10-15）；企业设备型号 / 通道顺序 / LSL 流名称待书面确认；游戏端用 Unity 还是自研 Python；websockets 依赖能否安装并跑通；真实评测协议（数据集与指标口径，含数据集许可）
- Source files: docs/research-request-BCI-Decoder.md → docs/research-BCI-Decoder.md（合并版，本文件）

---

*本文件为**合并版**（2026-10-15），已并入初版 `docs/research-BCI-Decoder.md` 与联网检索版 `outputs/research-BCI-Decoder.md`（该副本已于 2026-10-15 删除）的全部独有内容。*
*标注 `[推断]` 的段落不是引用；标注 `[项目内]` 的内容来自本工作区自身文档与代码，**不得对外作为行业结论引用**。*
