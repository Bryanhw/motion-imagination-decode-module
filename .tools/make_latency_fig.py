# -*- coding: utf-8 -*-
# T6 延迟分解对比图：等一块数据(2.0s 窗口) vs 单次分类计算。红线：只报延迟，不含任何准确率。
# 用法：.venv\Scripts\python.exe .tools/make_latency_fig.py   (见 docs/阎浩文-任务执行清单_1027.md T6)
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# 数字口径（对齐王释贤 2026-10-21 说明）：1.849 = 旧 bandpower 版本 p95 中位，仅历史值，
# 非当前正式演示值；新版 CSP p95 0.320 仅 CLI 计算范围，不含完整预处理与游戏端到端。
# 正式演示数字须：指定演示机 + 同提交 + 同配置 + 三轮复测后在此更新。
WAIT_MS = 2000.0
# 旧 bandpower 口径三次 p95 中位（王释贤 2026-10-20）；本机同口径 1.339 见 00_测试报告；
# 新版 CSP 0.320 仅 CLI 计算范围。正式值待统一演示机三轮复测后替换，勿作正式演示数字。
COMP_P95_MS = 1.849

fig, ax = plt.subplots(figsize=(8, 3.6))
labels = ["单次分类计算", "等一块数据(2.0s 窗口)"]
vals = [COMP_P95_MS, WAIT_MS]
ax.barh(labels, vals, color=["#fc8d62", "#8da0cb"])
ax.set_xscale("log")
ax.set_xlim(0.05, 30000)
ax.set_title("端到端链路延迟分解（对数轴，只报延迟）")
for i, v in enumerate(vals):
    ax.text(v * 1.2, i, f"{v:.3g} ms", va="center")
ax.set_xlabel("ms（对数刻度）")
ratio = COMP_P95_MS / WAIT_MS * 100
ax.text(0.98, -0.5, f"计算占比≈{ratio:.3g}%，0.5s/条的决策节奏预算内余量充足",
        transform=ax.transAxes, ha="right", fontsize=9, color="#555555")
fig.tight_layout()
out_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "docs", "evidence",
                                        "W9_1027", "00_测试报告"))
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "latency_breakdown.png")
fig.savefig(out, dpi=150)
print("saved:", out, "| 计算 p95:", COMP_P95_MS, "ms")
