# TechDesign · BCI-Decoder · MVP

> **Step 3 产出**（对照 vibe-coding-prompt-template 的 "Start a project"）
> **应用名**：`BCI-Decoder`（与 PRD 一致）
> **版本**：v1.1（2026-10-15）
> **定位**：本文件是**工作流契约版技术设计**，供 AI 助手与工作流 CLI 解析。
> **工程细节的详版是** [`在线解码模块设计说明.md`](在线解码模块设计说明.md)；
> **技术论证的详版是** [`详细技术路线.md`](详细技术路线.md)；**接口冻结以** [`MVP规格说明书.md`](MVP规格说明书.md) 第 4 节为准。
> **游戏端（横版闯关 MI Pixel Run / platformer）已单独成文**：[`TechDesign-Game-MVP.md`](TechDesign-Game-MVP.md)。
> **2026-10-22 现状注记**：游戏端主打 = **横版闯关 MI Pixel Run v1.0**（`bci-decoder/game/platformer/`，2026-10-21 并入主线并接入 WebSocket 解码器），实现自检 **72 项通过**；弹球 `pong.py` / 格子版 `runner.py` 保留为备稿、pong **不入库**。正文中 `python game\pong.py ...` 等命令行属早期弹球示例，**当前统一入口为** `python -m game.platformer.main --mode keyboard|replay|ws`（详见 TechDesign-Game-MVP.md 头部注记）。
> **v1.1 变更**：修正 User level 口径（C→A）、补备选方案对比与成本明细、补三级降级与伪迹降级链、补 Part 3 结构合规（Handoff Context 与文末 JSON）、指向游戏端文档。依据见 [`一致性复核-PRD-TechDesign.md`](一致性复核-PRD-TechDesign.md)。

---

## 1. 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                        bci-decoder 进程                          │
│                                                                  │
│  数据源层         缓冲层         处理流水线           输出层       │
│  ┌──────┐      ┌────────┐    ┌────────────┐      ┌─────────┐    │
│  │ mock │      │  环形   │    │ 因果滤波    │      │ console │    │
│  │replay│─────▶│  缓冲   │───▶│ CAR 重参考  │─────▶│  jsonl  │    │
│  │ lsl  │      │(固定容量)│    │ 伪迹标记    │      │   ws    │    │
│  └──────┘      └────────┘    └─────┬──────┘      └────┬────┘    │
│                                    ▼                  │          │
│                      ┌─────────────────────────┐      │          │
│                      │ 滑窗触发 → 特征 → 分类   │      │          │
│                      │        → 决策稳定化      │      │          │
│                      └─────────────────────────┘      │          │
└───────────────────────────────────────────────────────┼──────────┘
                                          ws://127.0.0.1:8765
                                                        ▼
                            ┌────────────────────────────────────┐
                            │  game 进程（横版闯关 MI Pixel Run，独立文档）      │
                            │  见 TechDesign-Game-MVP.md          │
                            └────────────────────────────────────┘
