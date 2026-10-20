# -*- coding: utf-8 -*-
"""
握拳小人 · 脑控演示游戏（runner.py）· 马里奥像素风
====================================================

玩法：
  想象【左手握紧】→ 角色开始缓慢向前走（连续想象 = 一直走）；
                    走到水管前会被拦下来，并提示你该跳了。
  想象【右手握紧】→ 自带向前的跳跃：
      · 前方没有水管 → 向前跳一格；
      · 前方有水管   → 大跳越过水管（完整抛物线，落到水管后面那一格）。
  什么都没想 / 系统不确定 → 站着待命。

金币规则（两种指令各有各的专属奖励）：
  · 低金币挂在【空格】上方，人头高度 —— 想象左手【走过去】直接吃到；
  · 高金币挂在【水管正上方】 —— 只有想象右手【越障大跳】飞到半空才吃得到；
  · 水管前一格和后一格不会生成金币（不会出现"想吃却被跳跃占用"的死结）。

设计说明：
  · 脑电指令天生有 1~2 秒延迟，所以全程不需要快速反应：走路是缓慢的，
    跳跃是自动向前的，水管是固定不动的，碰到也不会死。
  · 小人始终钉在屏幕固定位置，"前进"是世界向左滚——跳跃才有干净的抛物线。
  · 像素风：低分辨率画布（240x135）画好后整体放大 4 倍，红白机的味道。

放置位置：bci-decoder/game/runner.py（和 pong.py 同一个文件夹）

运行方式（在 bci-decoder/ 目录下执行）：
    python game\\runner.py                        # 键盘模式（默认）：← 走（可按住），↑ 跳
    python game\\runner.py --input ws             # 脑电模式：连解码器的 WebSocket
    python game\\runner.py --input jsonl          # 降级模式：读 outputs/latest.jsonl

脑电模式要先启动解码器（另一个窗口）：
    python -m bci_decoder.cli run --config configs/demo_online.yaml --outputs console websocket --chunks 200

依赖：pygame-ce（requirements.txt 已含）；ws 模式用 websockets（requirements.txt 已含）。
"""

import argparse
import json
import math
import os
import random
import sys
import threading
import time

import pygame

# ======================= 可调参数（想改手感就动这里） =======================
SCALE = 4                    # 像素放大倍数（窗口 = 逻辑分辨率 x SCALE）
LW, LH = 240, 135            # 逻辑分辨率（像素风画布，别改）
WIDTH, HEIGHT = LW * SCALE, LH * SCALE   # 实际窗口 960x540
FPS = 60

GROUND_H = 27                # 地面高度（逻辑像素）
CELL = 21                    # 一格的宽度（逻辑像素）
PLAYER_IDX = 2               # 角色固定在从左数第几格（世界滚动，角色不动）
N_CELLS = LW // CELL + 4     # 世界里同时存在多少格

WALK_TIME  = 0.92            # 走一格花几秒（越大走得越慢）；0.92 = 原 1.1 × 5/6，即整体提速 6/5（组长拍板 2026-10-20）
WALK_QUEUE_MAX = 3           # 最多囤积几条"继续走"指令（防误触发堆太多）
JUMP_ANIM  = 0.70            # 向前小跳时长（秒）
JUMP_H     = 29              # 向前小跳最大高度（逻辑像素）
LEAP_ANIM  = 0.90            # 越障大跳时长（秒）
LEAP_H     = 36              # 越障大跳最大高度（逻辑像素）
BLOCK_ANIM = 0.35            # 被水管拦住时的抖动时长（秒）

COIN_LOW_Y  = 14             # 低金币离地高度（小人头顶，走路经过吃到）
COIN_HIGH_Y = 26             # 高金币离地高度（水管上方，越障大跳吃到）

P_OBSTACLE      = 0.25       # 新格子是水管的概率（水管不会连续出现）
P_COIN          = 0.30       # 空格挂低金币的概率
P_COIN_OBSTACLE = 0.55       # 水管正上方挂高金币的概率
SAFE_START      = 4          # 开局前 N 格保证无水管（起步安全）

