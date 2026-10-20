# T4 · 稳定化演示素材 — demo_nomodel（模型缺失 → 恒 idle）

> 日期：2026-10-20（D1）· 作者：阎浩文 · 归属：MVP v3 §6 A6（安全演示素材）
> 状态：✅ 解码台面素材完成；画面截图/录像待游戏端对接后补（不依赖解码端，见备注）

## 1. 演示目的

对应红线 #1/#2：**“未训练 / 模型缺失 / 置信度不足 → 必须输出 idle，绝不给游戏发随机左右指令”。**

本例证明 **“模型缺失 = 系统变哑巴”**：分类器未接任何已训练判别模型（`classifier.kind=untrained`，
两类给出均匀概率 0.5/0.5），配对 `postprocess.min_confidence=0.6` 门限 → 每一条决策都是 `idle`。

## 2. 配置与机制

- 配置：`bci-decoder/configs/demo_nomodel.yaml`
- 数据源：mock（250 Hz，8 通道 `C3,Cz,C4,CP3,CP4,P3,P4,Oz`，seed=0）
- 特征：bandpower（mu/beta）
- 分类器：`kind: untrained`（均匀先验 0.5/0.5）
- 门限：`min_confidence: 0.6` → 0.50 < 0.60 ⇒ 全 idle
- 窗口：window 2.0s / step 0.5s（冻结不可改）

## 3. 复现命令

```powershell
# 在 bci-decoder/ 下执行（Windows PowerShell 5.1，不用 &&）
.venv\Scripts\python.exe -m bci_decoder.cli run --config configs\demo_nomodel.yaml --chunks 1000
```

> 1000 数据块 → 每 0.5s 一条决策，共 200 条。日志见同目录 `demo_nomodel_200decisions.log`。

## 4. 证据

- 日志：`docs/evidence/W9_1027/T4_稳定化素材/demo_nomodel_200decisions.log`（36272 B）
- 决策统计（脚本核对）：**200 / 200 = idle**，0 条 left / 0 条 right。
- 示例行：

```
[    1.996s] idle   conf=0.50  probs=[0.50 0.50]  compute=1.3ms  win=2.0s state=running
...
```

## 5. 红线对照

| 红线 | 结论 |
|---|---|
| #1 未训练/model 缺失 → idle | ✅ 全程 200/200 idle，无任何 left/right |
| #2 置信度不足 → idle | ✅ conf=0.50 < 0.6 恒 idle |
| #3 输出字段冻结（9 字段） | ✅ 由 decode 契约测试覆盖（junit 22/0） |
| 通道顺序 C3→Oz | ✅ 配置保持冻结顺序，未重排 |

## 6. 备注 / 待办

1. **demo_weak（“弱信号 → idle”）素材未放**：实测 40 决策中 38 条 right（OOD 高置信缺陷，2c 降级交付），
   在核心 OOD 低置信机制落地前**不得用它录“安全 idle”素材**，否则会自曝其短。
   改进提案见 `docs/…/2c_OOD_低置信机制改进提案`（D 项）。
2. **画面截图/短视频**：需要游戏端画面才能录（A3/A6 画面部分），待组长新游戏推送后统一补。
   本文档为**解码台面侧**证据，不依赖游戏。
3. 原 T2-2d 存档（40 决策）在 `myworkoutputs/T2_演示配置/2d_demo_nomodel_200chunks.log`（初版快照，保留不删）。
