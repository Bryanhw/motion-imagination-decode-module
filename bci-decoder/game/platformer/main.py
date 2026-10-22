"""Run the pixel-art demo: python -m game.main --mode keyboard"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

try:
    import pygame
except ImportError as exc:
    raise SystemExit("缺少 pygame-ce。请运行：py -m pip install -r game/requirements.txt") from exc

from .input_layer import DecisionReceiver, KeyboardInputAdapter, ReplayInputAdapter
from .physics import GameController, GROUND_Y, HEIGHT, TILE, UPPER_Y, WIDTH, platform_spans
from .websocket_input import WebSocketInputAdapter

ROOT = Path(__file__).resolve().parent
NAVY = (17, 31, 64)
SKY = (30, 54, 96)
GROUND = (130, 76, 49)
BRICK = (155, 96, 58)
GRASS = (90, 170, 88)
GOLD = (247, 195, 57)
CREAM = (255, 235, 186)
WHITE = (247, 244, 222)
PINK = (235, 112, 102)


def px(surface, color, x, y, w=1, h=1):
    pygame.draw.rect(surface, color, (int(x), int(y), max(1, int(w)), max(1, int(h))))


def draw_tile(surface, x, y, ground=False):
    px(surface, GROUND if ground else BRICK, x, y, TILE, TILE)
    px(surface, GRASS, x, y, TILE, 3)
    px(surface, (107, 61, 45), x + 1, y + 8, 14, 1)
    px(surface, (179, 116, 70), x + 3, y + 4, 2, 3)
    px(surface, (179, 116, 70), x + 10, y + 11, 3, 3)


def draw_coin(surface, x, y, frame):
    radius = 5 if frame % 4 < 2 else 3
    pygame.draw.ellipse(surface, (119, 78, 34), (x - radius + 1, y - 4 + 1, radius * 2, 9))
    pygame.draw.ellipse(surface, GOLD, (x - radius, y - 4, radius * 2, 9))
    px(surface, (255, 230, 121), x - max(1, radius // 2), y - 2, 2, 5)


def draw_player(surface, player, camera, intent, frame):
    x, y = int(player.x - camera), int(player.y)
    # 16x16 hand-drawn sprite, with readable idle, walk and jump poses.
    px(surface, (45, 35, 52), x + 4, y + 13, 9, 3)
    px(surface, PINK, x + 4, y + 1, 9, 7)
    px(surface, (255, 181, 151), x + 6, y, 5, 2)
    px(surface, (255, 206, 168), x + 6, y + 3, 6, 4)
    px(surface, NAVY, x + 10, y + 3, 2, 2)
    px(surface, (102, 180, 215), x + 3, y + 8, 10, 6)
    px(surface, (79, 132, 184), x + 5, y + 9, 6, 4)
    px(surface, (245, 191, 79), x + 4, y + 14, 4, 2)
    px(surface, (245, 191, 79), x + 10, y + 14, 4, 2)
    if intent == "RIGHT_HAND":
        px(surface, WHITE, x + 2, y + 7, 2, 2)
        px(surface, WHITE, x + 13, y + 6, 2, 2)
    elif intent == "LEFT_HAND":
        stride = frame % 2
        px(surface, (245, 191, 79), x + 2 + stride, y + 14, 3, 2)
        px(surface, (245, 191, 79), x + 10 - stride, y + 14, 3, 2)


def draw_scene(screen, game, camera, intent, source_label, frame, title=None, overlay=None):
    screen.fill(SKY)
    for i in range(4):
        cx, cy = (48 + i * 93 - camera // 3) % 370 - 25, 28 + (i % 2) * 17
        px(screen, (81, 108, 142), cx, cy, 23, 4)
        px(screen, (81, 108, 142), cx + 6, cy - 4, 12, 4)
    for x, y, w in platform_spans():
        start = max(0, (x // TILE) * TILE)
        for world_x in range(start, x + w, TILE):
            sx = world_x - camera
            if -TILE <= sx <= WIDTH:
                draw_tile(screen, sx, y, y == GROUND_Y)
    # Checkpoint flag and level-end flag.
    for wx, flag_color in ((24, GRASS), (930, GOLD)):
        sx = wx - camera
        if -12 < sx < WIDTH:
            px(screen, CREAM, sx, GROUND_Y - 34, 2, 34)
            px(screen, flag_color, sx + 2, GROUND_Y - 34, 13, 8)
    for x, y, w, h in game.obstacles:
        sx = x - camera
        if -20 < sx < WIDTH:
            px(screen, (75, 48, 47), sx, y + 2, w, h - 2)
            px(screen, (189, 82, 68), sx + 2, y, w - 4, 6)
            px(screen, (243, 151, 102), sx + 4, y + 3, 3, 2)
    for index, (x, y) in enumerate(game.coins):
        if index not in game.collected:
            draw_coin(screen, int(x - camera), y, frame)
    draw_player(screen, game.player, camera, intent, frame)
    font = pygame.font.Font(None, 10)
    screen.blit(font.render(f"COINS {len(game.collected):02}/{len(game.coins):02}", True, GOLD), (7, 7))
    screen.blit(font.render(f"SOURCE: {source_label}", True, CREAM), (211, 7))
    state_text = {"LEFT_HAND": "FORWARD", "RIGHT_HAND": "JUMP", "NONE": "IDLE"}[intent]
    screen.blit(font.render(f"STATE: {state_text}", True, WHITE), (250, 17))
    screen.blit(font.render("W FORWARD   D JUMP   ESC QUIT", True, (196, 207, 214)), (7, 167))
    if overlay:
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((7, 15, 34, 190))
        screen.blit(veil, (0, 0))
        big = pygame.font.Font(None, 24)
        medium = pygame.font.Font(None, 11)
        text = big.render(title or "", True, GOLD)
        screen.blit(text, text.get_rect(center=(WIDTH // 2, 67)))
        for i, line in enumerate(overlay):
            label = medium.render(line, True, WHITE)
            screen.blit(label, label.get_rect(center=(WIDTH // 2, 96 + i * 15)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="键盘试玩/契约 JSONL 回放平台游戏")
    parser.add_argument("--mode", choices=("keyboard", "replay", "ws"), default="keyboard")
    parser.add_argument("--replay-file", type=Path, default=ROOT / "replay_demo.jsonl")
    parser.add_argument("--timeout", type=float, default=1.5, help="replay/device 输入超时秒数")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8765", help="解码器 WebSocket 输出地址")
    args = parser.parse_args(argv)
    websocket = None
    try:
        if args.mode == "ws":
            websocket = WebSocketInputAdapter(args.ws_url)
            websocket.start()
        pygame.init()
        window = pygame.display.set_mode((WIDTH * 3, HEIGHT * 3))
        pygame.display.set_caption("MI Pixel Run 闯关游戏正式版 — 键盘模拟/数据回放")
        canvas = pygame.Surface((WIDTH, HEIGHT))
        clock = pygame.time.Clock()
        keyboard = KeyboardInputAdapter()
        receiver = DecisionReceiver(args.timeout)
        replay = ReplayInputAdapter(args.replay_file) if args.mode == "replay" else None
        game = GameController()
        started, running = False, True
        mode_label = {"keyboard": "键盘模拟", "replay": "数据回放", "ws": "解码器 WebSocket"}[args.mode]
        ws_status = "CONNECTING" if websocket else ""
        frame = 0
        w_held = False
        d_held = False
        while running:
            dt = min(clock.tick(60) / 1000, 0.05)
            now = time.monotonic()
            jump_event = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN and not started:
                    started = True
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_r and (game.finished or not started):
                    game.reset()
                    keyboard = KeyboardInputAdapter()
                    receiver = DecisionReceiver(args.timeout)
                    if replay:
                        replay = ReplayInputAdapter(args.replay_file)
                    started = False
                    w_held = False
                    d_held = False
                elif args.mode == "keyboard" and event.type == pygame.KEYDOWN and event.key == pygame.K_w:
                    w_held = True
                elif args.mode == "keyboard" and event.type == pygame.KEYUP and event.key == pygame.K_w:
                    w_held = False
                elif args.mode == "keyboard" and event.type == pygame.KEYUP and event.key == pygame.K_d:
                    d_held = False
                elif args.mode == "keyboard" and event.type == pygame.WINDOWFOCUSLOST:
                    w_held = False
                    d_held = False
                elif (args.mode == "keyboard" and started and event.type == pygame.KEYDOWN
                      and event.key == pygame.K_d and not getattr(event, "repeat", False)
                      and not d_held):
                    d_held = True
                    receiver.receive(keyboard.press_jump(now), now)
                    jump_event = True
            if websocket:
                for event_type, payload in websocket.poll():
                    if event_type == "connecting":
                        if ws_status != "CONNECTED":
                            ws_status = "CONNECTING"
                    elif event_type == "connected":
                        receiver.reset_remote()
                        ws_status = "CONNECTED"
                    elif event_type == "disconnected":
                        receiver.reset_remote()
                        ws_status = "SAFE IDLE"
                    elif event_type == "connection_error":
                        ws_status = "RECONNECTING"
                    elif event_type == "decision":
                        if started and not game.finished:
                            receiver.receive(payload, received_at=now)
                        ws_status = "CONNECTED"
                    elif event_type == "invalid":
                        receiver.reset_remote()
                        ws_status = "SAFE IDLE"
                        print(f"拒绝无效解码器消息：{payload}")
            if started and not game.finished:
                if args.mode == "keyboard":
                    if not jump_event:
                        decisions = keyboard.poll(w_held, d_held, now)
                        for decision in decisions:
                            receiver.receive(decision, now)
                elif args.mode == "replay":
                    decision = replay.poll(now) if replay else None
                    if decision:
                        receiver.receive(decision, received_at=now)
                intent = receiver.current(now).intent
                game.update(intent, dt)
            else:
                intent = receiver.current(now).intent
            camera = max(0, min(game.level_width - WIDTH, int(game.player.x - 88)))
            if not started:
                if args.mode == "keyboard":
                    lines = [f"正式版 v1.0 · {mode_label}  |  W 前进，D 向前跳跃",
                             "W 是持续状态，D 按下只跳一次；收集金币后到达终点。",
                             "按 Enter 开始    R 重新开始    Esc 退出"]
                elif args.mode == "ws":
                    lines = [f"订阅 {args.ws_url}", f"DECODER: {ws_status}",
                             "连接中断或输入超时会自动进入 NONE 安全态。",
                             "按 Enter 开始    R 重新开始    Esc 退出"]
                else:
                    lines = [f"正式版 v1.0 · {mode_label}  |  示例数据驱动相同游戏逻辑",
                             "W 是持续状态，D 按下只跳一次；收集金币后到达终点。",
                             "按 Enter 开始    R 重新开始    Esc 退出"]
                draw_scene(canvas, game, camera, intent, mode_label, frame, "MI PIXEL RUN · 正式版", lines)
            elif game.finished:
                draw_scene(canvas, game, camera, intent, mode_label, frame, "LEVEL CLEAR!",
                           [f"金币 {len(game.collected)}/{len(game.coins)}（金币不是通关条件）", "按 R 重新开始    Esc 退出"])
            else:
                source_label = f"WS {ws_status}" if websocket else mode_label
                draw_scene(canvas, game, camera, intent, source_label, frame)
            pygame.transform.scale(canvas, window.get_size(), window)
            pygame.display.flip()
            frame += 1
    finally:
        pygame.quit()
        if websocket:
            websocket.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