```

**分层原则**（来自详版设计说明，保持不变）：

1. **数据源可替换** —— 实现 `Source.stream()` 即可接入任意设备；
2. **各环节独立可测** —— 预处理/特征/分类/后处理都能单独单元测试；
3. **输出多通道** —— 同一次解码可同时送终端、落盘、WebSocket；
4. **配置驱动** —— 所有参数集中在单个 YAML，交付时企业只改一个文件。

**唯一的用户界面是游戏端**（游戏窗口）；本模块是 headless 的，**游戏端坏掉不影响本模块成立**。

---

## 2. 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 语言 | **Python 3.14.7**（当前实测环境；`requirements` 口径为 3.10+） | 生态完整、团队可学 |
| 数值计算 | NumPy 2.5.3 / SciPy 1.18.1 | `sosfilt` 提供因果滤波与状态保持 |
| 机器学习 | scikit-learn 1.9.1 | LDA + 标准化，小数据强基线 |
| 配置 | PyYAML 6.0.3 | 单文件配置 |
| 模型持久化 | joblib 1.6.0 | 保存/加载 LDA |
| 测试 | pytest 9.1.1 | 单元 + 端到端 |
| 实时通信 | **websockets**（✅ 已装通并端到端验证，17.2，2026-10-16） | F5 的关键依赖 |
| 设备接入 | **pylsl**（尚未安装，④ 阶段） | 真实设备 LSL 流 |
| GPU | **不需要** | 计算量极小（p95 数毫秒） |
| 明确不引入 | 深度学习框架、Docker、Web 框架、消息队列 | 见 §3；MVP 拒绝无谓依赖 |

> **依赖现状（2026-10-15 核实）**：venv 内已装 numpy / scipy / scikit-learn / PyYAML / joblib / pytest；
> **`mne`、`moabb`、`pyriemann`、`pylsl` 均未安装**（`websockets` 已于 2026-10-16 装通并端到端验证）。

---

## 3. 备选方案对比与取舍

技术选型有两个真正需要论证的决策点。**两处都选"更笨但更稳"的那个**——MVP 的瓶颈是窗口长度与工程纪律，不是算法先进度。

### 3.1 解码算法路线

| 候选 | 优势 | 代价 / 风险 | 结论 |
|---|---|---|---|
| **A. 因果带通 + CAR + CSP（空间滤波，4 维）+ LDA** | 小数据强基线；空间滤波对 ERD/ERS 判别力强（与立项 `Project-Proposal` 路线一致）；训练秒级；单次推理数毫秒、**无需 GPU**；调试路径短（滤波器有没有保状态一看就知道） | 跨被试/跨 session 泛化一般，需靠④的校准补 | ✅ **采用（MVP）** |
| B. 深度学习（EEGNet 等 CNN） | 理论上可自动学空域滤波，上限更高 | **数据量不够**；跨被试常打不过传统方法；需 GPU 与调参预算；**不可解释**，出问题难定位；训练慢 → 迭代慢 | ❌ 本期不做（`MVP规格说明书` L89 已明确） |
| C. 黎曼几何（协方差 + 欧氏对齐 / Riemannian） | 跨被试/跨 session 通常优于频带功率/CSP | 需引入 `pyriemann`；调试门槛高；团队 10 周内消化不了 | ⏳ **延后至里程碑 ④**（已排期） |

> **为什么"不靠换算法提速"**：`research-BCI-Decoder.md` 已核实瓶颈是**窗口长度（2.0 s）**，不是算法——换深度模型或买显卡对端到端延迟几乎没有帮助。所以 MVP 把精力投在因果滤波、稳定化与工程纪律上，而不是模型层。

### 3.2 与游戏端的传输机制

| 候选 | 优势 | 代价 / 风险 | 结论 |
|---|---|---|---|
| **WebSocket（本机 127.0.0.1）** | 轻量、协议自研可读（就是 §5.2 的 JSON）；Python 客户端 5 行；**与"本地单进程、不联网"取向一致** | ~~需装 `websockets`（尚未验证，最大不确定性）~~ ✅ **已验证（2026-10-16，17.2 装通并端到端跑通）** | ✅ **采用（MVP 的 F5 主路径）** |
| LSL（Lab Streaming Layer） | 脑电界事实标准；企业侧设备生态成熟；天然多消费者 | 需 `pylsl` + 设备端配合；企业设备型号/流名称**尚未书面确认**；调试链路更长 | ⏳ ④ 阶段（真实设备与对外集成） |
| 文件轮询（`jsonl` tail） | **零新依赖**，一定能跑通 | 有落盘延迟，非实时 | ✅ 作为**降级路径**保留（见 §9） |

> **企业未来客户端若用 Unity**，才需要再评估 LSL4Unity vs WebSocket。注意：`research-BCI-Decoder.md` §6 记录 **LSL4Unity 许可证来源冲突（`NOASSERTION` vs MIT）未定论、主分支最后提交 2023-07-31**，采用前必须读 LICENSE 正文。**此项不在 MVP 范围。**

---

## 4. 目录结构

```
bci-decoder/
├── bci_decoder/
│   ├── types.py              # EEGChunk / DecoderOutput —— 对外契约
│   ├── config.py             # 全部可调参数
│   ├── buffer.py             # 环形缓冲（固定容量）
│   ├── core.py               # 解码引擎主循环 + 延迟统计
│   ├── cli.py                # 命令行入口（run / benchmark / show-config）
│   ├── synth.py              # 合成数据（仅供自检，禁止用于评测）
│   ├── pipeline/
│   │   ├── preprocess.py     # 因果滤波 + CAR + 伪迹标记
│   │   ├── features.py       # CSP(当前路线) / 频带功率 / 协方差
│   │   ├── classifier.py     # LDA / ONNX / 未训练占位
│   │   └── postprocess.py    # EMA 平滑 + 投票 + 置信度门限
│   ├── sources/              # mock / replay / lsl
│   └── outputs/              # console / jsonl / websocket
├── configs/                  # default.yaml / demo_online.yaml / demo_replay.yaml
├── scripts/                  # bootstrap_demo.py / make_sample_data.py
├── tests/                    # test_buffer.py / test_pipeline.py / test_engine.py
├── artifacts/                # 模型与输出产物（不入库）
├── requirements.txt
├── pytest.ini
└── game/                     # 游戏端（横版闯关 MI Pixel Run / platformer）—— 见 TechDesign-Game-MVP.md
```

> **命令一律在 `bci-decoder/` 目录下执行**（扁平布局，`python -m bci_decoder.cli` 免安装）。
> **`game/` 位置已定案（2026-10-15）：`bci-decoder/game/`** —— 与 `MVP规格说明书` 附录A 一致（先 `cd bci-decoder`，再执行 `python -m game.platformer.main --mode keyboard|replay|ws`；早期 `python game\pong.py` 为弹球备稿、不入库）。

---

## 5. 数据模型与契约

### 5.1 输入（`EEGChunk`）

形状 `(n_channels, n_samples)`、单位 µV（不做量纲转换）、采样率 250 Hz、
通道数 8、通道顺序 `C3, Cz, C4, CP3, CP4, P3, P4, Oz`（**顺序即语义**）、
建议块长 100 ms（25 采样点）、时间戳单调递增（秒，float）。

> ⚠️ **通道顺序是本项目最容易出错、最难排查的问题**：顺序错了 C3/C4 侧向性完全颠倒，
> 模型会**稳定地输出相反结果**（看起来"很准"，其实全反）。

### 5.2 输出（`DecoderOutput` → JSON 一行）

```text
{
  "t_data": 12.345, "t_wall": 8412.551,
  "label": "left", "label_id": 0, "confidence": 0.83,
  "probs": [0.83, 0.17], "state": "running",
  "compute_ms": 1.2, "window_seconds": 2.0
}
```

不变式：`label_id == -1 ⟺ label == "idle"`；`probs` 恒长 2、和为 1；
`confidence` 是**当前输出类别**的置信度；数值一律 JSON number。
**字段不得增删**（已冻结）。

### 5.3 配置基线（关键字段）

```yaml
source:   { kind: replay, sfreq: 250.0, ch_names: [C3,Cz,C4,CP3,CP4,P3,P4,Oz], block_ms: 100 }
preprocess: { notch_hz: 50.0, notch_q: 30.0, bandpass_hz: [8.0, 30.0], reref: car,
              artifact: { method: ptp, threshold_uv: 150, action: mark } }
