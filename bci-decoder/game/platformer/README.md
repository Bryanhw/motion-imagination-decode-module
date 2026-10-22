# MI Pixel Run 闯关游戏正式版 v1.0

这是仓库中独立的横版像素平台游戏，保留原有脑控弹球。正式版包含可玩的键盘模式、JSONL 示例回放、第一关和冻结的输入接口契约。

游戏不直接读取脑电设备，也不实现解码算法；新增的 `ws` 模式会订阅本机解码器。键盘模式标为“键盘模拟”，JSONL 模式标为“数据回放”，WebSocket 演示也必须如实说明数据源（如 mock 工程自检），不能把合成数据说成真人脑控。

## 安装

在 `bci-decoder/` 目录运行。仓库的 `.venv` 已通过主依赖文件包含 `pygame-ce`；如果单独准备环境：

```powershell
python -m pip install -r game\platformer\requirements.txt
```

## 运行

在 `bci-decoder/` 目录运行：

```powershell
# 键盘模式
.venv\Scripts\python.exe -m game.platformer.main --mode keyboard

# 使用内置 JSONL 文件实际驱动同一套输入层和游戏控制器
.venv\Scripts\python.exe -m game.platformer.main --mode replay

# 指定回放文件与输入超时
.venv\Scripts\python.exe -m game.platformer.main --mode replay --replay-file game\platformer\replay_demo.jsonl --timeout 2.0

# 订阅本机解码器 WebSocket（先启动解码器，见下方联调步骤）
.venv\Scripts\python.exe -m game.platformer.main --mode ws --ws-url ws://127.0.0.1:8765
```

也可以双击 `game\platformer\start_game.ps1` 打开浏览器版。游戏地址为 `http://localhost:8766/`；本机重启后再次运行脚本即可。网页右上角的全屏按钮、双击画面或 `F` 键可以切换全屏。

## 按键与玩法

- `W` 按住：持续向前走；松开就停止主动前进。
- `D` 点按：向前跳一次。即使先按 W 顶住障碍、松开 W，再单独点 D，也会向前越障；按住 D 不会重复起跳。
- `R`：回到开始界面；`Enter` 开始；`Esc` 退出；`F` 切换全屏。

游戏为 320×180 逻辑画布，最近邻放大。上下路线都有可选金币；障碍不会扣血，掉到下层不会失败，也没有计时和移动敌人。

## 输入接口

完整契约见 [`INTERFACE.md`](INTERFACE.md)。键盘与回放适配器产生同一种 v1 决策对象，再由 `DecisionReceiver` 校验序号、处理超时，并交给 `GameController`。回放示例见 [`replay_demo.jsonl`](replay_demo.jsonl)。

`ws` 模式使用 `websocket_input.py` 订阅解码器冻结的 9 字段输出，并在游戏端转换为内部 v1 输入；不改变解码器输出字段。`left/right/idle` 分别映射为 `LEFT_HAND/RIGHT_HAND/NONE`；非 `running` 状态一律映射为 `NONE`。连接丢失时立刻进入安全待机，客户端每 0.5 秒自动重连，默认 1.5 秒无新消息也会超时到 `NONE`。网页试玩服务使用 8766 端口，避免与解码器 WebSocket 的 8765 端口冲突。

### 解码器联调与断线重连

在 `bci-decoder/` 目录，确认演示模型已生成（首次运行可执行 `python scripts/bootstrap_demo.py --config configs/demo_online.yaml`）。终端 1 启动每 4 秒交替类别的实时 mock 工程自检源：

```powershell
.venv\Scripts\python.exe -m bci_decoder.cli run --config configs/demo_game_ws.yaml
```

终端 2 启动游戏并按 Enter：

```powershell
.venv\Scripts\python.exe -m game.platformer.main --mode ws --ws-url ws://127.0.0.1:8765 --timeout 1.5
```

确认画面状态随解码器输出变化后，在终端 1 按 `Ctrl+C`。游戏应立即停在 `NONE` 安全态；再次执行终端 1 的命令后，游戏客户端自动重连并继续接收。录屏和说明需标注这是 **mock 工程链路自检**，仅证明消息通路与断线恢复，不证明算法准确率或真人实时脑控。

### 用本地 PhysioNet EDF 做回放联调

仓库提供 `data/eegmmidb_s001/` 中的三段匿名公开 EDF+ 原始记录。若尚未安装 MNE，先执行 `python -m pip install mne`。在 `bci-decoder/` 下转换第一段记录（原 EDF 不会改动）：

```powershell
python scripts/prepare_eegmmidb_replay.py --input data/eegmmidb_s001/S001R04.edf
```

准备演示模型后，在终端 1 用真实 EEG 回放启动解码器：

```powershell
python scripts/bootstrap_demo.py --config configs/demo_online.yaml
python -m bci_decoder.cli run --config configs/demo_game_eegmmidb.yaml
```

终端 2 仍运行 `python -m game.platformer.main --mode ws`。这能检查 EDF 读取、预处理、解码消息、WebSocket 传输与游戏输入链路。演示模型由合成数据训练，不能用它评价该被试的分类效果；要检查角色方向和关卡手感，请用上面的 mock 联调配置。

## 测试

从 `bci-decoder/` 目录运行：

```powershell
.venv\Scripts\python.exe -m pytest -q game\platformer\tests
```

其中 `test_main_events.py` 会向实际 pygame 主循环发送不带 `repeat` 属性的 D 键事件，并检查只跳一次及 `ws` 模式不会被键盘 D 触发。

## 目录

```text
game/platformer/
├── main.py              pygame 窗口与第一关
├── physics.py           关卡、物理、金币、碰撞和终点
├── input_layer.py       键盘/回放适配器、统一决策接收器
├── websocket_input.py   解码器 WebSocket 客户端、断线重连和输出映射
├── tests/               输入和游戏逻辑测试
├── web/                 浏览器版与全屏画面
├── serve_web.py         本机网页服务
├── start_game.ps1       Windows 启动脚本
├── replay_demo.jsonl    回放示例消息
├── requirements.txt     独立运行所需的 pygame-ce
└── INTERFACE.md         v1 输入契约与接入说明
```
