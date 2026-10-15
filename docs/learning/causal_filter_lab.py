"""实验 1：为什么在线只能用因果滤波？（filtfilt vs sosfilt 对照）

这是《大一学生学习路线图》里 P0 + ⭐⭐⭐ 那个门槛的最小可运行实验。
运行：

    python docs/learning/causal_filter_lab.py

实验 A  零相位 vs 因果：同一个滤波器，两种用法，波形差在哪
实验 B  分块流式 vs 一次性：证明"跨块传状态"是流式滤波的正确写法
实验 C  忘记传状态会怎样：亲眼看到每个块边界的阶跃
实验 D  相位延迟与块大小无关：打破"块切小一点就没延迟"的直觉
实验 E  ★ 延迟到底怎么测：三种"看起来合理"的测法全都给出错误答案

实验 E 值得特别说明：它记录的是本实验脚本**开发过程中真实踩过的坑**——
最初用"单频信号互相关"测出 72 ms、用"冲激响应峰值"测出 32 ms，
而真值是 80 ms。**三个数全都错，而且错得各有原因。**
这正好是本项目的核心命题：**数字看起来有，和数字可信，是两件事。**

纪律提醒（章程 5.4 / MVP 规格 6.3）：
本脚本用的是**合成信号**，只用于理解原理，**不能作为任何算法成绩**。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, hilbert, sosfilt, sosfiltfilt

# Windows 控制台默认 GBK，print 非 GBK 字符会抛 UnicodeEncodeError。
# 这两行让输出用 UTF-8，避免"脚本逻辑没问题、却在打印时崩掉"。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ----------------------------------------------------------------------------
# 0. 参数集中在这里，方便改完重跑（"配置驱动"的习惯）
# ----------------------------------------------------------------------------
SFREC = 250.0            # 采样率 Hz，与项目冻结值一致
DURATION = 4.0           # 信号时长 s
BAND = (8.0, 30.0)       # 带通 8–30 Hz，与 MVP 冻结值一致
ORDER = 4                # 滤波器阶数
CHUNK_MS = 100.0         # 数据块长度 ms，与项目冻结值一致（100ms = 25 点）
SIGNAL_HZ = 10.0         # 信号主频 10 Hz，落在通带内（模拟 μ 节律）

FIG_DIR = Path(__file__).resolve().parent / "figs"


def design_bandpass(sfreq: float, l_freq: float, h_freq: float, order: int = 4) -> np.ndarray:
    """设计带通 IIR 滤波器，输出 SOS 形式（与骨架 preprocess.py 完全一致）。"""
    return butter(order, [l_freq, h_freq], btype="bandpass", fs=sfreq, output="sos")


def make_signal(sfreq: float = SFREC, duration: float = DURATION, seed: int = 0):
    """造一段"干净信号 + 干扰"，干净信号已知，这样能看清滤波器干了什么。

    额外加 40 Hz 成分（通带外）和一段基线漂移（低频），
    用于直观看到"带通"到底滤掉了什么。
    """
    rng = np.random.default_rng(seed)
    n = int(sfreq * duration)
    t = np.arange(n) / sfreq

    clean = 15.0 * np.sin(2 * np.pi * SIGNAL_HZ * t)            # 通带内，要保留
    out_of_band = 8.0 * np.sin(2 * np.pi * 40.0 * t)            # 通带外，要滤掉
    drift = 20.0 * np.sin(2 * np.pi * 0.3 * t)                  # 低频漂移，要滤掉
    noise = 3.0 * rng.standard_normal(n)                        # 背景噪声

    return t, clean + out_of_band + drift + noise, clean


# ----------------------------------------------------------------------------
# 延迟测量工具箱（实验 E 的主角）
# ----------------------------------------------------------------------------
def delay_impulse(sos: np.ndarray, f0: float, sfreq: float = SFREC,
                  n: int = 200000) -> float:
    """【权威法】由脉冲响应算群延迟，单位 ms。

    群延迟的定义是 -dφ/dω。在时域上它等价于：

        gd(ω) = Re[ Σ n·h[n]·e^{-jωn} / Σ h[n]·e^{-jωn} ]

    h[n] 是滤波器的脉冲响应。这个写法**不需要做相位解缠绕**，
    因此在数值上最稳，本脚本把它当作真值基准。

    注意 n 必须足够大（这里取 20 万点），否则脉冲响应被截断会引入偏差。
    """
    imp = np.zeros(n)
    imp[0] = 1.0
    h = sosfilt(sos, imp)
    w = 2 * np.pi * f0 / sfreq
    idx = np.arange(n)
    e = np.exp(-1j * w * idx)
    return float(np.real(np.sum(idx * h * e) / np.sum(h * e))) / sfreq * 1000.0


def delay_phase_dense(sos: np.ndarray, f0: float, sfreq: float = SFREC) -> float:
    """【正确法 2】相位斜率法，但必须用稠密频率网格 + 只在通带内解缠绕。

    这个函数专门用来对比"稀疏网格 + 全域解缠绕"的错误做法（见 delay_phase_naive）。
    """
    from scipy.signal import sosfreqz

    w = np.linspace(2 * np.pi * 7.5 / sfreq, 2 * np.pi * 31.0 / sfreq, 20001)
    _, h = sosfreqz(sos, worN=w)
    ph = np.unwrap(np.angle(h))
    gd = -np.gradient(ph, w) / sfreq * 1000.0
    f = w * sfreq / (2 * np.pi)
    return float(gd[int(np.argmin(np.abs(f - f0)))])


def delay_phase_naive(sos: np.ndarray, f0: float, sfreq: float = SFREC) -> float:
    """【错误示范 1】稀疏网格 + 全域解缠绕求相位斜率。

    这是本脚本第一版真实用过的写法，对 4 阶 8–30 Hz 带通在 10 Hz 处给出 ~2 ms，
    而真值是 80 ms —— **差了 40 倍**。

    错因：`sosfreqz(worN=4096)` 的 4096 个点在 0..Nyquist 上均匀分布，
    低频段（0–30 Hz 只占 4096 点里的约 490 点）分辨率太粗；
    再叠加全域解缠绕时相位在阻带里剧烈翻滚，斜率就被彻底带偏。
    """
    from scipy.signal import sosfreqz

    w, h = sosfreqz(sos, worN=4096, fs=sfreq)
    ph = np.unwrap(np.angle(h))
    gd = -np.gradient(ph, w) / sfreq * 1000.0
    return float(gd[int(np.argmin(np.abs(w - f0)))])


def delay_envelope(sos: np.ndarray, f0: float, sfreq: float = SFREC,
                   sigma: float = 0.15) -> float:
    """【正确法 3，最直观】把 f0 正弦包进高斯包，看输出包络峰延后多少。

    "信号整体晚到了多久"——这就是普通人理解的延迟，物理上对应群延迟。
    """
    n = 2500
    t = np.arange(n) / sfreq
    burst = np.exp(-((t - 1.0) ** 2) / (2 * sigma ** 2)) * np.sin(2 * np.pi * f0 * t)
    y = sosfilt(sos, burst)
    return (int(np.argmax(np.abs(hilbert(y)))) -
            int(np.argmax(np.abs(hilbert(burst))))) / sfreq * 1000.0


def delay_xcorr_single_tone(sos: np.ndarray, f0: float, sfreq: float = SFREC,
                            n: int = 4000, seed: int = 0) -> float:
    """【错误示范 2】用单频信号做互相关测延迟 —— 本项目第一版真实踩过的坑。

    在 10 Hz 上它给出 72 ms（真值 80 ms，看着"差不多"），
    但换到 12 Hz 就变成 -12 ms、20 Hz 变成 8 ms —— 结果完全不可复现。

    错因：单频信号的自相关**每隔一个周期（1/10 s = 100 ms）就有一个峰**，
    互相关无法区分"延迟了 80 ms"和"延迟了 -20 ms"。这是周期信号的根本歧义。
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n) / sfreq
    x = 15 * np.sin(2 * np.pi * f0 * t) + 3 * rng.standard_normal(n)
    y = sosfilt(sos, x)
    c = np.correlate(y - y.mean(), x - x.mean(), mode="full")
    lag = np.arange(-(n - 1), n)
    return float(lag[int(np.argmax(c))]) / sfreq * 1000.0