window:   { seconds: 2.0, step_seconds: 0.5 }
features: { kind: csp, csp_components: 4, csp_reg: 1e-4, model_path: artifacts/demo_csp.joblib }
classifier: { kind: lda, path: artifacts/demo_lda.joblib }
postprocess: { ema_alpha: 0.3, vote_n: 3, confidence_threshold: 0.6, untrained_policy: idle }
outputs:  [ {kind: console},
            {kind: jsonl, path: artifacts/decoder_output.jsonl},
            {kind: websocket, host: 127.0.0.1, port: 8765} ]
```

### 5.4 `state` 取值规则（v1.1 新增）

`state` 只有两个取值，**游戏端会依赖它做界面显示，必须按规则给出**：

| 取值 | 何时 | 说明 |
|---|---|---|
| `stabilizing` | 启动后 / `start` 之后、**首次达到"连续 N 次一致"之前** | 即"过渡期"。此时输出应为 `idle`（除非已满足门限） |
| `running` | 稳定化确认之后 | 正常解码输出 |

> **不要用 `state` 改玩法**：它只表达"是否还在稳定化"，**不是**置信度、也不是信号质量。
> 交界处应单调切换（`stabilizing` → `running`），**不得来回跳**。

### 5.5 伪迹降级链（v1.1 新增）⚠️ 安全链

契约的 `artifact.action: mark` **只是"标记"**，不构成安全保证。完整链条必须显式实现：

```
PTP > 150 µV  →  标记该窗口
              →  该窗口不产生有效决策（输出 idle，或沿用上一稳定状态但不得切换类别）
              →  连续超阈值 / 信号质量持续异常
              →  进入  stabilizing（必要时驱动 stop 语义）→ 输出 idle
              →  游戏端表现为"角色不动"