MIN_CONFIDENCE = 0.0         # 指令最低把握度（解码端已过滤，0 = 不再过滤；想更稳可改 0.5）
SIGNAL_TIMEOUT = 3.0         # 脑电模式：超过这么久没新消息 → 显示"等待信号"（断线安全态）

WS_URL = "ws://127.0.0.1:8765"   # 解码器 WebSocket 地址（与 outputs/websocket.py 一致）

# ---- 马里奥经典配色（逻辑像素世界用） ----
SKY      = (92, 148, 252)    # 红白机天蓝
CLOUD    = (252, 252, 252)
GRASS    = (80, 200, 60)     # 草皮
DIRT     = (200, 130, 70)    # 土
DIRT_D   = (170, 105, 55)    # 土块斑点
GRID     = (64, 170, 50)     # 格子线
PIPE_G   = (60, 180, 60)     # 水管绿
PIPE_D   = (30, 120, 40)     # 水管阴影
PIPE_L   = (150, 240, 130)   # 水管高光
COIN     = (250, 200, 60)
COIN_D   = (210, 160, 30)
BRICK    = (190, 90, 50)     # 悬浮砖
BRICK_D  = (140, 60, 30)
HUD_BG   = (20, 26, 36)
WHITE    = (255, 255, 255)
DARK     = (40, 48, 60)
BAR_OK   = (92, 200, 120)
BAR_BG   = (70, 78, 92)
HINT     = (255, 90, 90)

# ---- 像素小人（12x13，字符 = 颜色；马里奥风：红帽蓝背带） ----
PALETTE = {
    "R": (200, 40, 40),      # 帽子红
    "H": (120, 72, 30),      # 头发棕
    "F": (255, 205, 160),    # 脸
    "E": (30, 30, 30),       # 眼睛
    "B": (60, 100, 220),     # 衣服蓝
    "L": (40, 70, 170),      # 裤子
    "S": (120, 72, 30),      # 鞋
}
_HEAD = [
    "....RRRR....",
    "...RRRRRR...",
    "...HHHHHH...",
    "...HFFFFH...",
    "...HFEFFH...",
    "....FFFF....",
    "...BBBBBB...",
    "..BBBBBBBB..",
    "..BB.BB.BB..",
    "...BBBBBB...",
]
SPRITE_IDLE = _HEAD + [
    "...LL..LL...",
    "...LL..LL...",
    "..SSS..SSS..",
]
SPRITE_WALK1 = _HEAD + [
    "...LL.LL....",
    "..LL...LL...",
    "..SS....SS..",
]
SPRITE_WALK2 = _HEAD + [
    "....LL.LL...",
    "...LL...LL..",
    "...SS....SS.",
]
SPRITE_JUMP = _HEAD + [
    "...LLLLLL...",
    "....LLLL....",
    "....SSSS....",
]


# ======================= 输入层：指令从哪来 =======================
# 三种来源统一产出 (label, confidence, stamp)：
#   label ∈ {"left", "right", "idle"}；confidence ∈ [0,1]；
#   stamp 用来去重——同一条消息只响应一次。

class KeyboardSource:
    """键盘模式：← 或 A = 左手握紧（向前走，可按住连走）；↑ / W / 空格 = 右手握紧（向前跳）。"""
    name = "键盘（←走 / ↑跳）"

    def __init__(self):
        self._pending = None

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._pending = ("left", 1.0, time.time())
            elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_SPACE):
                self._pending = ("right", 1.0, time.time())

    def poll(self):
        cmd, self._pending = self._pending, None
        return cmd, True

    def close(self):
        pass


