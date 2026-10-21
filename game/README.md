# MI Pixel Run：运动想象输入试玩平台游戏

这是一个用 Python 和 pygame-ce 编写的横向复古像素平台小游戏。当前版本用键盘或预设 JSONL 决策检查玩法和接口；**它没有连接实时脑电设备，也没有实现脑电解码**。画面会明显标注“键盘模拟”或“数据回放”。

也可以直接在浏览器里玩：在 Windows 上双击 `game/start_game.ps1`，它会启动本地网页并打开 `http://localhost:8765/`。把该地址加入收藏即可再次打开。网页右上角有**全屏**按钮，也支持双击游戏画面或按 `F` 切换全屏。只要本机游戏服务还在运行，之后不必重启 pygame 窗口。

本机固定地址仅能从这台电脑访问。若要局域网其他设备访问，可在 PowerShell 中运行 `$env:GAME_HOST = "0.0.0.0"; py -m game.serve_web`，再用本机局域网 IP 和端口 8765 打开；若设备防火墙拦截连接，需要在 Windows 防火墙允许本地 Python 服务。按 `Ctrl+C` 可停止网页服务。

## 安装

先在仓库项目目录打开 PowerShell。游戏使用自己的可选依赖清单，不会把 pygame-ce 加到原有的数据核验依赖中：

```powershell
cd "D:\CST AI\脑电运动想象\motion-imagery-eeg"
py -m pip install -r game\requirements.txt
```

如果项目虚拟环境已经建好，可改用：

```powershell
.\.venv\Scripts\python.exe -m pip install -r game\requirements.txt
```

Python 3.10 或更新版本均可。pygame-ce 安装后提供 `pygame` 导入模块。

## 运行

### 浏览器版（Windows）

在项目根目录运行：

```powershell
.\game\start_game.ps1
```

脚本会启动本机网页服务并打开浏览器中的 `http://localhost:8765/`。再次运行时会复用已在 8765 端口监听的游戏服务。游戏页可选择键盘模拟或数据回放，右上角按钮、双击画面或 `F` 可切换全屏。若 PowerShell 的执行策略阻止脚本，可在当前窗口运行 `Set-ExecutionPolicy -Scope Process Bypass` 后重试。

### pygame 版

在项目根目录运行以下命令：

```powershell
# 键盘完整试玩
py -m game.main --mode keyboard

# 使用内置 JSONL 示例回放
py -m game.main --mode replay

# 指定回放文件并把输入超时调成 2 秒
py -m game.main --mode replay --replay-file game\replay_demo.jsonl --timeout 2.0
```

Enter 开始；`R` 在开始画面或通关后重开；`Esc` 退出。游戏是 320×180 逻辑画布，以最近邻放大至 960×540。初始游戏只处理契约输入：W 是持续前进，D 按下只跳一次。空中惯性能帮助只收到一次 RIGHT_HAND 时越过障碍；D 必须松开后再按，落地并结束冷却后才能起跳。

上下路线各放有三枚金币作为可选奖励，不需要收齐。固定障碍只让角色停顿。上层平台有缺口，走出边缘会落到下层。没有倒计时或敌人。

## 输入契约

阅读 [`INTERFACE.md`](INTERFACE.md)。键盘和回放适配器都产出同一种对象，经过 `DecisionReceiver` 的校验、序号去重和超时逻辑后，交给同一个 `GameController`。JSONL 一行一个决策，字段示例：

```json
{"version":1,"sequence":42,"intent":"LEFT_HAND","source":"replay","timestamp":12.75}
```

完整的小型示例在 [`replay_demo.jsonl`](replay_demo.jsonl)。回放按行间隔逐条驱动游戏，播放结束后不会伪造输入；最后的主动状态会按超时转成 NONE。

## 目录

```text
game/
├── main.py              pygame 窗口、像素绘制和开始/通关界面
├── web/                 可收藏访问的浏览器版本（含全屏模式）
├── serve_web.py         本机固定端口网页服务
├── start_game.ps1       启动网页服务并打开浏览器的 Windows 脚本
├── platformer.py        关卡布局、角色物理、碰撞、金币和终点
├── input_layer.py       Decision、键盘/回放适配器和统一接收器
├── test_input_layer.py  标准库 unittest 输入与控制逻辑检查
├── replay_demo.jsonl    小型静态回放示例
├── requirements.txt     游戏专用可选依赖 pygame-ce
├── INTERFACE.md         v1 输入契约及未来设备接入说明
└── README.md            本说明
```

## 未来接入解码模块

在 `input_layer.py` 新增 `DecoderInputAdapter`，把解码输出映射到 `LEFT_HAND`、`RIGHT_HAND`、`NONE`，使用 `source="device"` 和严格递增序号，再送到 `DecisionReceiver.receive(...)`。设备事件的时间戳用于追踪原始事件，连接新鲜度依然只按程序本地收到消息的单调时间计算。未来模块只需替换输入适配器，无需修改角色物理、金币、平台、碰撞或游戏控制器。现在没有该适配器和实时脑电能力；不要把键盘试玩或静态示例回放描述为实时脑控。

## 检查

在项目根目录执行：

```powershell
py -m unittest game.test_input_layer -v
```