```

**规则**：
- **可疑窗口绝不产生"新方向"**——宁可不更新，不可误触发（视觉原则 1 / "宁可迟钝，不可抖动"）；
- 降级是**可恢复**的：质量恢复后重新走稳定化流程回到 `running`；
- 触发降级时**必须记日志**（时间戳 + 触发的统计量），否则演示时无法解释"为什么刚才不动"。

---

## 6. 关键实现要点（三个"必须"）

### 6.1 滤波必须**带状态**（因果）

在线数据分块到达。若用零相位 `filtfilt` 逐块重滤，**块边界会产生跳变**，特征剧烈抖动，在线表现远差于离线。
实现用 `sosfilt` 并**跨 chunk 保持滤波器状态**（`zi`）。这是在线与离线最本质的工程差异。

### 6.2 缓冲必须**固定容量**

环形缓冲容量恒定，保证**长跑 1 h 内存不增长**。

### 6.3 未训练必须**恒输出 `idle`**

未指定模型时使用未训练占位分类器 → 输出均匀概率 → 低于置信度门限 → `idle`。
**保证模型没准备好时也不会给游戏发送随机指令。**

> **"宁可迟钝，不可抖动"**：后处理三重机制 = 概率 EMA 平滑 → 连续 N 次一致才切换 → 置信度门限。
> demo 中类别切换时约 1 秒的过渡期（显示 `idle`）**正是策略体现，不是缺陷**。

---

## 7. 命令（确切命令，在 `bci-decoder/` 下执行）

> Windows PowerShell 5.1 环境（**不使用 `&&`**）。

| 用途 | 命令 |
|---|---|
| **setup** | `python -m venv .venv` → `.venv\Scripts\activate` → `pip install -r requirements.txt` |
| **test** | `python -m pytest` |
| **build**（准备演示模型） | `python scripts/bootstrap_demo.py --config configs/default.yaml` |
| **dev**（在线解码，mock 源） | `python -m bci_decoder.cli run --config configs/demo_online.yaml --chunks 200` |
| dev（不限块数：长跑 / 联调用） | `python -m bci_decoder.cli run --config configs/demo_online.yaml` |
| dev（伪在线回放） | `python scripts/make_sample_data.py --out data/sample_continuous.npy --seconds 60` 后 `python -m bci_decoder.cli run --config configs/demo_replay.yaml --chunks 300` |
| **benchmark** | `python -m bci_decoder.cli benchmark --config configs/demo_online.yaml --chunks 600` |
| 查看生效配置 | `python -m bci_decoder.cli show-config --config configs/demo_online.yaml` |
| **游戏端** | `python -m game.platformer.main --mode ws --ws-url ws://127.0.0.1:8765`（详见 `TechDesign-Game-MVP.md`） |
| lint / typecheck | **未设置**（MVP 不引入 flake8/mypy） |

**验收当天五步（顺序与含义不得省略）**：

