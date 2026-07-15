"""Air Slice game logic.

All coordinates are normalized [0,1] (x left→right, y top→bottom), matching the
mirrored webcam frame the player sees. The client only renders state.
"""

import math
import os
import random
from itertools import count

ROUND_SECONDS = float(os.getenv("ROUND_SECONDS", "20"))
START_HOVER_SECONDS = 1.0
COUNTDOWN_SECONDS = 3.0

GRAVITY = 2.2            # normalized units / s^2
MIN_SLICE_SPEED = 0.5    # fingertip speed (units/s) needed to cut
BLADE_RADIUS = 0.02      # slack added to fruit hitboxes
COMBO_WINDOW = 0.6       # seconds between slices to keep the combo alive
COMBO_CAP = 5
BOMB_PENALTY = 30
MAX_FRUITS = 12

START_TARGET = {"x": 0.5, "y": 0.45, "r": 0.09}

FRUIT_KINDS = {
    "apple":      {"points": 10, "radius": 0.050},
    "orange":     {"points": 10, "radius": 0.050},
    "banana":     {"points": 12, "radius": 0.060},
    "watermelon": {"points": 15, "radius": 0.075},
    "bomb":       {"points": 0,  "radius": 0.055},
}
SPAWN_POOL = ["apple", "apple", "orange", "orange", "banana", "banana", "watermelon"]


def _seg_circle_hit(p1, p2, center, r):
    """Does segment p1→p2 pass within r of center?"""
    ax, ay = p1
    bx, by = p2
    cx, cy = center
    abx, aby = bx - ax, by - ay
    ab2 = abx * abx + aby * aby
    t = 0.0 if ab2 == 0 else max(0.0, min(1.0, ((cx - ax) * abx + (cy - ay) * aby) / ab2))
    px, py = ax + t * abx, ay + t * aby
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r


class Fruit:
    __slots__ = ("id", "kind", "x", "y", "vx", "vy", "r", "points")

    def __init__(self, fid, kind, x, y, vx, vy):
        self.id = fid
        self.kind = kind
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.r = FRUIT_KINDS[kind]["radius"]
        self.points = FRUIT_KINDS[kind]["points"]