class WsSource:
    """脑电模式：后台线程连解码器 WebSocket，保留最新一条消息。
    解码器没开 / 断了 → 自动每 2 秒重连，游戏本身不卡。"""
    name = "脑电（WebSocket）"

    def __init__(self, url):
        self.url = url
        self._latest = None
        self._seen_stamp = None
        self.connected = False
        self._lock = threading.Lock()
        self._stop = False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        from websockets.sync.client import connect  # websockets>=17 自带的同步客户端
        while not self._stop:
            try:
                with connect(self.url) as ws:
                    self.connected = True
                    for raw in ws:
                        if self._stop:
                            break
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        with self._lock:
                            self._latest = (
                                msg.get("label", "idle"),
                                float(msg.get("confidence", 0.0)),
                                msg.get("t_data"),
                            )
            except Exception:
                self.connected = False
                time.sleep(2.0)

    def poll(self):
        with self._lock:
            latest = self._latest
        if latest is None:
            return None, self.connected
        label, conf, stamp = latest
        if stamp == self._seen_stamp:
            return None, self.connected
        self._seen_stamp = stamp
        return (label, conf, time.time()), self.connected

    def close(self):
        self._stop = True


class JsonlSource:
    """降级模式：每 0.25 秒读一次 latest.jsonl 的最后一行（零网络依赖）。"""
    name = "离线（jsonl 文件）"

    def __init__(self, path):
        self.path = path
        self._seen_stamp = None
        self._last_check = 0.0
        self._latest = None
        self.connected = False

    def poll(self):
        now = time.time()
        if now - self._last_check > 0.25:
            self._last_check = now
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    lines = [ln for ln in f.read().strip().splitlines() if ln.strip()]
                if lines:
                    msg = json.loads(lines[-1])
                    self._latest = (
                        msg.get("label", "idle"),
                        float(msg.get("confidence", 0.0)),
                        msg.get("t_data"),
                    )
                    self.connected = True
            except (OSError, json.JSONDecodeError):
                self.connected = False
        if self._latest is None:
            return None, self.connected
        label, conf, stamp = self._latest
        if stamp == self._seen_stamp:
            return None, self.connected
        self._seen_stamp = stamp
        return (label, conf, now), self.connected

    def close(self):
        pass


# ======================= 游戏层 =======================

def gen_cell(prev_cell):
    """生成一个新格子（prev_cell 会被原地修正，见下）。规则：
      · 水管不连续（水管后面必为空格）；
      · 空格挂低金币，但【水管后一格】不挂（留给落地，不诱惑）；
      · 水管正上方可以挂高金币（越障大跳时吃）；
      · 若新格子是水管，则抹掉前一格的低金币（水管前一格不生成金币）。
    """
    prev_obstacle = prev_cell["obstacle"]
    obstacle = False if prev_obstacle else (random.random() < P_OBSTACLE)
    if obstacle:
        coin = random.random() < P_COIN_OBSTACLE
        prev_cell["coin"] = False
    else:
        coin = (not prev_obstacle) and (random.random() < P_COIN)
    return {"obstacle": obstacle, "coin": coin}


class Particle:
    """金币粒子：吃到金币时向四周飞溅的小像素块。"""
    def __init__(self, x, y):
        ang = random.uniform(0, 2 * math.pi)
        sp = random.uniform(15, 45)
        self.x, self.y = float(x), float(y)
        self.vx = math.cos(ang) * sp
        self.vy = math.sin(ang) * sp - 30   # 整体向上喷
        self.life = 0.6

    def update(self, dt):
        self.vy += 150 * dt   # 重力往下拉
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

    def draw(self, surf):
        if self.life <= 0:
            return
        color = COIN if self.life > 0.25 else WHITE   # 快消失时变白闪一下
        surf.fill(color, (int(self.x), int(self.y), 2, 2))


