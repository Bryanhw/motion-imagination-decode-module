"""真采数据格式预检脚本：在 calibrate 之前一键核对 raw/labels 是否符合校准契约。

为什么需要（docs/calibration_flow.md §4 的“真实采集数据格式约定”）：
- raw.npy    (n_ch, n_t) 连续 EEG；通道顺序必须与 source.ch_names 一致（红线 4，绝不重排）
- labels.npy  每个 trial 一个类别标签，取值 ∈ config.classifier.classes
- calibrate 默认按 sfreq × trial_seconds（如 250Hz × 2.0s = 500 样本/trial）切分 trial。

风险点：若采集设备采样率与配置 sfreq 不一致（例如设备 500Hz 而配置 250），
calibrate.py 会**静默切错 trial**（最坏情况是整个采集报废重来）。
本脚本在进 calibrate 之前核对格式，并基于数据自身推断采样率，尽早暴露不一致。

用法（在 bci-decoder 目录下）：
    .venv/Scripts/python.exe scripts/precheck_real_data.py --real-data data/raw.npy --labels data/labels.npy
    # 可选：--config configs/default.yaml --trial-seconds 2.0 --subject-id alice --out-dir artifacts/users

退出码：0 = 通过（PASS）  1 = 有警告（WARN，仍可继续但建议核对）  2 = 校验失败（FAIL，校准必失败）

红线遵守：
- 只读数据、只写核对报告（artifacts/users/<subject_id>/precheck.{json,md}），不碰模型/配置；
- 不重排通道、不加/改输出消息字段；不做任何性能评估、不对外报准确率。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bci_decoder.config import Config  # noqa: E402

DEFAULT_USERS_ROOT = os.path.join("artifacts", "users")
DEFAULT_CONFIG = "configs/default.yaml"


def _validate_and_report(raw: np.ndarray, labels: np.ndarray, cfg: Config, trial_seconds: float) -> dict:
    """核对 raw/labels 是否满足 calibrate 契约，返回结构化报告 dict（可测）。"""
    n_ch_expected = len(cfg.source.ch_names)
    sfreq = cfg.source.sfreq
    step_expected = int(sfreq * trial_seconds)

    errors: list[str] = []
    warnings: list[str] = []
    info_raw: dict = {}
    info_trial: dict = {}
    info_labels: dict = {}

    # 1) 通道数/维度（红线 4 的第一道防线；与 calibrate 同规则）
    n_ch = n_t = None
    if raw.ndim != 2:
        errors.append(f"raw 必须是二维数组 (n_ch, n_t)，当前 shape={raw.shape}")
    else:
        n_ch, n_t = raw.shape
        info_raw = {"shape": list(raw.shape), "n_ch": n_ch, "n_t": n_t}
        if n_ch != n_ch_expected:
            errors.append(
                f"通道数不符：raw 有 {n_ch} 通道，期望 {n_ch_expected}"
                f"（source.ch_names={cfg.source.ch_names}）。通道顺序必须与其一致（红线 4）。"
            )

    # 2) labels：一维 + 取值 ∈ classes（兼容 0..n-1 索引写法，与 calibrate 同规则）
    allowed_str = set(cfg.classifier.classes)
    allowed_idx = set(range(len(cfg.classifier.classes)))
    n_trials = 0
    if labels.ndim != 1:
        errors.append(f"labels 必须是一维数组，当前 shape={labels.shape}")
    else:
        n_trials = int(len(labels))
        bad = [
            v
            for v in np.unique(labels)
            if v not in allowed_str
            and not (isinstance(v, (int, np.integer)) and int(v) in allowed_idx)
        ]
        if bad:
            errors.append(
                f"labels 含未知类别 {bad}，期望 ∈ {cfg.classifier.classes}（或等价格引 0..n-1）。"
            )

    # 3) trial 对齐 + 采样率推断（核心增量价值：设备 sfreq 与配置不一致时提前暴露）
    if not errors:
        if n_trials == 0:
            errors.append("labels 为空：至少需要 1 个 trial 才能训练。")
        else:
            info_trial["config_step_samples"] = step_expected
            if n_t % n_trials == 0:
                inf_samples = n_t // n_trials
                inf_sfreq = inf_samples / trial_seconds
                info_trial["inferred_samples_per_trial"] = inf_samples
                info_trial["inferred_sfreq_hz"] = round(inf_sfreq, 1)
                if inf_samples < step_expected:
                    errors.append(
                        f"疑似数据长度不足/trial 数错误：推断每 trial {inf_samples} 样本 "
                        f"(≈{inf_sfreq:.0f}Hz)，低于配置要求 {step_expected}（{sfreq}Hz×{trial_seconds}s）。"
                    )
                elif abs(inf_sfreq - sfreq) < 0.5:
                    info_trial["sfreq_match"] = True
                else:
                    ratio = inf_sfreq / sfreq
                    strength = "强警告：" if (ratio > 1.25 or ratio < 0.75) else "警告："
                    warnings.append(
                        f"{strength}推断采样率 {inf_sfreq:.1f}Hz ≠ 配置 {sfreq}Hz"
                        f"（ratio≈{ratio:.2f}）。calibrate 将按 {sfreq}Hz 切 trial，可能导致错位，"
                        "请核对设备采样率或调整 configs/default.yaml 的 source.sfreq。"
                    )
                    info_trial["sfreq_match"] = False
            else:
                warnings.append(
                    f"样本数 {n_t} 不能被 trial 数 {n_trials} 整除：疑似标注未按 trial 对齐，"
                    "或 labels 的 trial 数不对。"
                )
            # 长度下限（即使能整除、sfreq 匹配，仍可能不足）
            if n_t < n_trials * step_expected:
                errors.append(
                    f"长度不足：raw 只有 {n_t} 样本，而 {n_trials} 个 trial 至少需要 "
                    f"{n_trials * step_expected}（{step_expected}/trial）。"
                )

    # 4) labels 分布（供人工核对采样均衡）
    if n_trials:
        uniq, counts = np.unique(labels, return_counts=True)
        display = {}
        for u, c in zip(uniq, counts):
            if isinstance(u, (int, np.integer)) and 0 <= int(u) < len(cfg.classifier.classes):
                key = cfg.classifier.classes[int(u)]
            else:
                key = str(u)
            display[key] = int(c)
        info_labels = {"n_trials": n_trials, "counts": display}
        if len(uniq) < 2:
            warnings.append(
                f"labels 只有 1 个类别（{list(display)}）：无法做二分类，建议补齐 2 类。"
            )

    verdict = "FAIL" if errors else ("WARN" if warnings else "PASS")
    return {
        "ok": verdict == "PASS",
        "verdict": verdict,
        "errors": errors,
        "warnings": warnings,
        "raw": info_raw,
        "trial": info_trial,
        "labels": info_labels,
        "config": {
            "sfreq": sfreq,
            "trial_seconds": trial_seconds,
            "step_samples": step_expected,
            "ch_names": cfg.source.ch_names,
            "classes": cfg.classifier.classes,
        },
    }


def _render_md(result: dict) -> str:
    lines = [
        "# 真采数据格式预检报告（precheck_real_data.py）",
        "",
        f"- **结论**：{result['verdict']}",
        f"- raw：shape={result['raw'].get('shape')} · 通道数 "
        f"{result['raw'].get('n_ch')}/{len(result['config']['ch_names'])}",
        "- trial 切分：配置 "
        f"{result['config']['step_samples']} 样本/trial"
        f"（{result['config']['sfreq']}Hz×{result['config']['trial_seconds']}s）",
    ]
    tr = result["trial"]
    if tr:
        lines.append(
            f"  - 推断：每 trial {tr.get('inferred_samples_per_trial')} 样本 · "
            f"推断采样率 {tr.get('inferred_sfreq_hz')}Hz · "
            f"sfreq_match={tr.get('sfreq_match')}"
        )
    lb = result["labels"]
    if lb:
        lines.append(f"- labels：{lb.get('n_trials')} 个 trial · 分布 {lb.get('counts')}")
    if result["warnings"]:
        lines.append("")
        lines.append("## 警告")
        lines.extend(f"- {w}" for w in result["warnings"])
    if result["errors"]:
        lines.append("")
        lines.append("## 错误（需修复后再进 calibrate）")
        lines.extend(f"- {e}" for e in result["errors"])
    lines.append("")
    lines.append(
        "> 用途：进 `scripts/calibrate.py --real-data ... --labels ...` 前的格式核对；"
        "**红线 4：通道顺序须与 ch_names 一致，请人工确认原始设备通道排布**。"
    )
    return "\n".join(lines)


def write_report(result: dict, subject_id: str, out_dir: str) -> dict:
    """把报告落盘到 <out_dir>/<subject_id>/precheck.{json,md}；返回落盘路径。"""
    root = os.path.join(out_dir, subject_id)
    os.makedirs(root, exist_ok=True)
    json_path = os.path.join(root, "precheck.json")
    md_path = os.path.join(root, "precheck.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_render_md(result))
    return {"json": json_path, "md": md_path}


def main() -> int:
    ap = argparse.ArgumentParser(description="真采数据格式预检（进 calibrate 前的核对与采样率推断）")
    ap.add_argument("--real-data", required=True, help="raw .npy 路径：(n_ch, n_t)")
    ap.add_argument("--labels", required=True, help="labels .npy 路径：长度=trial 数")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help="基础配置（默认 configs/default.yaml）")
    ap.add_argument("--trial-seconds", type=float, default=2.0, help="trial 时长（默认 2.0s，与滑窗一致）")
    ap.add_argument(
        "--subject-id", default="", help="若提供，报告落盘到 <out-dir>/<subject-id>/precheck.{json,md}"
    )
    ap.add_argument("--out-dir", default=DEFAULT_USERS_ROOT, help="报告根目录（默认 artifacts/users）")
    ap.add_argument("--no-save", action="store_true", help="只打印不落盘")
    args = ap.parse_args()

    if os.path.exists(args.config):
        cfg = Config.load(args.config)
    else:
        print(f"[precheck] 配置不存在：{args.config}（退回默认 Config）", file=sys.stderr)
        cfg = Config()

    result = _validate_and_report(np.load(args.real_data), np.load(args.labels), cfg, args.trial_seconds)

    print(_render_md(result))
    print()
    print(f"[precheck] verdict={result['verdict']}")

    if args.subject_id and not args.no_save:
        paths = write_report(result, args.subject_id, args.out_dir)
        print(f"[precheck] 报告已落盘：{paths['md']} / {paths['json']}")

    return 0 if result["ok"] else (1 if result["verdict"] == "WARN" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