```powershell
# 1) 自检：单元 + 端到端测试
python -m pytest
# 2) 终端观察解码输出（不需要游戏）
python -m bci_decoder.cli run --config configs/demo_online.yaml --chunks 200
# 3) 延迟分解
python -m bci_decoder.cli benchmark --config configs/demo_online.yaml --chunks 600
# 4) 查看实际生效的全部参数
python -m bci_decoder.cli show-config --config configs/demo_online.yaml
# 5) 启动 WebSocket，再启动游戏端（需先 pip install websockets）
python -m bci_decoder.cli run --config configs/demo_online.yaml --outputs websocket
python -m game.platformer.main --mode ws --ws-url ws://127.0.0.1:8765   # 另开一个终端；游戏端定义见 TechDesign-Game-MVP.md
```

> ⚠️ **`build` 步骤的红线提示（v1.1 新增）**：`bootstrap_demo.py` 会打印**合成数据**的交叉验证准确率。
> **该数字是必然接近 100% 的工程自检结果，禁止用于评估算法性能或对外报告**（`AGENTS.md` 硬性约束 5、6）。
> 演示与答辩材料中**不得**出现任何由此产生的准确率数字；真实数字须等里程碑 ③ 的公开数据集评测。

---

## 8. 部署

| 项 | MVP 方案 |
|---|---|
| 运行形态 | **本地单进程**（笔记本），无服务器、无云服务 |
| 依赖安装 | `pip install -r requirements.txt`（全部开源，零成本） |
| 网络 | **不联网也能演示** |
| 交付物 | 代码 + 单文件 YAML 配置 + 运行说明（`bci-decoder/README.md`） |
| Docker | **MVP 不做**，归里程碑 ⑥ |
| 演示机准备 | 提前在演示机跑通 + 准备离线依赖包 |

---

## 9. 降级策略（v1.1 新增）

对齐 `MVP规格说明书` §11.2 的三级降级。**降级不是失败，是预案**：

| 级别 | 触发条件 | 技术形态 | 演示口径 |
|---|---|---|---|
| **A 级**（正常） | 一切按设计运行 | 实时链路 + WebSocket，游戏端实时驱动 | 正常演示 |
| **B 级** | WebSocket 打不通 / `websockets` 装不上 | **砍 WebSocket**：保留 `console` + `jsonl`；游戏端改 `--input jsonl` 轮询 `artifacts/decoder_output.jsonl`（准实时回放）；或改本地 TCP | **必须说明是"准实时回放"**，不得声称实时 |
| **C 级** | 时间不够 / 真实链路仍不通 | 只演示**键盘版游戏** + 终端解码输出，讲清原理与已完成的验证 | **必须说明是键盘输入**，不得假装脑控 |

**WebSocket 的具体降级路径**（PRD §F5 要求，v1.1 补齐设计）：

1. **首选降级：`jsonl` 轮询**——链路几乎不变（`outputs/jsonl` 已在配置里），仅游戏端换输入源；**零新依赖**；
2. **备选降级：本地 TCP 直连**——若需要更低延迟但不支持 WebSocket；
3. 两者都要求在游戏端**不改玩法代码**（`input_source.py` 加一个实现即可，见 `TechDesign-Game-MVP.md` §8/§10）。

**决策纪律**：降级口径**必须如实通报**（`项目章程` 与 PRD Design Vibe 的"诚实"要求）。虚报进度比降级严重。

---

## 10. 验证与证据