class Game:
    """整个游戏世界：一串格子 + 一个钉在固定位置的小人。
    小人"前进"是世界往左滚；跳跃时世界继续滚、小人只上下动，
    这样抛物线才干净完整。"""

    def __init__(self):
        self.cells = [{"obstacle": False, "coin": random.random() < P_COIN}]
        for _ in range(SAFE_START - 1):
            self.cells.append({"obstacle": False, "coin": random.random() < P_COIN})
        while len(self.cells) < N_CELLS:
            self.cells.append(gen_cell(self.cells[-1]))

        self.score = 0
        self.particles = []
        # 动作状态机：idle / walk / jump / leap / block
        self.action = "idle"
        self.t = 0.0
        self.dur = 0.0
        self.scroll = 0.0       # 世界滚动偏移（逻辑像素，负数 = 向左滚）
        self.walk_queue = 0     # 走路中收到的"继续走"指令数（连续想左手 = 一直走）
        self.coin_popup = 0.0   # "+1" 飘字计时
        self.hint = ""
        self.hint_t = 0.0

    @property
    def busy(self):
        """动作播放中不响应新指令（脑电每 0.5 秒一条，偶尔丢一条无妨，
        但绝不能让动作叠罗汉）。例外：走路中可以接受"继续走"。"""
        return self.action != "idle"

    def _ahead(self):
        return self.cells[PLAYER_IDX + 1]

    # ---- 两条指令的入口 ----
    def on_left(self):
        """左手握紧 = 向前走。走路中再收到 → 存进队列，走完这段接着走
        （连续想象左手 = 持续缓慢前进）。前方有水管 → 被拦下（抖动 + 提示）。"""
        if self.action == "walk":
            if self.walk_queue < WALK_QUEUE_MAX:
                self.walk_queue += 1
            return
        if self.busy:
            return
        if self._ahead()["obstacle"]:
            self._start("block", BLOCK_ANIM)
            self._set_hint("前方有水管！想象【右手握紧】跳过去")
        else:
            self._start("walk", WALK_TIME)

    def on_right(self):
        """右手握紧 = 自带向前的跳。前方有水管 → 越障大跳（2 格）；
        没有 → 向前小跳（1 格）。"""
        if self.busy:
            return
        if self._ahead()["obstacle"]:
            self._start("leap", LEAP_ANIM)
        else:
            self._start("jump", JUMP_ANIM)

    def _start(self, action, dur):
        self.action, self.t, self.dur = action, 0.0, dur

    def _set_hint(self, text, secs=1.6):
        self.hint, self.hint_t = text, secs

    def _scroll_world(self, n):
        for _ in range(n):
            self.cells.pop(0)
            self.cells.append(gen_cell(self.cells[-1]))

    def _jump_h_now(self):
        """当前跳跃高度（非跳跃状态 = 0）。"""
        if self.action == "jump":
            return math.sin(math.pi * min(self.t / self.dur, 1.0)) * JUMP_H
        if self.action == "leap":
            return math.sin(math.pi * min(self.t / self.dur, 1.0)) * LEAP_H
        return 0.0

    def _collect(self, cell, x, y):
        """吃掉一枚金币：粒子爆发 + 计分 + 飘字。"""
        cell["coin"] = False
        self.score += 1
        self.coin_popup = 0.8
        for _ in range(12):
            self.particles.append(Particle(x, y))

    def _collect_coins(self, ground_y):
        """金币拾取判定（每帧跑）：
          · 低金币（空格，人头高度）：走路经过 / 站着时吃到；跳太高反而吃不到；
          · 高金币（水管正上方）：只有越障大跳飞到半空（p>=0.45）才吃得到。
        """
        px = PLAYER_IDX * CELL + CELL / 2
        feet_y = ground_y - self._jump_h_now()
        if feet_y > ground_y - 20:   # 没怎么跳起来（走路/站立/被拦）
            for i, cell in enumerate(self.cells):
                if cell["coin"] and not cell["obstacle"]:
                    cx = i * CELL + self.scroll + CELL / 2
                    if abs(cx - px) < CELL * 0.45:
                        self._collect(cell, cx, ground_y - COIN_LOW_Y)
        if self.action == "leap" and self.t / self.dur >= 0.45:
            cell = self.cells[PLAYER_IDX + 1]
            if cell["obstacle"] and cell["coin"]:
                cx = (PLAYER_IDX + 1) * CELL + self.scroll + CELL / 2
                self._collect(cell, cx, ground_y - COIN_HIGH_Y)

    def update(self, dt):
        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.particles:
            p.update(dt)
        if self.coin_popup > 0:
            self.coin_popup -= dt
        if self.hint_t > 0:
            self.hint_t -= dt

        if self.busy:
            self.t += dt
            p = min(self.t / self.dur, 1.0)

            if self.action == "walk":
                self.scroll = -CELL * p
                if p >= 1.0:
                    self._scroll_world(1)
                    self.scroll = 0.0
                    if self.walk_queue > 0:
                        if self._ahead()["obstacle"]:
                            # 下一段要撞水管了：拦下来，提示该跳了
                            self.walk_queue = 0
                            self._start("block", BLOCK_ANIM)
                            self._set_hint("前方有水管！想象【右手握紧】跳过去")
                        else:
                            self.walk_queue -= 1
                            self._start("walk", WALK_TIME)
                    else:
                        self.action = "idle"

            elif self.action == "jump":       # 向前小跳 1 格
                self.scroll = -CELL * p
                if p >= 1.0:
                    self._scroll_world(1)
                    self.scroll = 0.0
                    self.action = "idle"

            elif self.action == "leap":       # 越障大跳 2 格
                self.scroll = -2 * CELL * p   # 水管从小人脚下穿过
                if p >= 1.0:
                    self._scroll_world(2)     # 生成规则保证落点是空格
                    self.scroll = 0.0
                    self.action = "idle"

            elif self.action == "block":
                if p >= 1.0:
                    self.action = "idle"

        self._collect_coins(LH - GROUND_H)

    # ---- 小人的屏幕位置与当前帧 ----
    def player_pos(self, ground_y, now):
        x = PLAYER_IDX * CELL + CELL // 2   # 固定！不随世界滚动（抛物线的关键）
        dx = 0.0
        if self.action == "block":
            dx = math.sin(self.t / self.dur * math.pi * 4) * 1.5
        bob = math.sin(now * 2.2) * 0.5 if self.action == "idle" else 0
        return int(x + dx), int(ground_y - self._jump_h_now() + bob)

    def player_sprite(self):
        if self.action in ("jump", "leap"):
            return SPRITE_JUMP
        if self.action == "walk":
            return SPRITE_WALK1 if int(self.t * 7) % 2 == 0 else SPRITE_WALK2
        return SPRITE_IDLE


