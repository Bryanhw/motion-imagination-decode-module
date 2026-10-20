"""Small deterministic platformer simulation independent from pygame rendering."""

from __future__ import annotations

from dataclasses import dataclass

WIDTH, HEIGHT, TILE = 320, 180, 16
GROUND_Y, UPPER_Y = 144, 96
PLAYER_W, PLAYER_H = 16, 16
GRAVITY = 500
JUMP_SPEED = -250
RUN_SPEED = 72
# A single RIGHT_HAND event launches a forward-moving jump. This gives low-rate
# inputs time to clear a wall without needing LEFT_HAND at takeoff.
JUMP_CARRY = 104
CARRY_DECAY = 34


@dataclass
class Player:
    x: float = 28
    y: float = GROUND_Y - 16
    vx: float = 0
    vy: float = 0
    grounded: bool = True
    jump_cooldown: float = 0
    coins: int = 0
    facing: int = 1
    jump_carry: float = 0


class GameController:
    """Consume validated input-layer state and own all game physics and rules."""

    def __init__(self):
        self.player = Player()
        self.previous_intent = "NONE"
        self.finished = False
        self.level_width = 960
        # Three optional coins sit along the lower route; three reward the upper route.
        self.coins = [(80, GROUND_Y - 12), (300, GROUND_Y - 12),
                      (720, GROUND_Y - 12), (150, UPPER_Y - 12),
                      (205, UPPER_Y - 12), (505, UPPER_Y - 12)]
        self.collected: set[int] = set()
        self.obstacles = [(335, GROUND_Y - 16, 16, 16),
                          (555, GROUND_Y - 16, 16, 16),
                          (690, UPPER_Y - 16, 16, 16)]
        # A solid obstacle's top is also a safe, standable surface.
        self.solids = list(self.obstacles)

    def reset(self):
        self.__init__()

    def update(self, intent: str, dt: float):
        dt = min(max(dt, 0), 0.05)
        p = self.player
        if p.jump_cooldown > 0:
            p.jump_cooldown = max(0, p.jump_cooldown - dt)
        if intent == "RIGHT_HAND" and self.previous_intent != "RIGHT_HAND" and p.grounded and p.jump_cooldown == 0:
            p.vy = JUMP_SPEED
            p.jump_carry = JUMP_CARRY
            p.grounded = False
            p.jump_cooldown = 0.24
        if intent == "LEFT_HAND":
            p.facing = 1
        # Held LEFT_HAND is sustained forward motion. A jump always starts with forward carry.
        p.vx = RUN_SPEED if intent == "LEFT_HAND" else p.jump_carry
        if intent != "LEFT_HAND":
            p.jump_carry = max(0, p.jump_carry - CARRY_DECAY * dt)

        old_x, old_y = p.x, p.y
        p.x += p.vx * dt
        # Resolve only the solid's vertical face here; its top surface is checked after gravity.
        for left, top, width, height in self.solids:
            overlaps_x = p.x + PLAYER_W > left and p.x < left + width
            overlaps_y = p.y + PLAYER_H > top and p.y < top + height
            was_left_of_solid = old_x + PLAYER_W <= left
            if overlaps_x and overlaps_y and was_left_of_solid and p.vx > 0:
                p.x = left - PLAYER_W
                # Keep the forward intent/carry while braced against the wall. A jump can
                # then spend that stored motion to clear the top without a fast midair input.

        p.vy += GRAVITY * dt
        p.y += p.vy * dt
        p.grounded = False
        surfaces = [(0, self.level_width, GROUND_Y), (112, 270, UPPER_Y), (452, 620, UPPER_Y)]
        surfaces += [(left, left + width, top) for left, top, width, _ in self.solids]
        for left, right, top in surfaces:
            overlaps_x = p.x + PLAYER_W > left and p.x < right
            crossed_top = old_y + PLAYER_H <= top and p.y + PLAYER_H >= top
            if p.vy >= 0 and crossed_top and overlaps_x:
                p.y = top - PLAYER_H
                p.vy = 0
                p.grounded = True
                break
        p.y = min(p.y, HEIGHT + 20)
        if p.grounded:
            p.jump_carry = 0
        for index, (cx, cy) in enumerate(self.coins):
            if index not in self.collected and abs((p.x + 8) - cx) < 11 and abs((p.y + 8) - cy) < 13:
                self.collected.add(index)
        if p.x >= self.level_width - 27:
            self.finished = True
        self.previous_intent = intent


def platform_spans():
    return [(0, GROUND_Y, 960), (112, UPPER_Y, 158), (452, UPPER_Y, 168)]