| 层级 | 测什么 | 工具 | 通过标准 |
|---|---|---|---|
| 单元测试 | 缓冲覆盖/时间戳、滤波状态连续性、特征维度、分类器接口、稳定化逻辑 | `pytest` | 全部通过 |
| 端到端自检 | `mock` 源跑通全链路并产出结果 | `pytest` + mock | 全部通过 |
| **伪在线回放** | 录制数据分块重放，检验滤波状态与滑窗 | `replay` 源 | 输出连续、无跳变 |
| 算力压测 | 不限速测量计算耗时分布 | `cli benchmark` | **p95 < 50 ms** |
| 调度抖动 | 采集到决策的时间戳差值统计 | 长跑/联调脚本 | **< 10 ms**（`MVP规格说明书` N3，L143） |
| 稳定性 | 连续 1 h 观察内存与耗时漂移 | 长跑脚本 | 无增长趋势 |
| 降级演练 | 杀掉 WS 服务端 / 断网，走 B 级路径 | 手动 + 脚本 | 链路仍可演示（§9） |
| 游戏联调 | 解码消息驱动画面 | WebSocket | 动作与 `label` 一致（A7：**必须真驱动画面**，不是"端口能连"） |
| 契约一致性 | 输出字段/取值与冻结契约逐字段比对 | 脚本 + `REVIEW-CHECKLIST.md` 表 D | 无增删、无越界取值 |

> **测试纪律（红线）**：`mock` 源与 `synth` 合成数据**只用于自检流程是否通**，**绝不能作为算法成绩**。
> 交叉验证接近 100% 是合成数据的**必然结果**，不是成果。
> 真实准确率等里程碑 ③ 用 `moabb` + BCI IV 2a 给出。详见 [`agent_docs/testing.md`](../agent_docs/testing.md)。

**证据归档**：所有证据按 `docs/evidence/W{n}_{日期}/` 归档（`MVP规格说明书` §11.1，L552），包括：测试输出、benchmark 结果、联调录屏、降级演练记录。
（nice-to-have：可做一键归档脚本，见 PRD Nice to Have。）

---

## 11. 成本明细（v1.1 新增）

**口径**：本 MVP 为**课程/校企合作演示项目**，4 名成员人力投入计入课程学分，**不计货币成本**；下列金额为**估算/标注**，非报价。

| 项 | 估算 | 类型 | 依据 / 说明 |
|---|---|---|---|
| Python / NumPy / SciPy / scikit-learn / PyYAML / joblib / pytest | **￥0** | 软件（开源） | 全部开源免费；许可证类型以各项目 LICENSE 为准（对外交付前需核对） |
| Pygame（游戏端） | **￥0** | 软件（开源） | 同上；演示级使用 |
| `websockets` | **￥0** | 软件（开源） | 同上；~~能否装通尚未验证~~ ✅ **已验证**（2026-10-16，17.2 装通并端到端跑通） |
| 运行硬件（笔记本） | **￥0 新增** | 已有资产 | 团队自有笔记本；**要求无独立显卡**（本项目不需 GPU），非新增采购 |
| GPU / 云服务 / 服务器 | **￥0** | 不采用 | 明确不引入（§2 明确排除项） |
| 采集设备（脑电帽/放大器） | **不报价** | 企业提供 | 由翔宇医疗提供；型号与通道顺序**待企业书面确认**（【未决】）；若需自购属企业决策，不计入本项目预算 |
| 公开数据集（`moabb` / BCI IV 2a） | **￥0** | 公开数据 | 里程碑 ③ 评测使用 |
| 外包 / 美术 / 设计 | **￥0** | 不采用 | 界面为演示级，无美术采购 |
| 人力 | **课程学分** | 4 人 × 10 周 | `项目章程` 定义的团队投入 |

**总计新增货币支出：￥0。**
**主要"成本"是时间与人力**——这正是 §3 选择"更笨但更稳"技术路线、§9 预置降级方案的原因。

---

## 12. AI 范围（与 PRD 一致）

- **产品内 AI：无** —— 确定性信号处理链路，无深度学习、无 LLM、无 GPU 需求。
- **开发过程 AI：有** —— 使用 AI 编码助手（`AGENTS.md` 体系）辅助实现与测试。
- **排除**：在线自适应学习、AI 解码增强（属里程碑 ④ 之后的独立评估项）。

**AI 不得代劳的事**：不得替团队判断"是否可用真人体数据"——**本项目不采集真实患者数据**（伦理流程未走完，`MVP规格说明书` §11.3 L574 明确不做）；不得生成任何性能/准确率数字。

---

