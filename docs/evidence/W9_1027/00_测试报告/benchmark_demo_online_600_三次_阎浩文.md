# T5 测试证据归档说明（阎浩文，2026-10-20）

> 用途：为 A2「测试证据」提供本机可独立复现的原始 pytest 证据（pytest 在无终端环境会把总结
> 行写到 stderr/被缓冲吞掉，因此**精确计数以 junit XML 为准**，进度 txt 仅作过程留档）。
> 红线：本文与 junit 均不含准确率字段或准确率数字，demo 数据仅作工程自检。

## 1. 文件清单（`docs/evidence/W9_1027/00_测试报告/`）

| 文件 | 内容 | 关键口径 |
|---|---|---|
| `解码端_junit_阎浩文.xml` | pytest junit（`tests/`，bci-decoder 根） | `tests=22 errors=0 failures=0`（time≈3.2s，host LAPTOP-FAS37C8L） |
| `解码端_pytest_20261020_阎浩文.txt` | 同次 `pytest -q` 进度输出 | rc=0；22 项满点无失败 |
| `游戏端_junit_阎浩文.xml` | pytest junit（`game/tests`） | `tests=39 errors=0 failures=0`（time≈5.5s） |
| `游戏端_pytest_20261020_阎浩文.txt` | 同次 `pytest -q game\tests` 进度输出 | rc=0；39 项满点无失败 |
| `benchmark_demo_online_600_三次_阎浩文.md` | 正式三次延迟基准汇总 | p95 中位数 1.339 ms |

复现命令（`bci-decoder/` 下，Python `bci-decoder\.venv`）：

```powershell
.venv\Scripts\python.exe -m pytest --junitxml="<输出>/解码端_junit_阎浩文.xml" -q
.venv\Scripts\python.exe -m pytest --junitxml="<输出>/游戏端_junit_阎浩文.xml" -q "game\tests"
```

## 2. 延迟基准（正式三次，demo_online / 600 chunks）

命令（与王派同口径）：

```powershell
.venv\Scripts\python.exe -m bci_decoder.cli benchmark --config configs/demo_online.yaml --chunks 600
```

| 次数 | n | mean_ms | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|
| 1 | 120 | 0.738 | 0.593 | 1.339 | 6.845 |
| 2 | 120 | 1.366 | 1.075 | 2.179 | 8.253 |
| 3 | 120 | 0.857 | 0.724 | 1.287 | 6.302 |
| **中位数** | 120 | 0.857 | 0.724 | **1.339** | 6.845 |

口径说明：
- 三次在同机同配置下取 **p95 中位数 = 1.339 ms**；window_seconds=2 → est_e2e_p95≈2001–2002 ms（契约节奏 0.5s/块不受影响）。
- 与王派 p95 中位 1.849 ms **不同机不可直接比**，统一口径 = 同一配置×3 取中位（各自记录）；本份归属本人运行记录，**不覆盖**王派 `docs/evidence/W9_1027/01_延迟/`。
- 三次均值 0.738/1.366/0.857 ms，均远低于 500ms 步长预算，留足余量。

## 3. 结论

解码端 **22/22**、游戏端 **39/39**、正式三次延迟 p95 中位数 **1.339 ms** —— 均以可复现命令 + junit 为准记入本目录。
（补空文档 §6 待办 ③「正式三次 benchmark」至此销账；待办①②④⑤继续。）
