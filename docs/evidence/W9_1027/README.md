# W9_1027 验收证据目录（里程碑② 收口）

> 索引：A1–A11 逐条指向证据文件。更新日期 2026-10-22。
> 依据：`agent_docs/testing.md` §5 验收清单、`docs/M2冲刺作战清单.md`。
> **注意**：M2 评审日已由 10/27 **推迟至 10/31**（2026-10-22 组内通知）；本目录编号 `W9_1027` 作为里程碑②证据包代号**沿用不改**，其中"评审前 24 h 齐备"的死线相应顺延至 **10/30**。

## A1–A11 状态速查

| 验收项 | 内容 | 状态 | 证据 |
|---|---|---|---|
| **A1** | 4 名成员各自独立跑通 | 🔶 队长四份终端日志已归档（差游戏窗口截图 1 张）；阎浩文/黄凯森 D1 证据待挪入 `A1/`；王释贤待跑 | [A1/](./A1/)（`A1_蓝喜阳_*.txt`：解码 31 passed、游戏 25 passed、bootstrap、demo_online 200 块） |
| **A2** | 解码单元 pytest | ✅ 2026-10-21（31/31：22 旧 + 9 OOD）；2026-10-22 复跑确认 **31 passed** | `00_测试报告/解码端_pytest_20261022_阎浩文.txt`（20261021 OOD31 版与 junit 同目录） |
| **A3** | 链路现场验证（回放跟上类别切换、持续输出 ≥ 2 分钟） | ✅ 2026-10-22（demo_replay_switch 2400 块 / 480 决策 / 覆盖 240 s 数据流） | [A3_链路验证录屏.mp4](./A3_链路验证录屏.mp4)、[决策log](./A3_链路验证_决策log_20261022_阎浩文.txt) |
| **A4** | benchmark 正式实测 | ✅ 2026-10-21（本机 δ p95 0.955ms，3 取中位，见文件内口径声明，勿与他机直接比较） | [01_延迟/A4_benchmark_20261021_dfd9dfc.txt](./01_延迟/A4_benchmark_20261021_dfd9dfc.txt) |
| **A5** | 延迟分解演示页 | ✅ 2026-10-21（只报延迟，不报准确率） | [01_延迟/A5_延迟分解演示页.html](./01_延迟/A5_延迟分解演示页.html)（自包含单文件，可脱网打开）；配套图 [00_测试报告/latency_breakdown.png](./00_测试报告/latency_breakdown.png)（2026-10-22 更新为 A4 本机口径 0.955ms） |
| **A6** | 稳定化演示（弱信号/模型缺失 → 恒 idle，不随机） | ✅ 2026-10-22 复跑：demo_weak **40/40 idle**、demo_nomodel **40/40 idle**（早期 200 决策版亦归档） | `T4_稳定化素材/demo_weak_恒idle_20261022_阎浩文.log`、`T4_稳定化素材/demo_nomodel_恒idle_20261022_阎浩文.log`、`T4_稳定化素材/demo_nomodel_200decisions.log` |
| **A7** | 联调录屏 | ✅ 合成数据工程联调录屏完成；真人脑控仍待 A8 | [A7_联调录屏_ws.mp4](./A7_联调录屏_ws.mp4)；[核验记录](./WS_契约自检/A7_WebSocket联调工程验证_20261022.md) |
| **A8** | 真人现场演示 | ❌ 未做（F4 验收关键） | |
| **A9** | 启动到出结果 ≤ 3 min | ✅ 2026-10-21 自检 2.1 s | [01_延迟/A9_启动计时_20261021.txt](./01_延迟/A9_启动计时_20261021.txt) |
| **A10** | 连续 1h 长跑 + 断线重连 | ✅ 2026-10-21 全部完成 | `A10_断线重连演练.json`、`A10_长跑日志.txt`（本目录） |
| **A11** | 本证据目录 README 索引 | ✅ 2026-10-21 本文件建立 | |

## 其他归档

- `00_测试报告/`：解码端/游戏端 pytest 汇总（解码端 **31/31**【2026-10-22 复跑】、游戏端 **72/72**【2026-10-22】）、benchmark（阎浩文 1.339ms）、延迟分解图 `latency_breakdown.png`（2026-10-22 更新为 A4 本机口径 **0.955ms**，计算占比≈0.0478%，只报延迟）
- `01_延迟/`：A4（本机 0.955ms）、A9（2.1s）；王释贤 1.849ms 与阎浩文 1.339ms 证据见 00_测试报告 与各自提交，三机口径不得互比，正式展示数字由统一演示机复测定
- `T4_稳定化素材/`：demo_nomodel 全 idle 稳定性回放（早期 200 决策 log + 2026-10-22 复跑 demo_weak/demo_nomodel 各 40 决策，均全 idle）
- `WS_契约自检/`：WS 协议契约自检（王释贤）
- `2c_改进提案/`：OOD 低置信机制改进提案（D1）、实施细化（D2）、**落地实现记录 D3**（2026-10-21，pytest 31/31 含 9 OOD，提交 b58525f，附待组长拍板清单）、**拍板回填 D3 §6**（2026-10-21 晚，**8/8 全部通过**，含灰度扩展与规格书 v1.1.4 授权）、**灰度扩展回归 D5**（demo_online + demo_replay_switch 同参启用 OOD 后各重跑一次，随附 log ×2；demo_online 域内零误杀、demo_replay 空闲边变宽属保守口径）
- `D1_*.md`：各成员 D1 验收相关文档

## 演示样本与公开 EDF

`*.npy` 回放转换结果与模型仍不入库（见 `.gitignore`）。用户已要求把找到的公开 EDF 测试数据一并推送；未经修改的原始文件和来源说明位于 `bci-decoder/data/eegmmidb_s001/`。三段合成演示 replay 样本仍可在 `bci-decoder/` 目录下一键重建：

```powershell
# demo_replay.yaml        —— 连续段（也是 demo_replay_switch.yaml 的样本，哈希与旧 sample_switch.npy 一致）
python scripts/make_sample_data.py --out data/sample_continuous.npy --seconds 60 --label-period 4

# demo_weak.yaml         —— 弱信号（低信噪比；--snr-db 越小信号越弱）
python scripts/make_sample_data.py --out data/sample_weak.npy --seconds 60 --label-period 4 --snr-db -6
```

> 注：2026-10-21 已把 `demo_replay_switch.yaml` 的样本统一指向可重建的 `sample_continuous.npy`（旧 `sample_switch.npy` 与其哈希相同，属冗余文件，不再生成）。

真实 EDF 回放的格式转换命令和注意事项见 [`bci-decoder/game/platformer/README.md`](../../../../bci-decoder/game/platformer/README.md#用本地-physionet-edf-做回放联调)。

## 待补（评审前）

- [x] A5 延迟分解演示页（完成 2026-10-21 → `01_延迟/A5_延迟分解演示页.html`）
- [x] A3 链路验证录屏（2026-10-22：决策回放 mp4 + 480 决策 log，覆盖 240 s）
- [x] A6 稳定化演示（2026-10-22：demo_weak / demo_nomodel 各 40/40 恒 idle）
- [x] A7 合成数据联调录屏（修复版，2026-10-22）
- [ ] A8 真实现场演示（聚齐后录）
- [ ] A1 其余 3 名成员跑通截图