## 13. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| ~~**`websockets` 能否装通未验证**~~ ✅ **已排除（2026-10-16）**：17.2 装通并端到端跑通（CLI `--outputs websocket` → 客户端收消息、字段契约一致） | ~~阻塞 F5 + 游戏联调~~ | —— |
| **通道顺序错** | 稳定输出相反结果，且"看起来很像成功" | 从第一天锁定顺序；`show-config` 核对；CONTRIBUTING/README 写明 |
| **误把合成数据效果当成绩** | 触碰红线（学术诚信） | §7/§10 红线提示；代码注释 + 演示脚本检查 |
| **窗口长度被"顺手改小"** | 破坏游戏节奏与验收口径，且需重新训练 | 2.0 s 冻结；改动走 `MVP规格说明书` 第 9 节变更流程 |
| **设备型号/流名称未书面确认** | ④ 阶段 LSL 接入返工 | 尽早向企业书面确认 |
| **线上/离线实现的隐蔽分叉** | 离线能跑、在线失效（如用 `filtfilt` 重滤） | 伪在线回放必测；`sosfilt + zi` 状态保持有单测 |
| **`state` 语义被游戏端滥用** | 玩法出现莫名停顿/抖动 | §5.4 明确"`state` 只表达稳定化阶段"；新文档同步 |

---

## 14. 里程碑与技术债务

| # | 日期 | 技术目标 | 已知技术债 |
|---|---|---|---|
| ② | 10/27 | 链路 + 稳定化 + WebSocket + 横版闯关 Demo（MI Pixel Run）打通 | ~~`websockets` 未验证~~ ✅ 已跑通（2026-10-16）；`game/` 最终路径 ✅ 已定 = `bci-decoder/game/`（platformer 2026-10-21 接入 WS） |
| ③ | 11/10 | `moabb` + BCI IV 2a 真实基线；伪在线一致性 < 5% | 需引入 `mne` / `moabb` |
| ④ | 12/01 | 黎曼 + 欧氏对齐、校准流程、LSL、稳定性 | 设备型号未确认 |
| ⑥ | 12/15 | Docker / 一键部署、交付说明 | `vibe.project.json` 与 CI 尚无 |

> **游戏端必须与算法并行开工**（不等 ②），其玩法/输入切换/界面在 [`TechDesign-Game-MVP.md`](TechDesign-Game-MVP.md) 中定义。

---

*Last Updated: 2026-10-15 ｜ Next Review: 里程碑 ②（10/27）后复盘技术债与降级演练结果*

---

## Handoff Context

