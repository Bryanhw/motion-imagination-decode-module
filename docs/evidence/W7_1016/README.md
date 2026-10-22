# W7_1016 —— F4 脑控弹球游戏端里程碑证据

> **2026-10-22 现况注记**：本目录为 W7_1016 时点（早期弹球版）历史证据，`pong_report_*.json` 等文件名与语义**保留原样、不作追溯修改**。游戏端**现主线 = 横版闯关 MI Pixel Run**（`bci-decoder/game/platformer/`，2026-10-21 并入并接 WS，自检 72/72）；本目录证据仅用于追溯早期弹球版端到端自检，**不作为当前 F4 验收证据**（A7 联调录屏 / A8 真人现场演示待做）。

> 归档口径见 `docs/MVP规格说明书.md` §10；证据目录总说明见 `docs/evidence/W7_1013/README.md`。
> 本批证据对应 **F4 游戏端（`bci-decoder/game/`）** 与 **解码端 WebSocket 输出**的工程验收。
>
> ⚠️ **先文档、后代码**：本目录随文档提交先行入库，其中引用的复现命令依赖 `bci-decoder/game/`
> 与 `bci-decoder/tools/verify_game_headless.py`（代码将在下一次代码提交中合入）。
> 在代码合入前，本目录的用途是**留痕**：说明做过什么、结论是什么；命令跑不通属预期。

## 1. 结论（一句话）

游戏端已能**订阅解码器 WebSocket 输出并真的驱动画面**（A7），解码器被杀后**画面继续、自动重连、超时回安全态**（F5.3），
键盘降级路径可独立演示（C 级，演示时必须说明不是脑控）。全部 **39 项端到端断言 + 17 + 39 个单测**通过。

## 2. 环境

| 项 | 值 |
|---|---|
| OS / Shell | Windows（PowerShell 5.1） |
| Python | 3.14.7（`bci-decoder/.venv`） |
| 关键依赖 | `websockets 17.2`、`pygame-ce 2.5.8`（SDL 2.32.10）、`numpy 2.5.3`、`scipy 1.18.1`、`scikit-learn 1.9.1`、`PyYAML 6.0.3`、`joblib 1.6.0` |
| 数据来源 | 合成源（`configs/demo_online.yaml`）—— **仅工程自检** |
| 显示 | 全部以 `--headless`（SDL dummy 驱动）运行；无显示器 |

## 3. 本批文件与"读什么"

| 文件 | 说明 |
|---|---|
| `pytest_decode_20261016.txt` | 解码模块单测：**17 passed** |
| `pytest_game_20261016.txt` | 游戏端单测：**39 passed** |
| `verify_game_headless_20261016.txt` | 端到端验证原始输出：**checks=39, FAILS=0**（A/B/C/D 四场景） |
| `pong_report_online_run1.json` / `run2.json` | 场景 A：真解码器在线驱动（两轮） |
| `pong_report_killed.json` | 场景 B：解码器运行中被杀（F5.3） |
| `pong_report_jsonl_2hz.json` | 场景 D：契约控制率 2 条/秒回放 |
| `pong_report_keyboard.json` | 场景 C：键盘降级路径 |
| `pong_fps_probe_keyboard_600frames.json` | 无解码器负载时的帧率基线（60.2 fps） |

`pong_report_*.json` 的 `schema` 为 `bci-pong-report/1`，计数语义：
`applied_commands + rate_limited_commands + idle_commands == commands`，
`left_commands + right_commands + idle_commands == commands`（由单测 `test_report_counters_are_self_consistent` 锁定）。

## 4. 环境信息与复现命令

```powershell
# 依赖（仅首次）
& "bci-decoder\.venv\Scripts\python.exe" -m pip install -r bci-decoder\requirements.txt

# 单测（必须在 bci-decoder\ 目录下跑；PowerShell 5.1 不支持 &&）
Set-Location bci-decoder
& ".venv\Scripts\python.exe" -m pytest -q tests
& ".venv\Scripts\python.exe" -m pytest -q "game\tests"

# 端到端（真实解码器 → 游戏端，含"解码器中途被杀"）
Set-Location ..
& "bci-decoder\.venv\Scripts\python.exe" ".deepworks\tmp\verify_game_headless.py"

# 手动演示（两个终端）
& "bci-decoder\.venv\Scripts\python.exe" -m bci_decoder.cli run --config configs/demo_online.yaml --outputs websocket   # 终端 1（在 bci-decoder\）
& "bci-decoder\.venv\Scripts\python.exe" "bci-decoder\game\pong.py" --input ws                                            # 终端 2
```

