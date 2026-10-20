# A10 · 一小时稳定运行（soak）操作说明

> 日期：2026-10-20（D1）于 `docs/evidence/W9_1027/` 备料 · 作者：阎浩文
> 状态：**待执行**——需要你在场保持电脑唤醒约 1 小时（王释贤已跑过 5 分钟基线，正式一小时还没人跑）。

## 目的

证明解码端能**连续稳定跑 60 分钟**：内存有界（≈看 demo 正常 RSS）、无缓慢漂移/递增失败、8192 条历史容量有界、
耗时不劣化。属 A10 验收项之一入报告（真实数字：只报稳定性，不报准确率）。

## 操作（Windows PowerShell，cwd = `bci-decoder/`）

```powershell
# 单独一个终端，别关，电脑别睡眠
.venv\Scripts\python.exe -m bci_decoder.cli run --config configs\demo_online.yaml
#   ↑ demo_online.yaml 为 realtime 在线节奏；让它跑满 60 分钟
```

跑的同时，另开一个终端盯资源（每 5 分钟记一次日志顶到文件）：

```powershell
1..12 | ForEach-Object { Get-Process python | Select-Object Id,@{n='RSS_MB';e={[math]::Round($_.WorkingSet64/1MB,1)}},StartTime | Out-File "..\myworkoutputs\A10_soak\rss_$_.txt"; Start-Sleep -Seconds 300 }
```

## 跑完后归档

1. 解码器终端日志 → `docs/evidence/W9_1027/`（如 `A10_soak_20261020_阎浩文.log`）；
2. RSS 采样汇总 → `A10_soak_rss.csv`（判断：60 分钟 RSS 不持续上涨、峰值 ≤ 500MB 左右）；
3. 观察：决策按 ~0.5s 节奏持续输出无中断、无异常 traceback；尾部统计 `n/outputs` ≈ 120×12，`p95_ms` 与短跑同量级（不漂移）。
4. 顺手可跑 `demo_online.yaml` 同参数 benchmark 三次对照（短跑 vs 一小时尾段 p95 差异 < 2ms 即视为无劣化）。

## 红线

- 输出 9 字段冻结；全程 `label_id==-1 ⟺ label==idle`（soak 不额外报准确率）；
- 不喂 synth 数据作性能结论；本项只做“稳定性”证据。
