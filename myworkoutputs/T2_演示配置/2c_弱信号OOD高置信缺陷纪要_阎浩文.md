# T2c 弱信号演示：OOD 高置信缺陷调查纪要（阎浩文，2026-10-20）

> 本文档如实记录 `demo_weak.yaml` 无法达成“弱信号→稳定 idle”的原因，
> 定位为**核心模型缺陷**并上报；合成数据仅用于工程自检，不含任何模型准确率口径。

## 一、T2 任务状态（截至本纪要）

| 条目 | 内容 | 状态 |
|---|---|---|
| 2a | `data/sample_switch.npy`（8×15000，60s，label-period 4s 左右交替）| ✅ 完成 |
| 2b | `configs/demo_replay_switch.yaml`；`--chunks 240` | ✅ 左/右规律交替（切换边界出现短暂 idle，符合安全逻辑）|
| 2c | `configs/demo_weak.yaml`；`--chunks 200` | ⚠️ **未达标·核心缺陷阻塞** |
| 2d | `configs/demo_nomodel.yaml`；`--chunks 200` | ✅ 40/40 决策全部 `idle`，无任何 left/right，不崩 |

验证命令（均 `bci-decoder/` 下，rc=0）：
```
python -m bci_decoder.cli run --config configs/demo_replay_switch.yaml --chunks 240
python -m bci_decoder.cli run --config configs/demo_weak.yaml --chunks 200
python -m bci_decoder.cli run --config configs/demo_nomodel.yaml --chunks 200
```
证据日志：`myworkoutputs/T2_演示配置/2b_*.log`、`2d_*.log`；`2c_weak.log`（40 决策中仅 2 idle，38 right）。

## 二、现象（实证复现）

用同一个 `demo_csp.joblib + demo_lda.joblib`（bootstrap 产物）对以下合成输入逐个验证：

| 输入形态 | 决策计数（20s≈40 条窗口决策） | 观察 |
|---|---|---|
| 纯噪声 std 25µV | 37~38 right / 2~3 idle，conf≈0.96~1.00 | **噪声也被判 right 高置信** |
| 低幅同相信号（无 C3/C4 差异） | 同上 | 同上 |
| 弱交替（幅值 0.5~2µV、噪声 15/25µV、周期 0.25/0.5/4s） | 全部 38 right / 2 idle | 强度参数不影响输出 |
| 持续单侧弱结构（增益差 0.01~0.2） | 与随机种子相关：seed9 出现 13 idle，seed13 则 2 idle | idle 由噪声偶然性驱动，不可控 |
| 纯左 / 纯右强信号（对照） | left/right 判别正确 | **模型本身有判别力，问题仅在分布外** |

## 三、根因分析

1. **CSP 特征对强度的盲区**：CSP 提取的是 `log(归一化方差)`——通道功率整体缩放/噪声水平被归一化抹掉，
   纯噪声与低信噪比信号在特征空间里的落点相近。
2. **LDA 对分布外输入不降置信**：训练分布外（OOD）的特征仍被线性超平面武断分到一侧，
   sklearn `predict_proba` 归一化后给出接近 0/1 的极端概率 → 超过 `min_confidence 0.6` 门限 → 输出指令。
3. 因此“弱信号→conf 低→idle”依赖特征恰好落在决策边界两侧的随机性，无法稳定构造。

## 四、与红线的关系

本项目红线：**未训练 / 模型缺失 / 置信度不足 → 必须 idle，绝不给游戏发随机指令。**
当前模型对**任意陌生输入仍然高置信输出指令**，等于“模型缺失时不落 idle、把噪声当特征”，
与红线精神直接冲突（尽管 2d 的 `kind: untrained` 兜底是好的，但已训练模型的 OOD 段没有等价兜底）。

## 五、处置与建议（上报队长 / 核心负责人）

- T2c **本次按“未达标·已被核心缺陷阻塞”交付**，配置保留为实验配置，不宣称达标。
- 建议另立核心改进任务（不在 T2 范围内擅自改核心，符合 `docs/MVP规格说明书.md` §9 变更流程）：
  1. 上线**OOD/低置信判据**：例如 LDA 到决策边界的归一化距离门限、或对 `predict_proba` 做置信校准；
  2. 或对特征域加“可靠区”判定（如通道能量/方差合理范围、CSP 特征流形内距离）；
  3. 改进后：回到本纪要用 `--chunks 200` 复验弱信号→全程 idle。
- 附：探测脚本备份在 `myworkoutputs/T2_演示配置/_work/`，可复现上表。

## 六、附件清单

- `_work/t2_probe_weak.py`：候选形态探测（A~E）
- `_work/t2_probe2.py`：判别力/OOD 对照（pure L/R、weak right、split）
- `_work/t2_scan_weak.py`、`t2_scan_weak2.py`：参数网格扫描（强度×结构×种子）
- `_work/t2_verify_logs.py`：日志 label 序列统计
- `2c_demo_weak_200chunks.log`：2c 实测日志（未达标）