# ======================= 像素风绘制 =======================

def draw_sprite(surf, sprite, x, y):
    """把字符画像素小人画到逻辑画布上（x, y = 左上角）。"""
    for r, row in enumerate(sprite):
        for c, ch in enumerate(row):
            if ch != ".":
                surf.set_at((x + c, y + r), PALETTE[ch])


def draw_cloud(surf, x, y):
    pygame.draw.rect(surf, CLOUD, (x, y + 3, 26, 6))
    pygame.draw.rect(surf, CLOUD, (x + 6, y, 14, 6))


def draw_pipe(surf, x, ground_y):
    """绿色水管（马里奥那个）。"""
    pygame.draw.rect(surf, PIPE_G, (x + 4, ground_y - 12, CELL - 8, 12))   # 管身
    pygame.draw.rect(surf, PIPE_G, (x + 2, ground_y - 15, CELL - 4, 4))    # 管口翻边
    pygame.draw.rect(surf, PIPE_D, (x + 4, ground_y - 12, 2, 12))          # 左侧阴影
    pygame.draw.rect(surf, PIPE_L, (x + CELL - 7, ground_y - 12, 2, 12))   # 右侧高光
    pygame.draw.rect(surf, PIPE_D, (x + 2, ground_y - 15, CELL - 4, 1))    # 翻边上沿