def delay_xcorr_broadband(sos: np.ndarray, sfreq: float = SFREC,
                          n: int = 50000, seed: int = 0) -> float:
    """【易被误用】宽带（白噪声）互相关。

    它没有周期性歧义，给出的是**通带内的平均延迟**（52 ms）。
    但本项目关心的是"μ 节律（8–13 Hz）的延迟"，
    用平均延迟代替特定频段延迟会低估约 35%。**能用，但要清楚它测的是什么。**
    """
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n) * 10.0
    y = sosfilt(sos, x)
    c = np.correlate(y - y.mean(), x - x.mean(), mode="full")
    lag = np.arange(-(n - 1), n)
    return float(lag[int(np.argmax(c))]) / sfreq * 1000.0


class StreamFilter:
    """带状态的因果滤波器 —— **这就是骨架 preprocess.py 里那个类的核心**。

    关键只有两行：
      1) __init__ 里准备 state（滤波器记忆）
      2) 每次 process 把 state 传进去，并**存回返回的新 state**
    """

    def __init__(self, sos: np.ndarray):
        self.sos = np.asarray(sos, dtype=np.float64)
        self.state = np.zeros((self.sos.shape[0], 2), dtype=np.float64)

    def process(self, x: np.ndarray, use_state: bool = True) -> np.ndarray:
        if use_state:
            y, self.state = sosfilt(self.sos, x, zi=self.state)
            return y
        # 错误示范：每次都从零状态开始 = 把每块都当成新信号的开始。
        # 不传 zi 时 sosfilt 只返回 y（不再返回 state），所以只有一个返回值。
        return sosfilt(self.sos, x)


