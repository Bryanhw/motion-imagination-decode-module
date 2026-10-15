# bci-decoder · 面向脑控游戏的在线运动想象解码模块

一个**可独立运行、可被游戏直接调用**的在线解码服务。
输入脑电数据流，输出 `运动意图 + 置信度 + 时间戳`，游戏侧无需了解任何脑电细节。

```
[EEG 设备/回放] ──LSL/文件──▶ [bci-decoder] ──WebSocket/JSONL──▶ [脑控游戏]
                                滤波→特征→分类→稳定化
```

---

## 快速开始

```bash
# 1. 建虚拟环境并装依赖
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

# 2. 跑单元测试（14 项）
python -m pytest

# 3. 端到端自检 + 训练一个演示模型
python scripts/bootstrap_demo.py --config configs/default.yaml

# 4. 在线解码（mock 源，加载刚训练的模型）
python -m bci_decoder.cli run --config configs/demo_online.yaml --chunks 200

# 5. 伪在线验证：把离线数据当实时流回放
python scripts/make_sample_data.py --out data/sample_continuous.npy --seconds 60
python -m bci_decoder.cli run --config configs/demo_replay.yaml --chunks 300

# 6. 算力压测（不限速，看纯计算耗时）
python -m bci_decoder.cli benchmark --config configs/demo_online.yaml --chunks 600
```

---

## 三种数据源（改一个配置项即可切换）

| kind | 用途 | 何时用 |
|---|---|---|
| `mock` | 合成脑电自检 | 无硬件、无数据时验证工程链路 |
| `replay` | 离线数据回放 | **最重要**：伪在线验证，不占设备与被试 |
| `lsl` | 真实设备实时流 | 设备接入后（需 `pip install pylsl`） |

切换只需改 `configs/*.yaml` 里的 `source.kind`。

---

## 目录结构

```
bci-decoder/
├── bci_decoder/
│   ├── types.py              # EEGChunk / DecoderOutput —— 对外契约
│   ├── config.py             # 全部可调参数
│   ├── buffer.py             # 环形缓冲
│   ├── core.py               # 解码引擎主循环
│   ├── cli.py                # 命令行入口
│   ├── synth.py              # 合成数据（仅供自检）
│   ├── pipeline/
│   │   ├── preprocess.py     # 因果滤波 + CAR + 伪迹标记
│   │   ├── features.py       # 频带功率 / 协方差 / 欧氏对齐
│   │   ├── classifier.py     # LDA / ONNX / 占位
│   │   └── postprocess.py    # 平滑 + 投票 + 置信度门限
│   ├── sources/              # mock / replay / lsl
│   └── outputs/              # console / jsonl / websocket
├── configs/                  # default / demo_online / demo_replay
├── scripts/                  # bootstrap_demo / make_sample_data
└── tests/                    # 单元测试
```

---

## 关键设计说明

### 1. 为什么滤波必须"带状态"

在线场景下数据是分块到达的。如果用普通的 `filtfilt`（零相位、非因果），
每个 chunk 都要重新滤波，**块边界会产生跳变**，特征剧烈抖动，
在线表现会远差于离线。因此 `pipeline/preprocess.py` 使用 `sosfilt` 并
跨 chunk 保持滤波器状态——这是在线与离线最本质的工程差异之一。

### 2. 延迟由什么决定

`benchmark` 实测（本机 Python 3.14）：

| 指标 | 数值 |
|---|---|
| 计算耗时 p50 | 3.1 ms |
| 计算耗时 p95 | 4.7 ms |
| 计算耗时 max | 11.1 ms |
| 预估端到端 p95 | **≈ 2005 ms** |

**结论很有指导意义**：纯计算只占约 5 ms，端到端延迟几乎完全由 **2 秒滑窗**决定。
所以想提速，方向不是"优化模型"，而是**缩短窗口**——但窗口越短准确率越低。
这个权衡必须和游戏节奏一起定，是项目最核心的工程决策。

### 3. 未训练模型的安全行为

`configs/default.yaml` 未指定 `classifier.model_path` 时使用占位分类器，
输出均匀概率 → 低于置信度门限 → **恒输出 `idle`**。
这样即使模型没准备好，也不会给游戏发送随机指令。

### 4. "宁可迟钝，不可抖动"

`postprocess.py` 的三重机制：概率 EMA 平滑 → 连续 N 次一致才切换 → 置信度门限。
注意 demo 输出中类别切换时约 1 秒的过渡期（显示 `idle`），
这正是"稳定优先"策略的体现，而非缺陷。

---

## 输出消息格式（游戏侧对接契约）

WebSocket 每帧一条 JSON：

```json
{
  "t_data": 12.345,
  "t_wall": 8412.551,
  "label": "left",
  "label_id": 0,
  "confidence": 0.83,
  "probs": [0.83, 0.17],
  "state": "running",
  "compute_ms": 1.2,
  "window_seconds": 2.0
}
```

启用方式：把配置里的 `output.sinks` 改为 `[websocket]`（需 `pip install websockets`）。

---

## 扩展点（留给后续迭代）

| 要做什么 | 改哪里 |
|---|---|
| 换成黎曼几何分类 | `pipeline/features.py` 用 `CovarianceExtractor` + `pyriemann`，`classifier.py` 加分类器 |
| 接入深度模型（EEGNet 等） | 训练后导出 ONNX，配置 `classifier.kind: onnx` |
| 多脑区融合 | 在 `features.py` 按通道分组提取，或 `classifier.py` 加多分支模型 |
| 在线自适应 | 在 `core.py` 决策循环中加入增量更新 |
| 跨被试迁移 | 训练阶段用 `synth`/真实数据做 LOSO 实验，推理阶段用 `euclidean_align` |

---

## 免责说明

`synth.py` 与 `mock` 源生成的是**工程自检数据**（交叉验证 100% 是必然结果），
只用于验证代码链路是否正确，**不得用于评估算法性能或对外报告准确率**。
真实评估必须使用公开数据集（BCI IV 2a/2b、OpenBMI 等）或企业实测数据。
