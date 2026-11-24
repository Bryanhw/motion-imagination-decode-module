# B2 Docker 草稿评估（2026-11-24）

> 归属：`最终汇报前任务总览_20261119.md` B2 ｜ 承接：`docs/阎浩文M4_第4周收口对表_20261117.md` §3（X6 ⑤）。
> **属性：草稿评估，非正式交付。**本机无 Docker，未实跑，仅书面论证 + 交付期验证清单。

## 1. 结论（一句话）

**可行性高；本轮只出草稿、不实跑；正式做排交付期；不阻塞任何功能件。**

## 2. 交付物属性（Docker 化的对象是什么）

- **对象**：`bci-decoder` 解码模块（含 WebSocket 输出），**不是游戏画面**。游戏端（platformer，pygame-ce）默认本地跑，容器可选承载。
- **运行形态**：`python -m bci_decoder.cli run --config configs/demo_online.yaml --outputs websocket`（WS 默认 `127.0.0.1:8765`，见 `config.py` ws_port=8765）。
- **资源需求**：纯 CPU、无 GPU、演示可完全离线（无网络需求）→ 天然适合容器。

## 3. 可行性判断

| 维度 | 判断 | 依据 |
|---|---|---|
| 语法/依赖 | 高 | 核心依赖全部为 PyPI 包，本机 Python 3.14.7 已验证有 wheel（numpy / scipy / scikit-learn / websockets） |
| 可选依赖 | 中 | `pylsl`（liblsl 的 desc 不同步限制需在容器内复验加载）；pyriemann/mne/onnxruntime 为可选，不进基础镜像 |
| 运行形态 | 高 | 无窗口、纯 CLI + WS，天然适合容器 |
| **验证缺口** | **本机无 Docker，无法实跑 smoke** | 已明确记录，不掩盖 |

## 4. Dockerfile 草稿（骨架，未在容器验证）

```dockerfile
# 交付期以官方 python:3.14 系 slim 镜像为准（tag 需在 Docker 主机实测确认）
FROM python:3.14-slim

# 非 root 运行（安全）
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# 先装依赖，用镜像层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 只拷贝运行所需（不拷 artifacts / tests / .venv）
COPY bci_decoder/ bci_decoder/
COPY scripts/ scripts/
COPY configs/ configs/

USER app

# 解码模块默认 WS 输出端口
EXPOSE 8765

# 入口：mock 源自检；真采路径由 config 里的 source 控制
CMD ["python", "-m", "bci_decoder.cli", "run", "--config", "configs/demo_online.yaml", "--outputs", "websocket"]
```

### 4.1 实跑前建议补的细节（交付期再做，本轮不实现）

- `requirements.txt` 追加锁版本：用 `pip freeze` 导出或 `requirements.lock.txt`；
- 基线镜像 tag：`python:3.14-slim` 需在 Docker 主机 `docker run python:3.14-slim python -V` 实测确认；
- 如需重建模型：把 `artifacts/*.joblib` 显式 `COPY` 进镜像并挂卷（本轮未含，避免镜像膨胀）；
- 健康检查可选：`HEALTHCHECK CMD python -c "import websockets; ..."`（演示可不加）。

## 5. 交付期验证清单（实跑时必做，勿跳过）

1. 容器内 `cli run`（mock 源）30s，心跳/JsonL 正常，无 traceback；决策率与裸机一致（同 config、同 seed）。
2. WS 输出：宿主连 `127.0.0.1:8765`（需 `-p 8765:8765` 并确认 host 绑定），收到逐行 JSON 消息。
3. 可选 `pylsl`：容器内装 `pylsl>=1.16`，复验 liblsl 在 slim 镜像的加载（liblsl 原生库路径）。
4. 有窗口的机器上可加：游戏端连容器 WS 源端到端。
5. 记录镜像大小、`cli benchmark` 纯计算耗时分布，与裸机对照（**只作工程证据，不报准确率**——红线）。

## 6. 与本轮其他证据的关系

- B1 稳定性（replay 30min soak）证明解码链路长时间稳定 → 容器化后的行为预期一致，可在交付期复用同样 soak 脚本；
- B3 LSL mock 证明接口层代码就绪 → 若容器内启用 LSL 源，需复验 liblsl 原生库加载（见 §5.3）。

## 7. 痕迹与产出

- 依据：`docs/阎浩文M4_第4周收口对表_20261117.md` §3.3（承接骨干）
- 本证据：`docs/evidence/M4_B2_docker_eval_20261124/README.md`