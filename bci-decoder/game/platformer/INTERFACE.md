# 输入接口契约（v1）

游戏控制器只接收 `DecisionReceiver` 提供的意图状态，不检查按键，也不连接设备。输入适配器接收原始来源的输出，再发送统一的决策对象：

```json
{"version":1,"sequence":42,"intent":"LEFT_HAND","source":"keyboard","timestamp":12.75}
```

对象包含且只包含这五个必要字段。`version` 当前为整数 `1`；`sequence` 为每个来源独立递增的非负整数；`timestamp` 是生成此事件时由来源记录的数字时间。`intent` 只能是 `LEFT_HAND`、`RIGHT_HAND` 或 `NONE`，`source` 只能是 `keyboard`、`replay` 或 `device`。

## 意图语义

- `LEFT_HAND` 是持续状态：收到新的有效决策后持续前进，直到新决策改变意图。编码中的“左手/右手”表示解码类别，不代表屏幕向左/向右移动。
- `RIGHT_HAND` 是边沿触发：从其它状态收到它时最多尝试跳跃一次。持续的 RIGHT_HAND 不重复跳跃；只有状态先回到另一个意图后，新的 RIGHT_HAND 才有下一次触发机会。角色还必须已落地并且冷却结束。
- `NONE` 清除主动前进，不触发跳跃。跳跃本身留下短暂、衰减的水平惯性。
- 每次有效的 `RIGHT_HAND` 起跳都会自带明显的向前惯性；即使此前没有 `LEFT_HAND`，或已松开 W，也能单独越过面前的固定障碍。
- 上层平台之间有间隔，角色从平台边缘离开时受重力落到下层；关卡边界外溢时由物理和镜头继续处理，不扣分。
- 固定障碍会令角色短暂停住；没有生命值、失败判定或移动敌人。

## 键盘映射

- 按住 W = `LEFT_HAND`（持续前进）。
- D 从松开变为按下时 = `RIGHT_HAND`（一次跳跃尝试）。按住 D 不会重复输出跳跃；必须松开再按。
- W 松开且无其他有效输入 = `NONE`（停止主动前进）。
- 同时按住 W 并按下 D 会在持续前进中发出一次 RIGHT_HAND。
- 实际操作可先按住 W 顶到障碍，再松开 W、只点一下 D；D 本身会触发向前跳，不需要 W 和 D 同时按。

浏览器和 pygame 窗口都在 D 的按下事件到达时立即产生 RIGHT_HAND，因此很短的点按也不会因为帧轮询漏掉。W 的持续状态仍由按键状态维护，松开立即发出 NONE，不依赖网络式超时。

## 顺序、时间与安全失效

接收器按来源追踪最新的序号；重复或较小的 `sequence` 被忽略。外部 `timestamp` 保留以便记录和检查，但**永远不用于连接新鲜度计算**。新鲜度使用收到消息时记录的本地单调时钟 `received_at`。`keyboard` 由释放边沿立即发 `NONE`，不设置超时；`replay` 和 `device` 的超时可用 `--timeout` 配置（秒，默认 1.5）。超时后意图变成 `NONE` 并停止主动前进。适配器仍须持续发消息或显式发 NONE；旧消息无法续命。

## 接入方式

```text
键盘 ──> KeyboardInputAdapter ──┐
                                 ├──> DecisionReceiver ──> GameController.update(intent, dt)
JSONL ──> ReplayInputAdapter ───┤
解码器 ─> 新建 DecoderInputAdapter ┘
```

键盘、回放与未来设备共享校验、序号、超时和物理路径。未来适配器应把设备类别原样映射为 intent，把每个输出映射为严格递增序号、`source="device"` 及自己的事件时间，再传给 `DecisionReceiver.receive(message, received_at=本地单调时钟)`。无需更改关卡或物理。输入来源可能切换；每个来源各自维护序号空间。

示例格式和时序见 `replay_demo.jsonl`。当前游戏没有实时设备连接或脑电分类模型；回放是静态示例数据演示，键盘模式是人工模拟。
