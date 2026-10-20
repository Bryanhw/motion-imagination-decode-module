# 王释贤：W9 演示模型与样本交付副本

按老师要求，将可公开的项目产出随 GitHub 分支交付。本目录是选定产物的版本化副本；虚拟环境、缓存与临时执行状态不作为交付包。当前仅准备在本地，待下一次本人提交并推送后才会出现在 GitHub；不要提前宣称已上传。

| 内容 | 相对位置 | 用途 |
|---|---|---|
| 新版 CSP 空间滤波模型 | `models/csp/demo_csp.joblib` | 4个空间滤波器，8通道输入 |
| 新版 LDA 模型 | `models/csp/demo_lda.joblib` | 与上述CSP配对，输入4维 |
| 旧版 LDA 历史模型 | `models/bandpower_history/demo_lda.joblib` | 16维频带功率输入，对应旧测速/长跑 |
| 合成连续样本 | `inputs/sample_continuous.npy` | replay工程验证，8通道、250Hz、60秒 |
| 现用配置副本 | `configs/demo_online.yaml`、`configs/demo_replay.yaml` | 新版CSP运行参数 |
| 旧版配置副本 | `configs/demo_online_bandpower_history.yaml` | 追溯旧版结果 |
| 来源与完整性 | `manifest.json` | 相对来源、SHA256、大小与环境版本 |

全部模型由合成数据生成，样本也是合成数据，**仅用于工程复现，不代表真实脑电准确率**。内部bootstrap交叉验证数字不作为课程演示成绩或公开性能证据；只导出模型准备结果。

## 从交付副本恢复运行

在仓库根目录，用 `Copy-Item` 将新版两个模型复制到 `bci-decoder/artifacts/`，将样本复制到 `bci-decoder/data/`（先建目录；已有历史模型先另存）。原配置中的路径相对 `bci-decoder/` 解析，不直接在本目录运行。

也可在 `bci-decoder/` 使用已入库的脚本重新生成：

```powershell
.\.venv\Scripts\python.exe scripts/bootstrap_demo.py --config configs/demo_online.yaml
.\.venv\Scripts\python.exe scripts/make_sample_data.py --out data/sample_continuous.npy --seconds 60
```

模型配对检查以及本人新版mock/replay复跑已通过（40/60条）；新版三次测速已完成，各轮p95中位数为0.320 ms（仅CLI计算范围）；汇总位于 `docs/evidence/W9_1027/01_延迟/CSP_15096bc/`。原始证据在 `docs/evidence/W9_1027/04_运行记录/CSP_15096bc/`。旧1.849ms和一小时结论只能引用旧bandpower配置，不用于新CSP成绩。

测试、测速、长跑、截图与复现记录统一索引见 `docs/交付物索引.md`，原始证据仍保留在 `docs/evidence/W9_1027/`，不重复复制。