`verify_game_headless.py` 是**非交付物脚本**（放在 `.deepworks/tmp/`），四个场景：
A 全程在线两轮 → B 解码器中途被杀 → C 键盘 headless → D 契约节奏 2 条/秒。

## 5. 实测数字（如实摘录）

| 场景 | 收到消息 | 驱动指令 | 限流丢弃 | idle | 挡板位移 | 得分/失误 | 帧率 |
|---|---|---|---|---|---|---|---|
| A 在线（600 帧×2） | 3003 条/轮 | 46 | 316 | 233 | 60.9 / 80.9 px | 1/2 | 60.2 fps |
| B 中途被杀（1200 帧） | — | 26（断线前） | — | 127 | 67.1 px | 1/1 | 57.2 fps |
| D 2 Hz 回放（420 帧） | 5 | 5 | **0** | 0 | **480.0 px**（截于右边界） | 0/3 | 59.2 fps |
| C 键盘（120 帧） | 0 | 0 | 0 | 0 | 0 px | 0/0 | 59.4 fps |

- **场景 D 是"一条指令一步位移"的确定性证据**：契约控制率（2 条/秒）下 5 条指令全部下发、全部驱动、一条不被限流。
- 场景 A 的摆幅（60~460 px 之间波动）**不代表手感**：自检合成源是"尽快跑 + 极性交替"的异常输入（≈300~400 条/秒，
  远超契约的 2 条/秒），限流窗口与交替相位的相对关系随机，因此摆幅随机；真实 2 Hz 由场景 D 覆盖。

## 6. 偏差与已知问题（不藏）

1. **本轮修掉的真缺陷：消息洪流下"看着在动其实没动"。**
   首轮端到端实测 596 条指令只位移 **0.2 px**：每条新指令都从当前位置重设目标并重启 0.5 s 插值，
   同向指令互相抵消。已加**控制率限流**（`paddle.min_command_interval_seconds = 0.2`，只丢弃过快到达的重复指令，
   不改变方向与单条位移量；`idle` 冻结不受限流影响），并补 4 个回归用例。
2. **本轮修掉的真缺陷：`WebSocketSink` 绑定失败会静默不服务。**
   原实现 `self._ready.wait(timeout=5.0)` 忽略返回值、线程吞掉异常 → 端口被占用时游戏端只能干等到超时，
   日志里没有任何异常（现场演示会表现为"莫名其妙连不上"）。现在**立即抛 `RuntimeError`**，并支持 `port=0`
   由操作系统分配端口。同时该单测原用"先探测空闲端口再绑定"（Windows 上存在竞争），偶发 `TimeoutError` 失败；
   已改为 `port=0` 并复跑 **5 次全绿**。
3. **死代码修复：** `Stats.left_commands / right_commands` 从未被累加（报告里恒为 0）→ 已改为在 `on_command` 中按标签累加，
   并把"真正驱动挡板"的计数单独暴露为 `applied_commands`。
4. **帧率受同机 CPU 争抢影响：** 无解码器负载时 headless 实测 **60.2 fps**；解码器合成源"尽快跑"抢满一个核时，
   同机帧率观察到 37.9~59.7 fps 波动。**这是自检环境特性，不是游戏端性能问题**（真实解码器按 2 条/秒实时跑）。
5. **`--input ws` 的真实手感尚未由人验证：** headless 只能证明"消息→位移"通路正确；"好不好玩、跟手不跟手"需要
   真实显示器 + 真人试玩（A8 现场验收项）。
6. **未做：** 真实采集设备（企业设备型号/LSL 流名称待书面确认）、校准流程、Docker、公开数据集评测（里程碑 ③）。

## 7. 红线自查

- 全批次**不含任何准确率数字**；报告与界面均无 `acc/accuracy/准确率/正确率` 字段（端到端每轮扫描 + 单测双保险）。
- 合成数据仅作工程自检（AGENTS.md 红线 5）；**不得**据此对外报告性能。
- 未收到消息时游戏端**不编造动作**（不返回指令），只在"曾收到过且刚超时"时下发一条 `idle`（AGENTS.md 红线 1）。
- 键盘演示路径会在启动时打印 `C 级键盘输入：演示时请说明这不是脑控`。