- Stage: techdesign
- App name: BCI-Decoder（脑控游戏 · 运动想象在线解码模块）
- User level: A（零基础 vibe coder，按 PRD 已确认口径统一；**团队实现能力另记于 Constraints**，不再占用本字段）
- Target platform: Windows 笔记本（PowerShell 5.1，Python 3.14.7，无 GPU，本地单进程）
- Budget: ￥0 新增货币支出（全开源；详见 §11 成本明细，人力计入课程学分）
- Timeline: 10 周（2026-10-13 – 2026-12-15）；MVP 硬节点 **10/27**（里程碑 ②）
- AI in product scope: none（产品运行不调用大模型与深度学习：确定性信号处理链路，无 LLM/GPU；AI 仅用于辅助开发）
- Chosen stack: Python 3.14.7 + NumPy 2.5.3 + SciPy 1.18.1 + scikit-learn 1.9.1（LDA）+ PyYAML 6.0.3 + joblib 1.6.0 + pytest 9.1.1；`websockets`（✅ 已装并跑通，17.2，F5 关键）；`pylsl`（④）；游戏端 Pygame（另见 TechDesign-Game-MVP.md）
- AI coding tool: AI 编码助手辅助实现与测试（`AGENTS.md` 体系 / vibe-coding 工作流）；人工负责跑测试、真机联调与验收
- Constraints: 命令必须在 `bci-decoder/` 内执行（扁平布局，`python -m bci_decoder.cli` 免安装）｜Windows PowerShell 5.1 **禁止 `&&`**｜滤波必须因果且跨 chunk 保状态（**禁止在线用 `filtfilt`**）｜环形缓冲固定容量｜未训练恒输出 `idle`｜**输出字段不得增删**｜滑窗 **2.0 s** / 步长 **0.5 s** **冻结不得改**｜通道顺序 `C3,Cz,C4,CP3,CP4,P3,P4,Oz` **不得重排**｜p95 < 50 ms｜调度抖动 < 10 ms｜**不采集真实患者数据**（伦理未走完）｜**MVP 不对外报告任何准确率**｜团队实现水平：C（大一学生，按此深度写注释与文档）
- Decisions: MVP 用**CSP + LDA**（2026-10-20 由频带功率 16 维切换，见 `MVP规格说明书` 第 9 节 v1.1.3；不用深度学习；黎曼延后至④）｜传输用 **WebSocket**（LSL 延后至④）｜本地单进程、不做 Docker｜数据源以 mock/replay 为主，lsl 留接口不启用｜模型产物存 `artifacts/`（不入库）｜**游戏端（主打横版闯关 MI Pixel Run）单独成文** `TechDesign-Game-MVP.md`｜降级优先 `jsonl` 轮询（零新依赖）｜`state` 仅表达稳定化阶段，不得用于改玩法
- Open questions: （已关闭 2026-10-16：`websockets` ✅ 已装通并端到端跑通）｜企业设备型号/通道顺序/LSL 流名称待书面确认｜真实基线评测协议（数据集与指标口径）｜企业未来客户端是否 Unity（不在 MVP 范围）｜`bci-decoder/` 归属口径 ✅ 已拍板为团队成果（2026-10-15）｜`game/` 位置 ✅ 已定案 `bci-decoder/game/`
- Research status: 已核实——因果滤波必要性、窗口长度是延迟瓶颈（非算法）、WebSocket vs LSL 取舍、`pylsl`/`moabb` 可用性、合成数据 CV 必然接近 100% ｜⚠️ 未定论——`LSL4Unity` 许可证来源冲突（`NOASSERTION` vs MIT）、支持哪些 Unity 版本 `[未核实]` ｜未核实——真实设备型号与通道顺序（待企业确认）
- Source files: docs/MVP_PRD.md｜docs/MVP规格说明书.md（§4 字段与控制消息、§11.1–11.3 证据/降级/明确不做、附录A 验收五步）｜docs/TechDesign-Game-MVP.md｜docs/在线解码模块设计说明.md｜docs/详细技术路线.md｜docs/research-BCI-Decoder.md｜docs/一致性复核-PRD-TechDesign.md｜REVIEW-CHECKLIST.md｜agent_docs/tech_stack.md、agent_docs/testing.md｜AGENTS.md、MEMORY.md

```json
{
  "schemaVersion": 1,
  "documentType": "techdesign",
  "appName": "BCI-Decoder",
  "stack": {
    "backend": "Python 3.14.7 + NumPy 2.5.3 + SciPy 1.18.1 + scikit-learn 1.9.1 + PyYAML 6.0.3 + joblib 1.6.0 + pytest 9.1.1；实时通信 websockets（✅ 已装通并端到端验证，17.2），设备接入 pylsl（④）",
    "frontend": "无（headless 模块，无 UI；唯一用户界面在 game/ 横版闯关 MI Pixel Run，见 TechDesign-Game-MVP.md）",
    "deployment": "本地单进程（Windows 笔记本，无 GPU），无服务器/无云服务；MVP 不做容器（Docker 归里程碑 ⑥）"
  },
  "commands": {
    "setup": "python -m venv .venv; .venv\\Scripts\\activate; pip install -r requirements.txt",
    "dev": "python -m bci_decoder.cli run --config configs/demo_online.yaml --chunks 200",
    "test": "python -m pytest",
    "typecheck": "",
    "lint": "",
    "build": "python scripts/bootstrap_demo.py --config configs/default.yaml"
  },
  "aiScope": "none（产品内不使用 AI：确定性信号处理链路，无深度学习/LLM/GPU；仅由 AI 编码助手辅助开发）"
}
```
