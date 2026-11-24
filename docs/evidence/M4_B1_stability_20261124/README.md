# B1 稳定性验收：replay 30min 长跑证据（2026-11-24）

## 结论

**PASS** —— replay 源 + realtime 真实节奏连续运行 ~34.9 分钟（数据时间戳 2091.5 s），无崩溃、无 error、内存不增长、计算延迟远低于预算。

## 验收口径（来源 `MVP规格说明书.md` §F4/§N2、`最终汇报前任务总览_20261119.md` B1）

- 连续运行 **≥30 分钟**无崩溃（进程不退出、无 traceback/CRITICAL）；
- 计算耗时 **p95 < 50 ms**；
- **1 小时内存不持续增长**（本跑采样 ~35 分钟内 RSS 稳定）。

## 环境

- 主机：Windows PowerShell 5.1；解释器 `.venv\Scripts\python.exe`（venv）。
- 配置：`bci-decoder/configs/demo_soak_replay.yaml`（replay 源 `data/sample_continuous.npy`，loop: true，realtime: true，speed 1.0，250 Hz，8 通道 C3..Oz）。
- 命令：`python -m bci_decoder.cli run --config configs/demo_soak_replay.yaml`（**未传 --chunks**，保持真实节奏）。
- 运行时段：约 09:04:09 启动 → 09:47:56 停止（墙钟 ~44 min，期间包含进程清理；数据时间戳累计 2091.5 s ≈ 34.9 min 真实回放节奏）。
- 原始日志（不入库，痕迹件）：`bci-decoder/artifacts/soak/B1_replay30min/B1_replay_20261124_090409.log`（4185 行）。

## 原始统计（由日志解析）

| 指标 | 数值 | 预算/门槛 | 判定 |
|---|---|---|---|
| 数据时间戳（真实节奏） | 2091.5 s（≈34.9 min） | ≥1800 s（30 min） | ✅ |
| 决策输出行数 | 4183 条 | 约 30min/0.5s ≈ 3600 量级 | ✅ |
| compute p50 | 1.6 ms | — | — |
| **compute p95** | **3.7 ms** | **< 50 ms** | ✅ |
| compute p99 | 4.3 ms | — | — |
| compute max | 159.2 ms（单点尖峰，可能来自首帧/GC/调度） | — | 不影响 p95 口径 |
| error / traceback / CRITICAL | 0 处 | 无 | ✅ |
| 进程状态 | 全程存活，结束时由审计主动停止 | 不崩溃 | ✅ |
| 内存 RSS | ~54–73 MB 区间波动，无单调增长 | 不增长 | ✅ |
| 输出消息 | 每行含 t_data/…/label/conf/probs/state，字段与冻结契约一致 | 字段不得增删 | ✅ |

## 备注（诚实性）

- 本验收用 **replay 回放数据**（`sample_continuous.npy`），属工程自检链路；**不构成任何算法性能/准确率证据**（红线 4/5/6）。
- max=159.2 ms 为单点极端尖峰，非持续状态；验收口径为 p95，结论不受影响。若需更严苛结论可扩大样本（1h soak mock 证据另见 A10 `docs/阎浩文X8_M4mock稳定长跑_soak冒烟凭证_20261112.md`）。

## 痕迹与产出

- 配置：`bci-decoder/configs/demo_soak_replay.yaml`
- 日志：`bci-decoder/artifacts/soak/B1_replay30min/B1_replay_20261124_090409.log`
- 本证据：`docs/evidence/M4_B1_stability_20261124/README.md`