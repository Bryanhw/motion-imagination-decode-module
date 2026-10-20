# -*- coding: utf-8 -*-
"""runner.py（握拳小人 · 格子版脑控游戏）单元测试。

跑法（在 bci-decoder/ 目录下）：
    pytest -q game\\tests

机制被测面：
  左手 = 缓慢向前走（走路中可续走；撞水管被拦并提示）；
  右手 = 自带向前的跳（前方空格跳 1 格；前方水管越障大跳 2 格）；
  低金币（空格）走路经过吃；高金币（水管正上方）越障大跳半空吃；
  水管前后一格不生成金币。
"""
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # 无窗口跑测试（CI/无显示器环境可跑）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import runner  # noqa: E402

random.seed(42)  # 结果可复现


# ---------------- 工具 ----------------

def run_action(game, secs=2.0):
    """以 60fps 推进游戏世界 secs 秒。"""
    for _ in range(int(secs * 60)):
        game.update(1 / 60)


def new_game():
    """可控的新游戏：清空所有水管和金币。"""
    g = runner.Game()
    for c in g.cells:
        c["obstacle"], c["coin"] = False, False
    return g


def ids(g):
    return list(map(id, g.cells))


# ---------------- 生成规则 ----------------

def test_generation_rules():
    cells = [{"obstacle": False, "coin": False}]
    for _ in range(1000):
        cells.append(runner.gen_cell(cells[-1]))
    assert all(not (a["obstacle"] and b["obstacle"])
               for a, b in zip(cells, cells[1:])), "水管不得连续出现"
    assert all(not cells[i - 1]["coin"] for i, c in enumerate(cells)
               if c["obstacle"] and i > 0), "水管前一格不得有金币"
    assert all(not cells[i + 1]["coin"] for i, c in enumerate(cells)
               if c["obstacle"] and i < len(cells) - 1), "水管后一格不得有金币"
    assert any(c["obstacle"] and c["coin"] for c in cells), "水管正上方应能长金币"


# ---------------- 左手：缓慢向前走 ----------------

def test_walk_scrolls_one_cell():
    g = new_game()
    before = g.cells[1]
    g.on_left()
    assert g.action == "walk"
    run_action(g)
    assert g.action == "idle"
    assert g.cells[0] is before and len(g.cells) == runner.N_CELLS


def test_walk_queue_keeps_walking():
    """连续想左手 = 一直走：walk 中再收到 left 进队列，走完自动续走。"""
    g = new_game()
    snap = ids(g)
    g.on_left()
    g.on_left()
    assert g.walk_queue == 1
    run_action(g, 3.0)
    assert ids(g)[:len(snap) - 2] == snap[2:] and g.action == "idle"


def test_walk_queue_blocked_by_pipe():
    """续走撞水管：走完当前段后被拦下（block + 提示），不再前进。"""
    g = new_game()
    g.cells[runner.PLAYER_IDX + 2]["obstacle"] = True
    snap = ids(g)
    g.on_left()
    g.on_left()
    run_action(g, 1.2)   # 第一段走完 → 应触发 block
    assert g.action == "block" and g.walk_queue == 0
    assert g.hint != "" and g.hint_t > 0
    run_action(g, 1.0)
    assert ids(g)[:len(snap) - 1] == snap[1:]   # 只滚了 1 格


def test_left_blocked_when_pipe_ahead():
    """静止时前方有水管，左手被拦：block + 提示 + 世界不动。"""
    g = new_game()
    g.cells[runner.PLAYER_IDX + 1]["obstacle"] = True
    snap = ids(g)
    g.on_left()
    assert g.action == "block"
    run_action(g)
    assert ids(g) == snap


# ---------------- 右手：自带向前的跳 ----------------

def test_leap_over_pipe_collects_high_coin():
    """越障大跳：滚 2 格；半空吃到水管正上方的高金币。"""
    g = new_game()
    g.cells[runner.PLAYER_IDX + 1] = {"obstacle": True, "coin": True}
    snap = ids(g)
    g.on_right()
    assert g.action == "leap"
    run_action(g, 0.6)   # p≈0.67 > 0.45，应已吃到高金币
    assert g.score == 1
    run_action(g, 1.0)
    assert ids(g)[:len(snap) - 2] == snap[2:]
    assert not g.cells[runner.PLAYER_IDX]["obstacle"]   # 落点是空格


def test_jump_forward_collects_landing_coin():
    """向前小跳：滚 1 格；吃到落点格的低金币。"""
    g = new_game()
    g.cells[runner.PLAYER_IDX + 1]["coin"] = True
    snap = ids(g)
    g.on_right()
    assert g.action == "jump"
    run_action(g, 1.5)
    assert ids(g)[:len(snap) - 1] == snap[1:]
    assert g.score == 1


def test_walk_collects_low_coin():
    """走路经过直接吃脚下低金币。"""
    g = new_game()
    g.cells[runner.PLAYER_IDX]["coin"] = True
    g.on_left()
    run_action(g, 0.3)
    assert g.score == 1 and not g.cells[runner.PLAYER_IDX]["coin"]


# ---------------- busy 锁 ----------------

def test_busy_lock():
    g = new_game()
    g.on_right()
    g.on_left()
    g.on_right()
    assert g.action == "jump" and g.walk_queue == 0   # jump 中指令全被忽略

    g2 = new_game()
    g2.on_left()
    g2.on_right()
    assert g2.action == "walk"   # walk 中 right 被忽略


# ---------------- 开局安全 ----------------

def test_safe_start():
    g = runner.Game()
    assert not any(c["obstacle"] for c in g.cells[:4])


# ---------------- 渲染冒烟 ----------------

def test_render_smoke():
    """走/跳/越障 + 高金币水管 + 粒子，全程绘制不得抛异常。"""
    surf = runner.pygame.Surface((runner.LW, runner.LH))
    ground_y = runner.LH - runner.GROUND_H

    g = runner.Game()
    for c in g.cells:
        c["obstacle"], c["coin"] = False, True   # 全屏低金币，含左边缘格
    g.on_left()
    for _ in range(20):
        g.update(1 / 60)
        runner.draw_ground(surf, ground_y)
        runner.draw_world(surf, g, ground_y, 0.0)
        px, py = g.player_pos(ground_y, 0.0)
        runner.draw_sprite(surf, g.player_sprite(), px - 6, py - 13)

    g = new_game()
    g.cells[runner.PLAYER_IDX + 1] = {"obstacle": True, "coin": True}   # 高金币水管
    g.on_right()
    for _ in range(60):
        g.update(1 / 60)
        runner.draw_world(surf, g, ground_y, 1.0)
        px, py = g.player_pos(ground_y, 1.0)
        runner.draw_sprite(surf, g.player_sprite(), px - 6, py - 13)
        for pt in g.particles:
            pt.draw(surf)
    assert g.score == 1
