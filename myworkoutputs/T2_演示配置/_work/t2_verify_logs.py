# 临时统计：解析 console sink 日志行，提取 label 序列摘要（T2 验证用，非交付物）
import re, collections

pat = re.compile(r"^\s*\[\s*[\d.]+s\]\s+(\S+)\s+conf=")

paths = {
    "2b_switch": r"D:\校企合作项目\.deepworks\tmp\t2b_switch.log",
    "2c_weak": r"D:\校企合作项目\.deepworks\tmp\t2c_weak.log",
    "2d_nomodel": r"D:\校企合作项目\.deepworks\tmp\t2d_nomodel.log",
}

for name, p in paths.items():
    labels = []
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = pat.match(line)
            if m:
                labels.append(m.group(1))
    cnt = collections.Counter(labels)
    runs = []
    for lb in labels:
        if not runs or runs[-1] != lb:
            runs.append(lb)
    print(f"[{name}] 决策数={len(labels)}  计数={dict(cnt)}")
    print(f"[{name}] run 序列={runs[:40]}{"..." if len(runs) > 40 else ""}")
    n = len(runs)
    lr = sum(1 for i in range(1, n) if runs[i] in ("left", "right"))
    print(f"[{name}] left/right 出现的不同 run 段数={lr}")
    print()
