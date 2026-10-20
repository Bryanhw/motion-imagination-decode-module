# WebSocket 测试接收超时：复现与修复

日期：2026-10-20；触发：王释贤本人在 PowerShell 运行 `.venv\Scripts\python.exe -m pytest`，截图显示 `15 passed / 1 failed`，失败为 `test_websocket_sink_broadcasts_frozen_contract` 的 `TimeoutError()`。

## 受控复现

- 原测试只等客户端握手完成，然后从主线程发送三条决策。
- 服务端登记订阅发生在独立事件循环中。握手完成与服务端 `_clients` 登记之间存在调度间隔；无订阅者时 `emit()` 按现有逻辑丢弃消息。
- 仅在诊断进程内将 `_handler` 的订阅登记延迟 50 ms，未修改源码。原测试复现相同 `TimeoutError()`；三次发送时订阅者数量均为 0，观测值 `[0, 0, 0]`。
- 无延迟的原测试连续五轮通过，说明一次通过不能排除该时序缺陷。用户截图的精确调度未被记录，但上述缺陷能解释并复现同样症状。

## 本机修复

- 仅修改 `bci-decoder/tests/test_websocket_sink.py`。
- 客户端握手后，通过服务端事件循环有界等待订阅登记完成，再发送并验证消息；等待失败也进入清理路径。
- 原契约用例参数化覆盖正常与 50 ms 延迟登记两种场景；关闭幂等测试保留。
- 未延长消息接收超时来掩盖丢消息，未修改广播行为、业务代码、协议字段、窗口、步长或依赖版本。

## 修复后证据

- WebSocket 3 项连续 5 轮全通过：`王释贤_20261020_ws_registration_5runs.txt`。
- 全量 `17 passed in 2.56s`，退出码 0：`王释贤_20261020_pytest_after_ws_fix.txt`。
- 用户首次失败截图：`王释贤_20261020_pytest_user_failure.png`。
- 本机新增的一项为延迟登记回归场景，**不是**历史文档声称存在的端口绑定失败用例；原远端仍收集 16 项，变更未提交或推送。
- 用户本人已在原 PowerShell 再次运行 pytest，结果 **17 passed in 2.85s**；成功截图为 `王释贤_20261020_pytest_user_success.png`。下一步继续 mock；A1 仍需四人独立完整跑通，且当前仓库尚缺游戏代码。