def draw_coin(surf, x, y, now, i):
    """金币：两帧交替（圆/窄条）模拟旋转闪光。"""
    cy = y + math.sin(now * 3 + i) * 1.0
    if int(now * 4 + i) % 2 == 0:
        pygame.draw.circle(surf, COIN_D, (int(x), int(cy)), 4)
        pygame.draw.circle(surf, COIN, (int(x), int(cy)), 3)
        hx, hy = int(x) - 1, int(cy) - 1
        if 0 <= hx < LW and 0 <= hy < LH:   # 滚到屏幕边缘时高光点坐标会出界，跳过
            surf.set_at((hx, hy), WHITE)    # 高光点
    else:
        pygame.draw.rect(surf, COIN, (int(x) - 1, int(cy) - 3, 2, 6))


def draw_ground(surf, ground_y):
    """草皮 + 土层（斑点用固定伪随机，稳定不闪）。"""
    pygame.draw.rect(surf, GRASS, (0, ground_y, LW, 3))
    pygame.draw.rect(surf, DIRT, (0, ground_y + 3, LW, LH - ground_y - 3))
    for gx in range(0, LW, 6):
        for gy in range(ground_y + 6, LH, 5):
            if (gx * 7 + gy * 13) % 5 == 0:
                pygame.draw.rect(surf, DIRT_D, (gx, gy, 2, 2))


def draw_world(surf, game, ground_y, now):
    for i, cell in enumerate(game.cells):
        cx = i * CELL + game.scroll
        if cx < -CELL or cx > LW + CELL:
            continue
        pygame.draw.line(surf, GRID, (int(cx), ground_y), (int(cx), LH), 1)  # 格子线
        if cell["obstacle"]:
            draw_pipe(surf, int(cx), ground_y)
            if cell["coin"]:   # 水管正上方的高金币（越障大跳专属）
                draw_coin(surf, cx + CELL / 2, ground_y - COIN_HIGH_Y, now, i)
        elif cell["coin"]:     # 空格上的低金币（走路经过就能吃）
            draw_coin(surf, cx + CELL / 2, ground_y - COIN_LOW_Y, now, i)


def make_coin_icon(scale):
    """HUD 右上角用的大金币图标。"""
    s = pygame.Surface((8, 8), pygame.SRCALPHA)
    pygame.draw.circle(s, COIN_D, (4, 4), 4)
    pygame.draw.circle(s, COIN, (4, 4), 3)
    s.set_at((3, 3), WHITE)
    return pygame.transform.scale(s, (8 * scale, 8 * scale))


# ======================= 主循环 =======================

