# 脑电运动想象在线解码模块（BCI-Decoder）

> 翔宇医疗校企合作项目 · 把脑电中的**运动想象意图**实时解码成**可被游戏直接调用的消息流**。
> 配套 Demo：**脑控弹球**（先键盘版完整可玩，再换成解码消息驱动画面）。

**当前状态（2026-10-16）**：里程碑 ①（10/13 文档）✅ 已交付；里程碑 ②（10/27 可运行 MVP）🔄 进行中。
解码链路（`sources → buffer → pipeline → outputs`）**已跑通**，`pytest` **17/17 通过**（`bci-decoder/tests`），已产出演示模型与输出文件。
**WebSocket 输出已端到端跑通**（2026-10-16 实测：解码器 `--outputs websocket` ← 客户端收到消息、字段契约一致；`websockets 17.2` 与 `pygame-ce 2.5.8` 已装入 `.venv`）。
**游戏端（脑控弹球）代码已完成并通过工程自检**（`bci-decoder/game/`：单测 **39/39**、端到端 **39 项断言全绿**；**A7 联调录屏 / A8 真人现场验收未做 → F4 尚不能判定验收通过**）。
**未完成**：LSL、校准流程、Docker。

---

## 目录结构

| 路径 | 说明 |
|---|---|
| `bci-decoder/` | **业务代码**（在线解码模块；`game/` 为脑控弹球游戏端，已实现） |
| `docs/` | **文档体系**（规格、PRD、技术设计、研究、证据） |
| `agent_docs/` · `AGENTS.md` · `MEMORY.md` | 给 AI 编码助手的协作层（长期规则 / 进度） |
| `docs/evidence/` | 里程碑证据归档（`W{n}_{日期}/`） |
| `.tools/` | 非交付物（格式转换脚本、PDF 等），**不是业务代码** |
| `bci-decoder/artifacts/` | 模型与输出产物（**不入库**） |

---

## 快速开始

> 命令在 **`bci-decoder/`** 目录下执行。Windows **PowerShell 5.1**：**不要用 `&&`**；
> 本机 Python 版本为 **3.14.7**，必须用虚拟环境解释器 `.venv\Scripts\python.exe`（全局 `python` 没装 pytest）。
> 完整命令清单见 [`docs/MVP规格说明书.md`](docs/MVP规格说明书.md) **附录 A**。

```powershell
# 1) 跑测试（当前 bci-decoder/tests 17/17 通过）
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -q "game\tests"   # 游戏端单测（39/39；pytest.ini 的 testpaths 不收 game/，须显式传路径）

# 2) 启动解码器，输出到 WebSocket（游戏端联调用）
.venv\Scripts\python.exe -m bci_decoder.cli run --config configs/demo_online.yaml --outputs websocket

# 3) 游戏端（bci-decoder/game/，2026-10-16 已实现）
.venv\Scripts\python.exe game\pong.py --input keyboard   # 键盘降级版（C 级演示，须明说不是脑控）
.venv\Scripts\python.exe game\pong.py --input ws         # 解码驱动版：需先启动第 2 步

# 4) headless 自检 + 出报告（无显示器也能跑，队友/CI 复现用）
.venv\Scripts\python.exe game\pong.py --input ws --headless --max-frames 600 --report artifacts\pong_report.json
```

---

## 文档导航

| 想了解 | 看这里 |
|---|---|
| **范围与验收的唯一依据** | [`docs/MVP规格说明书.md`](docs/MVP规格说明书.md) |
| 解码模块：需求 / 设计 | [`docs/MVP_PRD.md`](docs/MVP_PRD.md) · [`docs/TechDesign-BCI-Decoder-MVP.md`](docs/TechDesign-BCI-Decoder-MVP.md) |
| 游戏端：需求 / 设计 | [`docs/PRD-Game-MVP.md`](docs/PRD-Game-MVP.md) · [`docs/TechDesign-Game-MVP.md`](docs/TechDesign-Game-MVP.md) |
| 技术与研究论证 | [`docs/详细技术路线.md`](docs/详细技术路线.md) · [`docs/research-BCI-Decoder.md`](docs/research-BCI-Decoder.md) |
| 团队与纪律 | [`docs/项目章程.md`](docs/项目章程.md) |
| 进度与下一步（**开工先读**） | [`MEMORY.md`](MEMORY.md) |

---

## 红线（不得违反）

1. 未训练 / 模型缺失 / 置信度不足 → **必须输出 `idle`**，绝不给游戏发随机左右指令。
2. 在线链路**只允许因果滤波**（`sosfilt` + 跨块保持状态）；**禁止** `filtfilt`。
3. 输出消息字段**不得增删**（已冻结）；`label_id == -1` 当且仅当 `label == "idle"`。
4. 通道顺序即语义（`C3, Cz, C4, CP3, CP4, P3, P4, Oz`），不得重排。
5. `mock` / `synth` 数据**只用于工程自检**，绝不可用于评估算法性能或对外报告准确率。
6. **MVP 阶段不对外报告任何准确率数字**；真实数字须来自里程碑 ③ 的公开数据集评测。
7. 类别固定 **2 类 + `idle`**；滑窗 **2.0 s** / 步长 **0.5 s**，不得擅自改动。

---

## 协作约定

- 改代码前说明改什么、怎么验证；改完**必须跑最小可用测试**（`pytest`）。
- 环境与流程必须**4 名成员都能独立跑通**（"只有一个人会跑 = 没有人会跑"）。
- 完成任务后更新 [`MEMORY.md`](MEMORY.md)（进度、决策、下一步）。
- 新增/变更接口前，先走 [`docs/MVP规格说明书.md`](docs/MVP规格说明书.md) 第 9 节的变更流程。