class Game:
    """One game session (one websocket connection = one player at the stall)."""

    def __init__(self, leaderboard):
        self._lb = leaderboard
        self._ids = count(1)
        self._last_t = None
        self.finger = None
        self.phase = "idle"          # idle | countdown | playing | gameover
        self.score = 0
        self.combo = 0
        self.start_hover = 0.0
        self.qualifies = False
        self.submitted = False
        self._phase_t = 0.0
        self._round_end = 0.0
        self._round_start = 0.0
        self._next_spawn = 0.0
        self._last_slice_t = -1e9
        self.fruits = []

    # ------------------------------------------------------------------ update

    def update(self, fingertip, now):
        """Advance the game by one frame. Returns a list of one-shot events."""
        events = []
        dt = 0.0 if self._last_t is None else min(max(now - self._last_t, 0.0), 0.1)
        self._last_t = now

        prev = self.finger
        speed = 0.0
        if fingertip and prev and dt > 0:
            speed = math.hypot(fingertip[0] - prev[0], fingertip[1] - prev[1]) / dt
        self.finger = fingertip

        if self.phase in ("idle", "gameover"):
            self._update_start_hover(fingertip, dt, now)
        elif self.phase == "countdown":
            if now - self._phase_t >= COUNTDOWN_SECONDS:
                self._begin_round(now)
        elif self.phase == "playing":
            self._spawn_fruit(now)
            self._step_physics(dt)
            if prev and fingertip and speed >= MIN_SLICE_SPEED:
                events += self._check_slices(prev, fingertip, now)
            if now >= self._round_end:
                self._end_round()
                events.append({"type": "gameover", "score": self.score})
        return events

    def _update_start_hover(self, fingertip, dt, now):
        inside = (
            fingertip
            and math.hypot(fingertip[0] - START_TARGET["x"], fingertip[1] - START_TARGET["y"])
            <= START_TARGET["r"]
        )
        if inside:
            self.start_hover += dt
            if self.start_hover >= START_HOVER_SECONDS:
                self._begin_countdown(now)
        else:
            self.start_hover = 0.0

    def _begin_countdown(self, now):
        self.phase = "countdown"
        self._phase_t = now
        self.start_hover = 0.0
        self.score = 0
        self.combo = 0
        self.qualifies = False
        self.submitted = False
        self.fruits.clear()

    def _begin_round(self, now):
        self.phase = "playing"
        self._round_start = now
        self._round_end = now + ROUND_SECONDS
        self._next_spawn = now + 0.4
        self._last_slice_t = -1e9

    def _end_round(self):
        self.phase = "gameover"
        self.fruits.clear()
        self.combo = 0
        self.qualifies = self._lb.qualifies(self.score)

    # ----------------------------------------------------------------- fruits

    def _spawn_fruit(self, now):
        if now < self._next_spawn or len(self.fruits) >= MAX_FRUITS:
            return
        for _ in range(random.randint(1, 3)):
            kind = random.choice(SPAWN_POOL)
            self._launch(kind)
        # bombs only after the player has warmed up a bit
        if now - self._round_start > 4 and random.random() < 0.25:
            self._launch("bomb")
        self._next_spawn = now + random.uniform(0.7, 1.2)

    def _launch(self, kind):
        x = random.uniform(0.15, 0.85)
        vx = random.uniform(0.05, 0.25) * (1 if x < 0.5 else -1)
        vy = -random.uniform(1.6, 2.1)  # up; gravity brings it back down
        self.fruits.append(Fruit(next(self._ids), kind, x, 1.08, vx, vy))

    def _step_physics(self, dt):
        for f in self.fruits:
            f.x += f.vx * dt
            f.y += f.vy * dt
            f.vy += GRAVITY * dt
        self.fruits = [f for f in self.fruits if f.y < 1.25]

    def _check_slices(self, p_prev, p_now, now):
        events = []
        survivors = []
        for f in self.fruits:
            if not _seg_circle_hit(p_prev, p_now, (f.x, f.y), f.r + BLADE_RADIUS):
                survivors.append(f)
                continue
            if f.kind == "bomb":
                self.score = max(0, self.score - BOMB_PENALTY)
                self.combo = 0
                self._last_slice_t = -1e9
                events.append({"type": "bomb", "x": f.x, "y": f.y, "penalty": BOMB_PENALTY})
            else:
                self.combo = self.combo + 1 if now - self._last_slice_t <= COMBO_WINDOW else 1
                self._last_slice_t = now
                pts = f.points * min(self.combo, COMBO_CAP)
                self.score += pts
                events.append({
                    "type": "slice", "kind": f.kind,
                    "x": f.x, "y": f.y, "points": pts, "combo": self.combo,
                })
        self.fruits = survivors
        return events

    # ------------------------------------------------------------------ state

    def submit_score(self, name):
        if self.phase == "gameover" and self.qualifies and not self.submitted:
            self._lb.add(name, self.score)
            self.submitted = True

    def state(self, events):
        now = self._last_t or 0.0
        return {
            "phase": self.phase,
            "score": self.score,
            "combo": self.combo,
            "time_left": max(0.0, round(self._round_end - now, 2)) if self.phase == "playing" else 0,
            "round_seconds": ROUND_SECONDS,
            "countdown": max(0.0, round(COUNTDOWN_SECONDS - (now - self._phase_t), 2))
            if self.phase == "countdown" else 0,
            "finger": list(self.finger) if self.finger else None,
            "start": START_TARGET,
            "start_progress": min(1.0, self.start_hover / START_HOVER_SECONDS),
            "gravity": GRAVITY,
            "fruits": [
                {"id": f.id, "kind": f.kind, "x": round(f.x, 4), "y": round(f.y, 4),
                 "vx": round(f.vx, 4), "vy": round(f.vy, 4), "r": f.r}
                for f in self.fruits
            ],
            "leaderboard": self._lb.top(),
            "qualifies": self.qualifies,
            "submitted": self.submitted,
            "events": events,
        }