def split_chunks(x: np.ndarray, chunk_samples: int):
    for i in range(0, x.shape[-1], chunk_samples):
        yield x[..., i:i + chunk_samples]


# ----------------------------------------------------------------------------
def experiment_a(sos, t, raw, clean):
    y_ff = sosfiltfilt(sos, raw)
    y_ca = sosfilt(sos, raw)
    d_true = delay_impulse(sos, SIGNAL_HZ)

    print("=" * 74)
    print("实验 A：零相位（filtfilt）vs 因果（sosfilt）")
    print("=" * 74)
    print(f"  信号主频                : {SIGNAL_HZ} Hz")
    print(f"  因果滤波群延迟(真值)    : {d_true:.1f} ms  ← 方法见实验 E")
    print(f"  filtfilt 群延迟         : 0 ms（构造上前后各滤一遍，相位正好抵消）")
    print("  观察图 1：绿=真实干净信号，蓝=filtfilt 与绿重合；红=因果，整体右移。")
    print("  结论：filtfilt 的零延迟是**借未来数据**换来的 ——")
    print("        它在 t 时刻用到了 t 之后的数据，在线时那些数据还没发生 → 用不了。")
    return y_ff, y_ca


def experiment_b(sos, raw):
    chunk_samples = int(SFREC * CHUNK_MS / 1000.0)
    y_once = sosfilt(sos, raw)

    st = StreamFilter(sos)
    y_stream = np.concatenate([st.process(c) for c in split_chunks(raw, chunk_samples)])
    max_err = float(np.max(np.abs(y_once - y_stream)))

    print()
    print("=" * 74)
    print("实验 B：分块流式（带状态） vs 一次性滤波")
    print("=" * 74)
    print(f"  块大小              : {chunk_samples} 样本 ({CHUNK_MS:.0f} ms)")
    print(f"  最大逐点误差        : {max_err:.3e}")
    print(f"  是否一致(容差1e-9)  : {'是 [OK]' if max_err < 1e-9 else '否 [FAIL]'}")
    print("  结论：只要块与块之间传递 state，流式滤波与一次性滤波**完全等价**。")
    print("        这正是 MVP 测试用例 T3（因果滤波状态连续性）要断言的东西：")
    print("        『分块喂入 == 一次喂入』。")
    return y_stream, max_err


def experiment_c(sos, raw):
    chunk_samples = int(SFREC * CHUNK_MS / 1000.0)
    y_good = sosfilt(sos, raw)

    st_bad = StreamFilter(sos)
    y_bad = np.concatenate([st_bad.process(c, use_state=False)
                            for c in split_chunks(raw, chunk_samples)])

    step = lambda y: float(np.max(np.abs(np.diff(y))))  # noqa: E731

    print()
    print("=" * 74)
    print("实验 C：忘记传状态会怎样（最容易犯的错）")
    print("=" * 74)
    print(f"  正确（带状态）最大误差   : 0（见实验 B）")
    print(f"  错误（不传状态）最大误差 : {np.max(np.abs(y_good - y_bad)):.3e}")
    print(f"  正确写法最大一阶跳变     : {step(y_good):.4f}")
    print(f"  错误写法最大一阶跳变     : {step(y_bad):.4f}  "
          f"（放大 {step(y_bad) / step(y_good):.1f} 倍）")
    print("  结论：不传状态不是'精度差一点'，而是**每个块边界都出现一次阶跃**。")
    print("        这种跳变会污染 2 秒窗口里的频带功率 → 特征抖动 → 输出乱跳。")
    print("        而且它**不会报错**，只会让在线表现比离线差一大截 ——")
    print("        这就是'回放准确率与离线差 < 5%'那条验收指标要防的事。")
    return y_bad, step(y_good), step(y_bad)


