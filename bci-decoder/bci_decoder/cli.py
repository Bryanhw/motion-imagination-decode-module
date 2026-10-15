"""命令行入口。

常用命令：
    python -m bci_decoder.cli run --config configs/default.yaml            # mock 源自检
    python -m bci_decoder.cli run --config configs/default.yaml --chunks 200
    python -m bci_decoder.cli benchmark --config configs/default.yaml       # 延迟压测（不限速）
    python -m bci_decoder.cli show-config --config configs/default.yaml
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import Config
from .core import DecoderEngine
from .outputs import build_sinks
from .sources import build_source


def _load(args) -> Config:
    return Config.load(args.config)


def cmd_run(args) -> int:
    cfg = _load(args)
    if args.chunks is not None:
        cfg.source.realtime = False
    engine = DecoderEngine(cfg)
    sinks = build_sinks(cfg.output)
    print(f"[bci-decoder] 数据源={cfg.source.kind}  窗口={cfg.window.window_seconds}s  "
          f"步长={cfg.window.step_seconds}s  类别={cfg.classifier.classes}")
    print(f"[bci-decoder] 输出通道={cfg.output.sinks}")
    engine.run(source=build_source(cfg.source), sinks=sinks, max_chunks=args.chunks)
    report = engine.latency_report()
    print(f"[bci-decoder] 决策次数={engine.n_outputs}")
    print(f"[bci-decoder] 计算耗时统计: {json.dumps(report, ensure_ascii=False)}")
    return 0


def cmd_benchmark(args) -> int:
    """不限速跑固定时长数据，测量纯计算耗时分布（不看延迟，只看算力是否够）。"""
    cfg = _load(args)
    cfg.source.realtime = False
    from .outputs.console import ConsoleSink

    engine = DecoderEngine(cfg)
    engine.run(source=build_source(cfg.source), sinks=[], max_chunks=args.chunks)
    print(json.dumps(engine.latency_report(), ensure_ascii=False, indent=2))
    return 0


def cmd_show_config(args) -> int:
    cfg = _load(args)
    print(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bci-decoder", description="在线运动想象解码模块")
    sub = p.add_subparsers(dest="command", required=True)

    for name, fn, help_text in (
        ("run", cmd_run, "运行在线解码"),
        ("benchmark", cmd_benchmark, "计算耗时压测"),
        ("show-config", cmd_show_config, "打印解析后的配置"),
    ):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--config", default="configs/default.yaml", help="配置文件路径")
        sp.add_argument("--chunks", type=int, default=None, help="最多处理的数据块数")
        sp.set_defaults(func=fn)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
