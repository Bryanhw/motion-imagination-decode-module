# M4 E1 brainda 交叉互证证据链 — 复现说明

> 内部工程记录，不对外报告准确率（红线）。口径：BCI Competition IV 2a（BNCI2014-001）公开数据集回放。
> 完成时间：2026-11-19（星期四）。

## 1. 目标

E1 互证（临时备忘录 M4 余力项）：用**独立数据加载库 brainda（metabci）**重跑 D1 校准实验，
验证 D1 的数字不依赖具体数据加载实现（MOABB vs brainda），并厘清两库 CSP 特征口径差异。

## 2. 运行身份与环境

- 实验/脚本维护：阎浩文（DeepWorks 代跑）
- 复现环境：`bci-decoder/.deepworks/venv_e1`（Python 3.14，metabci 0.2.0 / brainda / mne 1.13.2 / sklearn）
- 脚本：`bci-decoder/scripts/m4_e1_brainda_crosscheck.py`（brainda loader），
  临时分析脚本在 `.deepworks/tmp/e1_ab_csp.py` / `.deepworks/tmp/e1_ab_csp2.py` / `.deepworks/tmp/e1_mne_on_brainda.py`
- **跨库对比细节**：MOABB 数值来自 `e1_dump_moabb_{0train,1test}.npy(_y)`，
  brainda 数值来自 `e1_dump_brainda_{0train,1test}.npy(_y)`（跨 venv 经 npy 中转）

## 3. 关键发现一：E1 旧 loader 缺 8–32 Hz 带通（已修复）

- MOABB `MotorImagery` 范式默认带 `filters=[[8, 32]]`，在切 epoch **之前**对 raw 做
  `raw.filter(8, 32, method="iir", picks="data")`（moabb/paradigms/motor_imagery.py L217-230；
  datasets/preprocessing.py `get_filter_pipeline` L1066-1089）。
- E1 旧加载路径漏了这一步，导致 brainda epoch 与 MOABB epoch 数值量级差约 3×、Kappa 偏低。
- **修复**：`m4_e1_brainda_crosscheck.py` 的 `raw_to_epochs_22ch` 在 find_events 前补
  `raw.copy().filter(l_freq=8, h_freq=32, method="iir", picks="data", verbose=False)`。
- **修复后逐元素一致**：brainda 与 MOABB 切出的 0train/1test 全 session（A01T run3-8）拼接后
  `max|X-Xm| = 0.0000e+00`、`mean = 0`、`y aligned = True`（数据 shape 均为 (144, 22, 1001)）。

## 4. 关键发现二：同一管道下 brainda loader 逐位复现 D1

脚本：`e1_mne_on_brainda.py`（brainda loader + 与 D1 相同的 mne CSP(n_components=4, log=True) + LDA(lsqr, auto)，
个人校准为受试自身前 N/类 trial 独立建 CSP+LDA）。

| 口径 | E1（brainda loader） | D1 基准（MOABB loader） | 差值 |
|---|---:|---:|---:|
| nocal（8人LOO） | 0.1914 | 0.191 | +0.0004 |
| 校准 N=10/类 | 0.2690 | 0.269 | +0.0000 |
| 校准 N=20/类 | 0.3642 | 0.364 | +0.0002 |
| 校准 N=30/类 | 0.3529 | 0.353 | −0.0001 |

**逐受试逐口径 kappa 与 `matrix_csp.csv` 全 diff=0**（见 `e1_cmp_csv.log`）：

| subj | nocal | cal10 | cal20 | cal30 |
|---|---:|---:|---:|---:|
| 1..9 | 全 +0 | 全 +0 | 全 +0 | 全 +0 |

**结论：数据加载层与 D1 完全可互换，D1 数字不依赖 MOABB；E1-loader 互证成立。**

## 5. 关键发现三：brainda 原生 csp_feature 与 mne CSP 的算法语义差异（非 bug）

单独把 CSP 层换成 brainda 原生 `csp_kernel + csp_feature`（`matrix_brainda_csp.csv`）后数字偏低
（nocal 均值 −0.083 vs D1 0.191）。A/B 隔离诊断（`e1_ab_csp2.py`，同批 brainda epoch）归因：

| 变体 | nocal 均值 | 说明 |
|---|---:|---|
| A mne CSP(4,log) | **+0.191** | = D1（复现） |
| B brainda csp_feature(4) | −0.083 | 每 trial 按总功率归一化后再 log + 仅取前 4 列 |
| C brainda W 前2+后2（经典对称取列） | +0.235 | 补对称取列后差异大幅缩小 |
| D brainda W 前4 log（不做功率归一化） | −0.017 | 归一化是主要差异源之一 |

根因（代码级）：
- brainda `csp_feature`（csp.py L82-121）：`W[:, :n_components].T` 投影 → 均方功率 →
  **除以该 trial 总功率(+eps) 归一化** → log。
- mne CSP（decoding/csp.py L268-275）：`filters_[: n_components]`（按特征值降序取前 4）→
  均方功率 → **直接 log（无逐 trial 功率归一化）**。
- 两者还存在求解器差异（brainda 用 `eigh(C1, Cc)` + nearestPD；mne 用协方差矩阵正则化 + 特征分解），
  以及取列策略差异（brainda 一律前 4 列，经典 CSP 惯例是前 2 + 后 2 对称）。

**结论：差异来自两库 CSP 特征构造语义不同，属已定位的算法差异，不是加载/管道 bug。**
互证成立靠 §4（同管道换 loader 逐位一致）+ §3（epoch 级逐元素一致）两条证据线。

## 6. 附件

- `matrix_e1_brainda_loader.csv`：E1-loader 互证矩阵（brainda loader + mne CSP/LDA，与 D1 diff=0）
- `matrix_brainda_csp.csv`：brainda 原生 csp_kernel+csp_feature 管道矩阵（算法语义对照用，非 D1 复现口径）
- `matrix_csp.csv`：D1 基准（MOABB loader，见 `../M4_calibration_20261117/`）
- 支持日志：`.deepworks/tmp/e1_mne_on_brainda.log`、`e1_ab_csp2.log`、`e1_cmp_csv.log`

## 备注

- 红线遵守：不对外报告准确率；本轮全部为公开数据集回放。
- 与 D1 口径完全一致（滑窗 2.0 s / 0.5 s、CSP+LDA、窗口级 Kappa、校准仅用 session1 前 N/类、测试统一 session2）。