def experiment_d(sos, raw):
    print()
    print("=" * 74)
    print("实验 D：把块切小一点，延迟会变小吗？（打破直觉）")
    print("=" * 74)
    print(f"  {'块长(ms)':>10} {'块长(样本)':>12} {'与一次性滤波误差':>18}")
    for chunk_ms in (25.0, 50.0, 100.0, 250.0, 500.0):
        cs = int(SFREC * chunk_ms / 1000.0)
        st = StreamFilter(sos)
        y = np.concatenate([st.process(c) for c in split_chunks(raw, cs)])
        err = float(np.max(np.abs(sosfilt(sos, raw) - y)))
        print(f"  {chunk_ms:>10.0f} {cs:>12d} {err:>18.3e}")
    print("  结论：块长只影响「计算多久跑一次」，**不影响延迟**；")
    print("        延迟由滤波器自身（阶数、截止频率）决定，见实验 E 的阶数扫描。")
    print("        → 同理：端到端响应慢不是因为计算慢，而是窗口要攒够 2 秒。")


def experiment_e(sos):
    """★ 本实验记录真实踩坑：三种测法给出三个不同的错误答案。"""
    print()
    print("=" * 74)
    print("实验 E：延迟到底怎么测？（本实验脚本开发时真实踩过的坑）")
    print("=" * 74)

    truth = delay_impulse(sos, SIGNAL_HZ)
    print(f"  真值基准（冲激响应法，4 阶 8–30Hz 带通 @ {SIGNAL_HZ} Hz）: {truth:.2f} ms")
    print()
    print(f"  {'测法':<34}{'结果(ms)':>12}{'误差':>12}")
    print("  " + "-" * 58)

    rows = [
        ("冲激响应法（权威，本脚本采用）", truth),
        ("相位斜率法·稠密网格+通带内解缠绕", delay_phase_dense(sos, SIGNAL_HZ)),
        ("包络法（高斯包络，最直观）", delay_envelope(sos, SIGNAL_HZ)),
        ("[错] 相位斜率法·稀疏网格全域解缠绕", delay_phase_naive(sos, SIGNAL_HZ)),
        ("[错] 单频互相关 @10Hz", delay_xcorr_single_tone(sos, 10.0)),
        ("[错] 单频互相关 @12Hz", delay_xcorr_single_tone(sos, 12.0)),
        ("[错] 单频互相关 @20Hz", delay_xcorr_single_tone(sos, 20.0)),
        ("[偏] 宽带互相关（测的是通带平均）", delay_xcorr_broadband(sos)),
    ]
    for name, val in rows:
        err = (val - truth) / truth * 100.0
        print(f"  {name:<34}{val:>12.2f}{err:>11.0f}%")

    print()
    print("  三个错误答案的错因（这才是本实验真正的收获）：")
    print("   1) 稀疏网格全域解缠绕 → 低频分辨率不足 + 阻带相位翻滚，斜率被带偏（差 40 倍）；")
    print("   2) 单频互相关 → 周期信号每 1/f0 = 100 ms 就有一个相关峰，")
    print("      无法区分'延迟 80 ms'和'提前 20 ms'，换个频率答案就变（见上表 10/12/20 Hz）；")
    print("   3) 宽带互相关 → 没有歧义，但测的是**通带平均延迟**，")
    print("      而我们关心的是 μ 节律（8–13 Hz）的延迟，用它会低估约 35%。")
    print()
    print("  阶数扫描（真值随阶数线性增长，这是群延迟的定义决定的）：")
    print(f"  {'阶数':>6}{'10 Hz 群延迟(ms)':>20}{'20 Hz 群延迟(ms)':>20}")
    for order in (2, 4, 6, 8):
        s = design_bandpass(SFREC, BAND[0], BAND[1], order)
        print(f"  {order:>6}{delay_impulse(s, 10.0):>20.1f}{delay_impulse(s, 20.0):>20.1f}")
    print("  → 阶数越高，延迟越大。所以'想减小延迟'只能从滤波器设计入手，")
    print("    而**不能**靠'把块切小一点'（实验 D 已证明块长不影响延迟）。")

    print()
    print("  ★ 写成一句话（答辩可以直接用）：")
    print(f"    『4 阶 8–30 Hz 因果带通在 10 Hz 处的群延迟约 {truth:.0f} ms；")
    print("      这个数用三种独立方法互相验证过（冲激响应 / 稠密相位斜率 / 包络延迟），")
    print("      而单频互相关会给出不可复现的假答案，所以我们不用它。』")
    return truth, rows


