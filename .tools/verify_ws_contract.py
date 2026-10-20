# -*- coding: utf-8 -*-
# WS 契约自检（黑盒）：订阅解码端 WebSocket 输出，校验冻结的 9 字段契约与安全语义。
# 用法：.venv\Scripts\python.exe .tools/verify_ws_contract.py --uri ws://127.0.0.1:8765 --n 20 [--require-idle-only]
# 说明：不自建解码器、不评估准确率；只验证“游戏客户端拿到的消息长得对不对、安全不安全”。
import argparse
import asyncio
import json
import sys
import websockets

FIELDS = {"t_data", "t_wall", "label", "label_id", "confidence",
          "probs", "state", "compute_ms", "window_seconds"}
LABELS = {"left", "right", "idle"}


def check(m, i, fails, idle_only):
    def fail(msg):
        fails.append(f"#{i + 1} {msg}")

    if set(m.keys()) != FIELDS:
        return fail(f"字段集不符: got={sorted(m)}, want={sorted(FIELDS)}")
    if m["label"] not in LABELS:
        return fail(f"非法 label={m['label']!r}")
    if (m["label_id"] == -1) != (m["label"] == "idle"):
        return fail(f"label_id/label 不一致: label={m['label']} label_id={m['label_id']}")
    if m["label"] != "idle" and m["label_id"] not in (0, 1):
        return fail(f"label_id 越界: {m['label_id']}")
    if not (0.0 <= m["confidence"] <= 1.0):
        return fail(f"confidence 越界: {m['confidence']}")
    p = m["probs"]
    if not isinstance(p, list) or len(p) != 2 or any(not (0.0 <= x <= 1.0) for x in p):
        return fail(f"probs 非法: {p}")
    if abs(sum(p) - 1.0) > 0.02:
        return fail(f"probs 不归一: {p}")
    if m["state"] not in ("running", "stabilizing", "error"):
        return fail(f"state 非法: {m['state']}")
    if not isinstance(m["compute_ms"], (int, float)) or m["compute_ms"] < 0:
        return fail(f"compute_ms 非法: {m['compute_ms']}")
    if m["window_seconds"] != 2.0:
        return fail(f"window_seconds 应为 2.0: {m['window_seconds']}")
    if idle_only and m["label"] != "idle":
        return fail(f"require-idle-only 但收到 {m['label']!r}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default="ws://127.0.0.1:8765")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--require-idle-only", action="store_true")
    ap.add_argument("--connect-timeout", type=float, default=25.0,
                    help="等待解码端 ws 就绪的最长时间(秒)")
    a = ap.parse_args()
    fails, prev_wall, prev_data = [], None, None
    async def connect_retry():
        import time
        deadline = time.time() + a.connect_timeout
        while True:
            try:
                return await websockets.connect(a.uri)
            except Exception:
                if time.time() > deadline:
                    raise
                await asyncio.sleep(0.5)
    try:
        async with await connect_retry() as ws:
            for i in range(a.n):
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                try:
                    m = json.loads(raw)
                except Exception as e:
                    fails.append(f"#{i + 1} 非 JSON: {e!r}")
                    continue
                if prev_wall is not None and m["t_wall"] < prev_wall:
                    fails.append(f"#{i + 1} t_wall 回退 {prev_wall}->{m['t_wall']}")
                if prev_data is not None and m["t_data"] < prev_data - 1e-6:
                    fails.append(f"#{i + 1} t_data 回退")
                prev_wall, prev_data = m["t_wall"], m["t_data"]
                check(m, i, fails, a.require_idle_only)
    except Exception as e:
        fails.append(f"连接/接收异常: {e!r}")
    print(f"校验 {a.n} 条: 失败 {len(fails)} 条")
    for f in fails:
        print("  -", f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
