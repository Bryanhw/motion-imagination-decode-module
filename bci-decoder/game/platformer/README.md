# MI Pixel Run 闯关游戏正式版 v1.0

这是仓库中独立的横版像素平台游戏，保留原有脑控弹球。正式版包含可玩的键盘模式、JSONL 示例回放、第一关和冻结的输入接口契约。

**当前没有连接实时脑电设备，也没有实现脑电解码。** 键盘模式标为“键盘模拟”，回放模式标为“数据回放”，两者都不能称为实时脑控。

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
```

也可以双击 `game\platformer\start_game.ps1` 打开浏览器版。游戏地址为 `http://localhost:8766/`；本机重启后再次运行脚本即可。网页右上角的全屏按钮、双击画面或 `F` 键可以切换全屏。

## 按键与玩法

- `W` 按住：持续向前走；松开就停止主动前进。
- `D` 点按：向前跳一次。即使先按 W 顶住障碍、松开 W，再单独点 D，也会向前越障；按住 D 不会重复起跳。
- `R`：回到开始界面；`Enter` 开始；`Esc` 退出；`F` 切换全屏。

游戏为 320×180 逻辑画布，最近邻放大。上下路线都有可选金币；障碍不会扣血，掉到下层不会失败，也没有计时和移动敌人。

## 输入接口

完整契约见 [`INTERFACE.md`](INTERFACE.md)。键盘与回放适配器产生同一种 v1 决策对象，再由 `DecisionReceiver` 校验序号、处理超时，并交给 `GameController`。回放示例见 [`replay_demo.jsonl`](replay_demo.jsonl)。

未来接入解码器时，在 `input_layer.py` 增加 `DecoderInputAdapter`，把现有解码类别转换为 `LEFT_HAND`、`RIGHT_HAND`、`NONE`，再走统一接收器。此游戏目前没有读取解码器的 WebSocket 或实时设备；无需改物理、关卡、金币和碰撞代码。网页试玩服务使用 8766 端口，避免与解码器 WebSocket 的 8765 端口冲突。

## 测试

从 `bci-decoder/` 目录运行：

```powershell
.venv\Scripts\python.exe -m pytest -q game\platformer\tests
```

## 目录

```text
game/platformer/
├── main.py              pygame 窗口与第一关
├── physics.py           关卡、物理、金币、碰撞和终点
├── input_layer.py       键盘/回放适配器、统一决策接收器
├── tests/               输入和游戏逻辑测试
├── web/                 浏览器版与全屏画面
├── serve_web.py         本机网页服务
├── start_game.ps1       Windows 启动脚本
├── replay_demo.jsonl    回放示例消息
├── requirements.txt     独立运行所需的 pygame-ce
└── INTERFACE.md         v1 输入契约与接入说明
```
