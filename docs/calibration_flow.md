# 校准流程（Skeleton）设计说明

> 状态：**骨架（里程碑②范围内）** —— 流程、接口、脚本已落地，可用 mock/synth 数据端到端跑通；
> **真实采集 → 训练 → 试玩**的完整闭环是里程碑④（12/01）的内容，本文件同时给出④的接入点与契约映射，避免届时推倒重来。
>
> 依据：`docs/脑控游戏方向专题建议.md` §5.2（校准必须设计进游戏）、`docs/MVP规格说明书.md` §4.4（冻结契约
> 含 `calibrate` / `load_subject`，MVP 仅响应 `start`/`stop`，其余**忽略并记日志**）、`MEMORY.md`（M2 主攻项）。

---

## 1. 为什么需要校准

在线解码用到的 **CSP 空间滤波器 W 与 LDA 分类器是人相关的**：
- 同一套模型在不同个体、不同电极佩戴位置上的可分性差异很大；
- 直接用"别人的模型"首玩，准确率可能不稳定，导致游戏体验崩塌（更难判断是用户没想法还是电极信号问题）。

因此**每位新用户首次使用前，应走一遍"采集 → 训练 → 质量门 → 试玩"**，生成该用户自己的模型，
后续可通过**迁移/微调**缩短校准时间（详见 §6 演进路线）。

---

## 2. 里程碑范围界定（避免范围蔓延）

| 里程碑 | 校准范围 | 说明 |
|---|---|---|
| **②（本骨架，10/27）** | **流程骨架 + 接口 + 脚手架脚本** | 已有 `bootstrap_demo.py` 的"trial→训练→保存"链路，本骨架把"采集数据 → 按用户分目录出模型 → 生成可运行配置"串成一步；真实采集由 mock/synth 占位。**不含** LSL 实录、引导页 UI、在线自适应微调。 |
| **④（12/01）** | 完整校准：引导页 → 2–3 min 采集（20–30 trial/类）→ 训练/加载 → 试玩 → 质量不满则重校准 | 接真实设备（LSL），实现 `calibrate` / `load_subject` 真实语义 |

**红线在本骨架同样适用**：mock/synth 数据只用于工程自检，**不得用于评估算法性能或对外报告准确率**（红线 5、6）。

---

## 3. 总体流程（对照专题建议 §5.2）

```
进入游戏/解码启动前
   │
   ├─ 已有该用户模型？ ──► 复用（load_subject），可选做轻量微调（④）
   │        │ 否
   │        ▼
   │  ① 引导页（30s 说明：想象左手 = 左移，想象右手 = 右移，倒计时提示）   [④：游戏内 UI]
   │        ▼
   │  ② 校准采集（2–3 min，每类 20–30 个 trial，屏幕提示 + 倒计时 2.0s/trial）  [④：真机 LSL 实录]
   │        ▼
   │  ③ 数据落地试（②→③ 由采集脚本切 trial）：
   │        artifacts/users/<subject_id>/raw/*.npy   # (n_ch, n_t) 连续段 + labels.npy
   │        ▼
   │  ④ 训练/加载分类器：
   │        python scripts/calibrate.py --subject-id <id> --real-data ... --labels ...
   │        ▼
   │  ⑤ 质量门（详见 §5）：交叉验证（仅工程自检参考）+ 基线 sanity check
   │        ▼
   │  ⑥ 产出（按用户分目录）：
   │        artifacts/users/<subject_id>/classifier.joblib
   │        artifacts/users/<subject_id>/csp.joblib          # 仅 kind=csp 时
   │        artifacts/users/<subject_id>/online.yaml         # 可直接被 cli run 加载的配置
   │        ▼
   ├─ 启动在线解码：
   │        python -m bci_decoder.cli run --config artifacts/users/<subject_id>/online.yaml
   ▼
  试玩 1 局 → 若体验差（大量误判/同侧不动）则提示重校准或降难度（④：游戏内策略）
```

> 骨架阶段 ②③⑤ 由脚本用 mock/synth 数据模拟、占位并打印"此处真机校验需要做什么"，
> 保证**接口与目录结构**先定型；④ 时只替换"采集"与"引导"两块，训练脚本无需大改。

---

