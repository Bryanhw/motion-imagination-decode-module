# P1 风险预案 · 排查记录（2026-11-17 夜，阎浩文 / DeepWorks 代跑）

> 触发条件（任务卡 §3 P1）：**小样本（N=10/类）学出来不稳** + 个别受试校准后无增益。
> 处置：按预案先加正则化，再试迁移校准；**两条都记录了数字**（“我们排查过”的证据）。
> ⚠️ 本记录为 P1 对照，**不替换 / 不修改主线证据**（`../matrix_csp.csv`，个人专属 CSP+LDA 口径）。

## 1. 为什么触发 P1

主线矩阵（窗口级 Kappa，同一 session2 测试集）中存在三类不稳样本：

| 现象 | 受试 | 具体数字 |
|---|---|---|
| N=10 档 极端负值 | S09 | cal10 = −0.130（免校准 −0.009） |
| 校准后贴零 | S05 | nocal +0.023 → cal10 −0.014 / cal20 0.000 / cal30 0.000 |
| 校准无增益（稳但不增） | S06 | nocal +0.153 → cal10 0.120 / cal20 0.139 / cal30 0.093 |
| 校准后在零附近 | S02 | nocal −0.037 → cal20 +0.069 仍≈0 |

→ 归类：**校准无明显增益的受试 = S02 / S05 / S06**（与 README §4 和发群文案统一口径）。

## 2. 第一路：加正则化（CSP 协方差收缩）

- 方法：`m4_calibration.py --csp-reg ledoit_wolf`（CSP 对类协方差用 Ledoit-Wolf 收缩），全 9 人窗口级重跑。
- 结果（均值）：免校准 +0.191（同主线）／ cal10 +0.267 ／ cal20 +0.367 ／ cal30 +0.354
  → 与主线（0.269 / 0.364 / 0.353）**几乎完全一致（Δ≤0.004）**；
  → 关键个体原样：S05 仍 0.00、S09 N10 仍 −0.139、S02 仍≈0、S07 N30 仍 0.032。
- 结论：**加 CSP 收缩几乎零影响**。原因：校准档是窗口堆叠样本（N=20/类→40 trial×多窗），
  协方差估计已不病态，收缩无可用空间。附 `matrix_csp_reg_ledoitwolf.csv` / `gradient_csp_reg_ledoitwolf.png`。

## 3. 第二路：迁移校准（全局空间 + 个体线性判据，轻量版）

- 方法：`m4_calibration.py --p1-migrate`——CSP 空间**只在 8 人 0train 全局数据上 fit**，
  个人校准数据仅用于 fit 线性 LDA（“全局空间打底 + 个体判据”，MEKT 思想的最简版）。
- 结果（均值）：cal10 +0.182（**低于免校准 0.191**）／ cal20 +0.238（Δ+0.046）／ cal30 +0.248（Δ+0.057）
  → **整体劣于个人专属 CSP+LDA（0.269 / 0.364 / 0.353）**；
  → 关键个体更差：S03 从 0.81 崩到 0.02~0.18、S08 从 0.84 掉到 0.78、S02/S05 仍为负。
- 结论：**8 人全局空间不足以刻画单个受试的可分性**（跨受试差异真实存在），作为主线替代不可行。
  附 `matrix_csp_migrate.csv` / `gradient_csp_migrate.png`。

## 4. 结论与留档

1. **个人专属 CSP+LDA（主线）已是当前自研管线的最优口径**：正则化无空间、简单迁移更差，均不替换主线。
2. S02 / S05 / S06 属于**受试固有信号弱**（公开文献 BCI IV 2a 中即属高难/低信噪比样本），非流程问题；
   如实呈现 + 本排查记录即是“排查过”的证据。
3. 后续可选（未在本轮执行，留给需要时）：
   - 叙事可补 **trial 级 3 窗投票**口径（通常更高，M3 已用同思想）抬升这类个体观感——README §4.1 第 4 点；
   - E2 余力项：更精细迁移（MEKT / LST，brainda）仅作内部对照，不替代主口径；
   - 若 S05/S02 进入演示选样，可优先选“代表性达标受试”（S08/S03/S09/S01）讲主叙事，低落个体放逐受试明细。

## 5. 复现命令

```powershell
$env:PYTHONPATH = "D:/校企合作项目/bci-decoder"
# 第一路
& '.deepworks/venv_m3/Scripts/python.exe' -B bci-decoder/scripts/m4_calibration.py `
    --subjects 1..9 --csp-reg ledoit_wolf --out-dir <写出目录>
# 第二路
& '.deepworks/venv_m3/Scripts/python.exe' -B bci-decoder/scripts/m4_calibration.py `
    --subjects 1..9 --p1-migrate --out-dir <写出目录>
```

附件（本目录）：`matrix_csp_reg_ledoitwolf.csv` ／ `gradient_csp_reg_ledoitwolf.png` ／ `matrix_csp_migrate.csv` ／ `gradient_csp_migrate.png`。
