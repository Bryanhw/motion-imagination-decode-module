# 技术栈与确切命令（tech_stack）

> **所有命令都在 `bci-decoder/` 目录下执行。** 环境是 **Windows PowerShell 5.1** ——
> **不要使用 `&&`**（PS 5.1 不支持），用 `;` 分隔或分步执行。

---

## 1. 环境事实（2026-10-15 核实）

| 项 | 值 |
|---|---|
| 解释器 | **Python 3.14.7**（`bci-decoder/.venv`） |
| Shell | Windows PowerShell 5.1（**win32**，非 WSL） |
| GPU | **不需要** |
| 网络 | **不需要**（演示可离线） |

**已安装**：`numpy 2.5.3`、`scipy 1.18.1`、`scikit-learn 1.9.1`、`PyYAML 6.0.3`、`joblib 1.6.0`、`pytest 9.1.1`

**未安装（注意）**：`mne`、`moabb`、`pyriemann`、`pylsl`（`websockets` 已于 2026-10-16 装通并端到端验证）

> ⚠️ **坑**：全局 `python`（`C:\Users\yhw\AppData\Local\Python\pythoncore-3.14-64`）**没有 pytest**。
> 直接跑 `python -m pytest` 会报 `No module named pytest`。**必须激活 venv**，或显式用
> `bci-decoder\.venv\Scripts\python.exe`。

---

## 2. 命令速查（setup / dev / test / build）

### setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### test

```powershell
python -m pytest
```

- 预期：**14 项全部通过**（基线，2026-10-15）
- 未激活 venv 时改用：`.venv\Scripts\python.exe -m pytest`

### build（准备演示模型）

```powershell
python scripts/bootstrap_demo.py --config configs/default.yaml
```

### dev（在线解码，mock 数据源）

```powershell
python -m bci_decoder.cli run --config configs/demo_online.yaml --chunks 200
```

### dev（伪在线回放，更接近真实）

```powershell
python scripts/make_sample_data.py --out data/sample_continuous.npy --seconds 60
python -m bci_decoder.cli run --config configs/demo_replay.yaml --chunks 300
```

### benchmark（延迟实测）

```powershell
python -m bci_decoder.cli benchmark --config configs/demo_online.yaml --chunks 600
```

### 查看实际生效的参数

```powershell
python -m bci_decoder.cli show-config --config configs/demo_online.yaml
```

### F5：WebSocket 输出（需先装 `websockets`）

```powershell
pip install websockets
python -m bci_decoder.cli run --config configs/demo_online.yaml --outputs websocket
```

### typecheck / lint

**本项目未设置 typecheck 与 lint。** 理由：MVP 期不引入 `mypy` / `flake8` 以降低环境负担；
保证质量靠 **`pytest` + `REVIEW-CHECKLIST.md` 的红线逐条核对**。
若后续引入，命令应写入本节并同步 `docs/TechDesign-BCI-Decoder-MVP.md` 的 `commands`。

---

## 3. 技术栈构成

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.14.7 | 扁平布局，`python -m bci_decoder.cli` **免安装** |
| 数值 | NumPy / SciPy | `scipy.signal.sosfilt` 提供**因果滤波与状态保持** |
| 机器学习 | scikit-learn（LDA） | 小数据强基线 |
| 配置 | PyYAML | 所有参数集中在 `configs/*.yaml` |
| 持久化 | joblib | 模型存 `artifacts/*.joblib` |
| 测试 | pytest | 单元 + 端到端 |
| 实时通信 | websockets（✅ **已装并跑通**，17.2） | F5 |
| 设备接入 | pylsl（**未装**，④ 阶段） | 真实 LSL 流 |

**后期（里程碑 ③④）才考虑**：`mne`、`moabb`（公开数据集评测）、`pyriemann`（黎曼几何）。

---

## 4. 配置入口

所有可调参数集中在**单个 YAML**，交付时企业只改这一个文件。

| 文件 | 用途 |
|---|---|
| `configs/default.yaml` | 基线（用于准备演示模型） |
| `configs/demo_online.yaml` | 在线演示（`mock` 源） |
| `configs/demo_replay.yaml` | 伪在线回放（读 `.npy` 文件） |

切换数据源只需改 `source.kind`（`mock` / `replay` / `lsl`）。

---

## 5. 目录约定

```
bci-decoder/
├── bci_decoder/        # 包本体（types/config/buffer/core/cli/synth）
│   ├── pipeline/       # preprocess / features / classifier / postprocess
│   ├── sources/        # mock / replay / lsl
│   └── outputs/        # console / jsonl / websocket
├── configs/            # YAML 配置
├── scripts/            # bootstrap_demo.py / make_sample_data.py
├── tests/              # pytest
├── artifacts/          # 模型与输出产物（不入库）
└── data/               # 样本数据
```

---

## 6. 环境纪律

- **不要用全局 Python 跑测试**（没有 pytest）。
- **不要在仓库根跑 pytest**（会在根生成 `.pytest_cache/`）。
- **不要提交** `.venv/`、`__pycache__/`、`.pytest_cache/`、`artifacts/*.joblib`、大数据文件。
- 环境必须**4 名成员各自独立跑通**——"只有一个人会跑 = 没有人会跑"。

---

## 7. 与文档的口径（2026-10-15 已校准）

| 项 | 现状 |
|---|---|
| Python 版本 | **3.14.7**（`bci-decoder/.venv`）；`requirements.txt` 已声明 3.10+ 下限 |
| 依赖安装 | 核心依赖已装（`pytest` **17/17** 通过）；`websockets` ✅ **已装并跑通**（17.2，2026-10-16 F5.1 端到端）、`pygame-ce` ✅ 已装（2.5.8，**上游 `pygame` 无 Python 3.14 wheel**）；`pylsl` **未装**（里程碑 ④ 前必验） |
| 命令示例所在 shell | **PowerShell 5.1**，不能用 `&&`；文档围栏已由 ```bash``` 统一为 ```powershell``` |
| `bci-decoder/` 归属 | ✅ 已拍板（2026-10-15）：**本团队成果、计入项目进度** |
| `game/` 位置 | ✅ 已定案：`bci-decoder/game/` |

> 拍板前的历史评估见 `docs/Start项目落地评估.md` §5.1/§5.2（保留备查）。