def load_font(size):
    """找系统自带中文字体（Windows 有微软雅黑/黑体），找不到就用默认字体。"""
    for name in ("microsoftyahei", "simhei", "simsun"):
        path = pygame.font.match_font(name)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def main():
    ap = argparse.ArgumentParser(description="握拳小人 · 脑控演示游戏（像素风）")
    ap.add_argument("--input", choices=["keyboard", "ws", "jsonl"], default="keyboard",
                    help="keyboard=键盘调试（默认）；ws=连解码器；jsonl=读文件（降级）")
    ap.add_argument("--file", default=os.path.join("outputs", "latest.jsonl"),
                    help="jsonl 模式的文件路径（默认 outputs/latest.jsonl）")
    ap.add_argument("--selftest", type=int, default=0,
                    help="跑 N 帧后自动退出（冒烟自检用，0=不启用）")
    args = ap.parse_args()

    source = (KeyboardSource() if args.input == "keyboard"
              else WsSource(WS_URL) if args.input == "ws"
              else JsonlSource(args.file))

    pygame.init()
    pygame.display.set_caption("握拳小人（左手握紧=向前走，右手握紧=向前跳）")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.key.set_repeat(400, 400)   # 按住 ← 会持续发"走"，模拟连续想象左手
    clock = pygame.time.Clock()
    font, big = load_font(20), load_font(28)
    coin_icon = make_coin_icon(3)

    world = pygame.Surface((LW, LH))   # 逻辑画布：所有游戏画面先画在这，最后放大

    game = Game()
    label, conf = "idle", 0.0
    last_signal_t = time.time()
    frame = 0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        now = time.time()
        frame += 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif args.input == "keyboard":
                source.handle_event(event)

        # 取一条新指令（没有新指令就是 None）
        cmd, connected = source.poll()
        if cmd is not None:
            new_label, new_conf, _ = cmd
            last_signal_t = now
            if new_conf >= MIN_CONFIDENCE:
                if new_label == "left":
                    game.on_left()
                    label, conf = "left", new_conf
                elif new_label == "right":
                    game.on_right()
                    label, conf = "right", new_conf
                else:
                    label, conf = "idle", new_conf
            else:
                label, conf = "idle", new_conf
        elif args.input != "keyboard" and now - last_signal_t > SIGNAL_TIMEOUT:
            label, conf = "idle", 0.0   # 断线安全态：站着等，绝不乱动

        game.update(dt)

        # ---------- 画游戏世界（逻辑画布，像素风） ----------
        ground_y = LH - GROUND_H
        world.fill(SKY)
        draw_cloud(world, 40, 18)
        draw_cloud(world, 120, 10)
        draw_cloud(world, 195, 26)
        # 两块悬浮砖当装饰
        for bx in (92, 152):
            pygame.draw.rect(world, BRICK, (bx, 42, 10, 5))
            pygame.draw.rect(world, BRICK_D, (bx, 42, 10, 5), 1)
        draw_ground(world, ground_y)
        draw_world(world, game, ground_y, now)
        # 小人（钉在固定格子上，世界从脚下滚过）
        px, py = game.player_pos(ground_y, now)
        draw_sprite(world, game.player_sprite(), px - 6, py - 13)
        # 金币粒子
        for p in game.particles:
            p.draw(world)
        # HUD 像素底条
        pygame.draw.rect(world, HUD_BG, (0, 0, LW, 15))

        # ---------- 放大 4 倍上屏（硬边像素风的关键一步） ----------
        screen.blit(pygame.transform.scale(world, (WIDTH, HEIGHT)), (0, 0))

        # ---------- HUD 文字（画在窗口层，保证中文清晰） ----------
        if game.hint_t > 0:
            text, color = game.hint, HINT
        else:
            text, color = {"left": "想象：左手握紧 → 向前走",
                           "right": "想象：右手握紧 → 向前跳！",
                           "idle": "等待指令…"}[label], WHITE
        screen.blit(big.render(text, True, color), (18, 16))
        # 把握度条（指令文字右边）
        pygame.draw.rect(screen, BAR_BG, (WIDTH - 480, 22, 130, 16), border_radius=8)
        pygame.draw.rect(screen, BAR_OK, (WIDTH - 480, 22, int(130 * max(0.0, min(conf, 1.0))), 16), border_radius=8)
        screen.blit(font.render(f"把握度 {conf:.0%}", True, WHITE), (WIDTH - 340, 20))
        # 右上角：金币统计（图标 + 数量，最显眼的位置）
        screen.blit(coin_icon, (WIDTH - 190, 14))
        screen.blit(big.render(f"× {game.score}", True, COIN), (WIDTH - 158, 16))
        # 吃金币的 "+1" 飘字
        if game.coin_popup > 0:
            rise = int((0.8 - game.coin_popup) * 150)
            screen.blit(big.render("+1", True, COIN),
                        (px * SCALE - 10, py * SCALE - 120 - rise))
        # 左下角小字：输入模式 + 连接状态
        state = f"输入：{source.name} ｜ " + ("已连接 ✓" if connected else "未连接（等解码器/文件）")
        screen.blit(font.render(state, True, DARK), (14, HEIGHT - 28))

        pygame.display.flip()

        if args.selftest and frame >= args.selftest:
            print(f"[selftest] 跑满 {frame} 帧，一切正常；score={game.score}")
            running = False

    source.close()
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