## 4. 冻结契约映射（不破坏现有 MVP 行为）

冻结契约（规格书 §4.4）含 `start/stop/calibrate/load_subject` 四条；MVP 仅响应前两条，后两条**忽略并记日志**。
本骨架不对契约做任何改动，只约定 **④启用时的映射**，避免到时破坏既有客户端：

| 控制消息 | MVP 行为（保持现状） | ④ 启用后的建议语义 |
|---|---|---|
| `start` | 开始流式解码 | 不变 |
| `stop` | 停止 | 不变 |
| `calibrate {"seconds":120}` | 忽略 + 记日志 | 进入"校准采集"子状态：接收端只做窗口缓冲与 trial 计时、落盘 trial，**不产决策**；期间由交互式 UI 引导用户 |
| `load_subject {"subject_id":"alice"}` | 忽略 + 记日志 | 切换 classifier/csp/配置到 `artifacts/users/alice/` 下对应模型；`subject_id` 未知则保持 `idle` 并记日志（红线 1） |

**约定**：④ 启用时必须**对 `calibrate` / `load_subject` 的无效输入保持 `idle` 且不断链**，
与现有"未知消息记日志不崩溃"的行为一致。此约定写入验收。

---

## 5. 质量门（骨架阶段的边界）

> ⚠️ **MVP 阶段不对外报告任何准确率数字**；下述数字仅作**工程自检**（确认数据携带可分信息 / 链路没断）。

骨架阶段质量门 = 两步，全部基于脚本内部输出：

1. **交叉验证**（沿用 `bootstrap_demo.py`）：CSP+LDA 5 折 CV。目的仅是确认"这次采集的数据里确有可分结构"，
   不是性能分。**结果只写日志，不进任何对外交付物**。
2. **链路 sanity**：`calibrate.py` 生成的 `online.yaml` 能被 cli 完整 `run` 且输出合法心跳（见 §7 验证）。

④ 阶段再加入：

3. **试玩门**：真人试玩 1 局后按"误判数 / 反应时间"作定性门（准确率过低 → 提示重校准或降难度，专题建议 §5.2）。
   这条始终是**定性/体验**门，仍不对外报数字（红线 6）。

---

## 6. 演进路线（为④及其后铺路，不属本次范围）

- **在线自适应微调**（专题建议 §5.2）：用游戏中的同侧真实片段做轻量更新，抵抗跨次漂移。
  脚手架已预留 `--fine-tune` 参数位与"加载已有模型"路径，④实现。
- **跨被试迁移 / 减少校准时间**：`features.py` 已实现 `euclidean_align`（欧氏对齐）。新用户只采少量 trial，
  对齐到公共参考协方差后再微调 CSP/LDA。④可先验证对齐 + 少量试。
- **按用户目录组织**（本骨架已定型）：`artifacts/users/<subject_id>/` 天然对接 `load_subject`，
  多用户低成本并存，避免重复训练。

---

## 7. 骨架可运行验证（工程自检）

```powershell
# 在 bci-decoder 目录下（PowerShell 5.1，不用 &&）
# ① 骨架脚本：用 synth 数据为 "demo" 用户生成模型 + 配置
.venv\Scripts\python.exe scripts\calibrate.py --subject-id demo

# ② 用生成的 online.yaml 启动在线解码（mock 源，2s 窗），确认链路通
.venv\Scripts\python.exe -m bci_decoder.cli run --config artifacts\users\demo\online.yaml --chunks 40

# ③ 若接入真实采集数据（.npy + labels.npy）：
.venv\Scripts\python.exe scripts\calibrate.py --subject-id alice --real-data data\alice_raw.npy --labels data\alice_labels.npy
```

真实采集数据格式约定（与 `bootstrap_demo.py --real-data` 一致）：

- `raw.npy`：`(n_channels, n_t)` 连续原始 EEG（或已按 trial 对齐的矩阵，需配 labels）
- `labels.npy`：每个 trial 的类别标签，长度 = trial 数；标签取值 ∈ `config.classifier.classes`（如 `left/right`）
- 通道顺序必须与 `source.ch_names` 一致（`C3, Cz, C4, CP3, CP4, P3, P4, Oz`）——**红线 4，不得重排**