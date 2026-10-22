# -*- coding: utf-8 -*-
# T6/A5 延迟分解对比图：等一块数据(2.0s 窗口) vs 单次分类计算。红线：只报延迟，不含准确率。
# 数字口径（2026-10-21 定）：本机 A4 正式基准 compute_p95 中位 0.955 ms
#   （docs/evidence/W9_1027/01_延迟/A4_benchmark_20261021_dfd9dfc.txt）；
#   1.849 ms 系王释贤旧 bandpower 历史值，非正式演示数字。
# 用法：venv_m3\Scripts\python.exe .tools/make_latency_fig.py
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

WAIT_MS, COMP_P95_MS = 2000.0, 0.955  # 等数据窗口 / A4 本机中位

fig, ax = plt.subplots(figsize=(8, 3.6))
ax.barh(["单次分类计算", "等一块数据(2.0s窗口)"], [COMP_P95_MS, WAIT_MS],
        color=["#fc8d62", "#8da0cb"])
ax.set_xscale("log")
ax.set_xlim(0.05, 30000)
ax.set_title("端到端链路延迟分解（对数轴，只报延迟）")
for i, v in enumerate([COMP_P95_MS, WAIT_MS]):
    ax.text(v * 1.2, i, f"{v:.3g} ms", va="center")
ax.set_xlabel("ms（对数刻度）")
ax.text(0.98, -0.5, f"计算占比≈{COMP_P95_MS / WAIT_MS * 100:.3g}%，"
        f"0.5s/条的决策节奏预算内余量充足", transform=ax.transAxes,
        ha="right", fontsize=9, color="#555555")
fig.tight_layout()
out = os.path.normpath(os.path.join(os.path.dirname(__file__), "..",
        "docs", "evidence", "W9_1027", "00_测试报告", "latency_breakdown.png"))
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.savefig(out, dpi=150)
print("saved:", out)