def plot_all(t, raw, clean, y_ff, y_ca, y_good, y_bad, out_path: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    matplotlib.rcParams["axes.unicode_minus"] = False
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]

    t0, t1 = 1.0, 2.0
    m = (t >= t0) & (t <= t1)
    cs = int(SFREC * CHUNK_MS / 1000.0)

    fig, axes = plt.subplots(3, 1, figsize=(11.5, 10.5), sharex=True)

    ax = axes[0]
    ax.plot(t[m], raw[m], color="0.75", lw=0.8, label="原始信号（含 40Hz + 低频漂移 + 噪声）")
    ax.plot(t[m], clean[m], color="C2", lw=2.0, alpha=0.75, label="真实干净信号（10 Hz）")
    ax.plot(t[m], y_ff[m], color="C0", lw=1.0, ls="--", label="filtfilt（零相位，离线可用）")
    ax.plot(t[m], y_ca[m], color="C3", lw=1.2, label="sosfilt（因果，在线只能这样）")
    ax.set_title("实验 A：零相位 vs 因果 —— 蓝色虚线追平绿色，红色整体右移（这就是相位延迟）")
    ax.set_ylabel("幅值 (µV)")
    ax.legend(loc="upper right", fontsize=8)

    ax = axes[1]
    ax.plot(t[m], y_good[m], color="C0", lw=1.5, label="正确：块间传递 state")
    ax.plot(t[m], y_bad[m], color="C1", lw=1.0, alpha=0.85, label="错误：每块从零状态开始")
    for b in range(int(t0 * SFREC), int(t1 * SFREC), cs):
        ax.axvline(b / SFREC, color="k", ls=":", lw=0.5, alpha=0.35)
    ax.set_title("实验 C：忘记传 state —— 灰虚线是块边界，错误曲线在每个边界发生阶跃")
    ax.set_ylabel("幅值 (µV)")
    ax.legend(loc="upper right", fontsize=8)

    ax = axes[2]
    ax.plot(t[m], np.abs(np.diff(y_good, prepend=y_good[0]))[m], color="C0", lw=1.0,
            label="正确：|一阶差分|")
    ax.plot(t[m], np.abs(np.diff(y_bad, prepend=y_bad[0]))[m], color="C1", lw=1.0,
            alpha=0.85, label="错误：|一阶差分|")
    for b in range(int(t0 * SFREC), int(t1 * SFREC), cs):
        ax.axvline(b / SFREC, color="k", ls=":", lw=0.5, alpha=0.35)
    ax.set_title("实验 C 放大：块边界处的尖峰 = 频带功率抖动 = 解码输出乱跳的根源")
    ax.set_xlabel("时间 (s)")
    ax.set_ylabel("|Δ| (µV)")
    ax.legend(loc="upper right", fontsize=8)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def main() -> int:
    sos = design_bandpass(SFREC, BAND[0], BAND[1], ORDER)
    t, raw, clean = make_signal()

    y_ff, y_ca = experiment_a(sos, t, raw, clean)
    y_stream, _ = experiment_b(sos, raw)
    y_bad, _, _ = experiment_c(sos, raw)
    experiment_d(sos, raw)
    truth, _ = experiment_e(sos)

    fig_path = FIG_DIR / "exp1_causal_filter.png"
    plot_all(t, raw, clean, y_ff, y_ca, y_stream, y_bad, fig_path)

    print()
    print("=" * 74)
    print("输出与下一步")
    print("=" * 74)
    print(f"  图已保存 : {fig_path}")
    print()
    print("  可以直接写进报告/答辩的三句话：")
    print("   1. filtfilt 的零相位延迟靠使用未来数据换来，在线不可实现；")
    print(f"   2. 因果滤波必然引入相位延迟：4 阶 8–30 Hz 带通在 10 Hz 处约 {truth:.0f} ms，")
    print("      随阶数线性增长，与分块大小无关；")
    print("   3. 流式滤波必须跨块传递滤波器状态，否则每个块边界产生阶跃，")
    print("      污染窗口内频带功率，导致输出抖动。")
    print()
    print("  【动手练习，必做】")
    print("   a) 把 CHUNK_MS 改成 50 / 250 重跑：实验 B 误差应仍为 0，实验 D 应仍无延迟差异。")
    print("   b) 把 ORDER 改成 2 / 8 重跑：观察群延迟如何随阶数变化，")
    print("      想一想'延迟要小'和'阻带要干净'为什么是一对矛盾。")
    print("   c) 把 BAND 改成 (8, 13) 只留 μ 节律，重跑实验 E：")
    print("      看 μ 波段内的延迟是否比 8–30 Hz 更大，为什么？")
    print("   d) ★ 在你自己的代码里做一个 T3 测试：")
    print("      断言『分块喂入 == 一次喂入』，容差 1e-9。写不出来就再看一遍实验 B。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
