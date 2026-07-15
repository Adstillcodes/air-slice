"""Air Slice — native desktop UI (pygame).

Lowest-latency version for the stall: OpenCV reads the webcam directly,
MediaPipe tracks in-process on a background thread, pygame renders at 60 fps.
Same game logic / leaderboard as the browser version (app.game, app.leaderboard).

Run:  python -m app.desktop      (ESC quits, F11 toggles fullscreen)
"""

import math
import random
import threading
import time

import cv2
import pygame

from .game import Game
from .leaderboard import Leaderboard
from .sounds import Sfx
from .tracker import HandTracker

WIN_W, WIN_H = 1280, 960
CAM_W, CAM_H = 640, 480
TRACK_W, TRACK_H = 320, 240   # tracking runs on a downscaled frame for speed
TRAIL_SECONDS = 0.25

GREEN = (46, 230, 168)
YELLOW = (255, 213, 74)
RED = (255, 82, 82)
WHITE = (240, 245, 255)

JUICE = {
    "apple": (255, 82, 82),
    "orange": (255, 167, 38),
    "banana": (255, 233, 92),
    "watermelon": (255, 79, 109),
    "bomb": (154, 160, 180),
}


# --------------------------------------------------------------------- camera

class Camera(threading.Thread):
    """Grabs mirrored webcam frames and runs hand tracking off the render loop."""

    daemon = True

    def __init__(self):
        super().__init__()
        self.frame_rgb = None     # mirrored, CAM_W x CAM_H
        self.frame_id = 0
        self.fingertip = None
        self.error = None
        self._quit = threading.Event()

    def run(self):
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
        if not cap.isOpened():
            self.error = "Could not open the webcam. Close other apps using it (e.g. the browser tab) and restart."
            return
        tracker = HandTracker()
        try:
            while not self._quit.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.02)
                    continue
                frame = cv2.flip(frame, 1)  # mirror so it matches what the player sees
                small = cv2.resize(frame, (TRACK_W, TRACK_H))
                self.fingertip = tracker.fingertip(small)
                self.frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frame_id += 1
        finally:
            cap.release()
            tracker.close()

    def stop(self):
        self._quit.set()


# -------------------------------------------------------------------- sprites

def _make_sprite(kind, px):
    """Pre-render one fruit as a pygame Surface (emoji fonts don't render in SDL)."""
    s = pygame.Surface((px, px), pygame.SRCALPHA)
    c = px // 2
    r = int(px * 0.42)
    if kind == "apple":
        pygame.draw.circle(s, (220, 40, 40), (c, c + int(px * 0.05)), r)
        pygame.draw.circle(s, (255, 120, 110), (c - r // 3, c - r // 4), r // 3)
        pygame.draw.line(s, (110, 70, 30), (c, c - r + int(px * 0.02)), (c + r // 5, c - r - int(px * 0.08)), max(3, px // 24))
        pygame.draw.ellipse(s, (80, 190, 90), (c + r // 6, c - r - int(px * 0.10), r // 2, r // 4))
    elif kind == "orange":
        pygame.draw.circle(s, (255, 152, 24), (c, c), r)
        pygame.draw.circle(s, (255, 200, 90), (c - r // 3, c - r // 3), r // 3)
        pygame.draw.circle(s, (90, 180, 90), (c, c - r), max(4, px // 16))
    elif kind == "banana":
        body = pygame.Surface((px, px), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, int(px * 0.9), int(px * 0.38))
        rect.center = (c, c)
        pygame.draw.ellipse(body, (250, 220, 60), rect)
        pygame.draw.ellipse(body, (255, 240, 140), rect.inflate(-px // 5, -px // 5))
        pygame.draw.circle(body, (120, 85, 40), (rect.left + px // 24, c), max(4, px // 18))
        pygame.draw.circle(body, (120, 85, 40), (rect.right - px // 24, c), max(4, px // 18))
        s = pygame.transform.rotozoom(body, 40, 1.0)
    elif kind == "watermelon":
        pygame.draw.circle(s, (40, 140, 70), (c, c), r)
        pygame.draw.circle(s, (225, 240, 210), (c, c), int(r * 0.86))
        pygame.draw.circle(s, (255, 79, 109), (c, c), int(r * 0.76))
        for i in range(6):
            a = i * math.pi / 3 + 0.4
            d = r * 0.42
            pygame.draw.ellipse(s, (30, 25, 30),
                                (c + d * math.cos(a) - px * 0.03, c + d * math.sin(a) - px * 0.045,
                                 px * 0.06, px * 0.09))
    elif kind == "bomb":
        pygame.draw.circle(s, (45, 48, 60), (c, c + int(px * 0.05)), r)
        pygame.draw.circle(s, (90, 95, 115), (c - r // 3, c - r // 5), r // 3)
        pygame.draw.line(s, (140, 100, 60), (c, c - r + int(px * 0.06)), (c + int(px * 0.16), c - r - int(px * 0.10)), max(4, px // 20))
        spark = (c + int(px * 0.18), c - r - int(px * 0.12))
        pygame.draw.circle(s, (255, 180, 40), spark, max(5, px // 14))
        pygame.draw.circle(s, (255, 240, 160), spark, max(3, px // 24))
    return s


# ----------------------------------------------------------------------- app

class App:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 256)  # small buffer = low audio latency
        pygame.init()
        pygame.display.set_caption("Air Slice — IEEE RAS")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.SCALED)
        self.clock = pygame.time.Clock()
        self.fonts = {
            size: pygame.font.SysFont("segoeui", size, bold=True)
            for size in (18, 24, 28, 34, 44, 56, 72, 96, 190)
        }
        self.game = Game(Leaderboard())
        self.cam = Camera()
        self.overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        self.dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        self.dim.fill((5, 8, 18, 90))
        self.sprites = {}
        self.cam_surface = None
        self.cam_frame_id = -1
        self.trail = []
        self.particles = []
        self.floaters = []
        self.flash_until = 0.0
        self.name_text = ""
        self.prev_phase = "idle"
        self.sfx = Sfx()
        self.st = None
        self.prev_countdown_n = 0

    def sprite(self, kind, r):
        key = kind
        if key not in self.sprites:
            self.sprites[key] = _make_sprite(kind, int(r * 2.5 * WIN_H))
        return self.sprites[key]

    # ------------------------------------------------------------------ input

    def handle_events(self):
        entering_name = self.game.phase == "entername"
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return False
                if ev.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif entering_name:
                    if ev.key == pygame.K_RETURN:
                        self.game.submit_name(self.name_text)
                        self.sfx.play("submit")
                    elif ev.key == pygame.K_BACKSPACE:
                        self.name_text = self.name_text[:-1]
                    elif ev.unicode and (ev.unicode.isalnum() or ev.unicode in " _-") and len(self.name_text) < 12:
                        self.name_text += ev.unicode.upper()
        return True

    # ------------------------------------------------------------------- tick

    def tick(self):
        now = time.monotonic()
        events = self.game.update(self.cam.fingertip, now)
        self.st = self.game.state([])

        if self.game.phase != self.prev_phase:
            if self.game.phase == "entername":
                self.name_text = ""
            elif self.game.phase == "gameover":
                self.sfx.play("gameover")
                if self.game.qualifies:
                    self.sfx.play("highscore")
            elif self.game.phase == "playing" and self.prev_phase == "countdown":
                self.sfx.play("go")
            self.prev_phase = self.game.phase

        if self.game.phase == "countdown":
            n = math.ceil(self.st["countdown"])
            if n != self.prev_countdown_n and n > 0:
                self.sfx.play("tick")
            self.prev_countdown_n = n
        else:
            self.prev_countdown_n = 0

        if self.game.finger:
            self.trail.append((self.game.finger, now))
        self.trail = [(p, t) for p, t in self.trail if now - t < TRAIL_SECONDS]

        for e in events:
            if e["type"] == "slice":
                self.sfx.play("slice")
                self.sfx.combo(e["combo"])
                self.burst(e["x"] * WIN_W, e["y"] * WIN_H, JUICE[e["kind"]], 16)
                text = f"+{e['points']}" + (f"  x{e['combo']}" if e["combo"] > 1 else "")
                self.floaters.append({"x": e["x"] * WIN_W, "y": e["y"] * WIN_H,
                                      "text": text, "life": 1.0,
                                      "color": YELLOW if e["combo"] > 1 else WHITE})
            elif e["type"] == "bomb":
                self.sfx.play("bomb")
                self.burst(e["x"] * WIN_W, e["y"] * WIN_H, JUICE["bomb"], 26)
                self.floaters.append({"x": e["x"] * WIN_W, "y": e["y"] * WIN_H,
                                      "text": f"-{e['penalty']}", "life": 1.0, "color": RED})
                self.flash_until = now + 0.18

    def burst(self, x, y, color, n):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(120, 520)
            self.particles.append({"x": x, "y": y,
                                   "vx": math.cos(a) * v, "vy": math.sin(a) * v - 140,
                                   "life": 1.0, "size": random.uniform(4, 11), "color": color})

    # ------------------------------------------------------------------- draw

    def draw(self, dt):
        now = time.monotonic()

        if self.cam.frame_rgb is not None and self.cam.frame_id != self.cam_frame_id:
            surf = pygame.image.frombuffer(self.cam.frame_rgb.tobytes(), (CAM_W, CAM_H), "RGB")
            self.cam_surface = pygame.transform.scale(surf, (WIN_W, WIN_H))
            self.cam_frame_id = self.cam.frame_id
        if self.cam_surface:
            self.screen.blit(self.cam_surface, (0, 0))
        else:
            self.screen.fill((5, 6, 12))
        self.screen.blit(self.dim, (0, 0))

        for f in self.game.fruits:
            spr = self.sprite(f.kind, f.r)
            angle = math.sin(now * 2.2 + f.id * 1.7) * 24
            img = pygame.transform.rotozoom(spr, angle, 1.0)
            self.screen.blit(img, img.get_rect(center=(f.x * WIN_W, f.y * WIN_H)))

        self.overlay.fill((0, 0, 0, 0))
        self.draw_trail(now)
        self.draw_particles(dt)
        self.screen.blit(self.overlay, (0, 0))
        self.draw_floaters(dt)
        self.draw_hud(now)

        if now < self.flash_until:
            flash = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            flash.fill((255, 60, 60, int(110 * (self.flash_until - now) / 0.18)))
            self.screen.blit(flash, (0, 0))

        if self.cam.error:
            self.center_text(self.cam.error, WIN_H // 2, 28, RED)

        pygame.display.flip()

    def draw_trail(self, now):
        pts = [((p[0] * WIN_W, p[1] * WIN_H), t) for p, t in self.trail]
        for i in range(1, len(pts)):
            a = 1 - (now - pts[i][1]) / TRAIL_SECONDS
            color = (80, 240, 255, int(230 * a))
            w = max(2, int(3 + 12 * a))
            pygame.draw.line(self.overlay, color, pts[i - 1][0], pts[i][0], w)
            pygame.draw.circle(self.overlay, color, pts[i][0], w // 2)
        if self.game.finger:
            fx, fy = self.game.finger[0] * WIN_W, self.game.finger[1] * WIN_H
            pygame.draw.circle(self.overlay, (223, 252, 255, 255), (fx, fy), 9)

    def draw_particles(self, dt):
        self.particles = [p for p in self.particles if p["life"] > 0]
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 950 * dt
            p["life"] -= dt * 1.7
            if p["life"] > 0:
                col = (*p["color"], int(255 * min(1, p["life"])))
                pygame.draw.circle(self.overlay, col, (p["x"], p["y"]), p["size"] * p["life"])

    def draw_floaters(self, dt):
        self.floaters = [f for f in self.floaters if f["life"] > 0]
        for f in self.floaters:
            f["y"] -= 75 * dt
            f["life"] -= dt * 1.1
            if f["life"] > 0:
                img = self.fonts[44].render(f["text"], True, f["color"])
                img.set_alpha(int(255 * min(1, f["life"])))
                self.screen.blit(img, img.get_rect(center=(f["x"], f["y"])))

    # -------------------------------------------------------------------- hud

    def text(self, s, size, color, pos, align="topleft", alpha=255, shadow=True):
        img = self.fonts[size].render(s, True, color)
        rect = img.get_rect(**{align: pos})
        if shadow:
            sh = self.fonts[size].render(s, True, (0, 0, 0))
            sh.set_alpha(150)
            self.screen.blit(sh, rect.move(2, 3))
        if alpha < 255:
            img.set_alpha(alpha)
        self.screen.blit(img, rect)

    def center_text(self, s, y, size, color):
        self.text(s, size, color, (WIN_W // 2, y), align="center")

    def draw_hud(self, now):
        g = self.game
        st = self.st or g.state([])

        self.text(f"{self.clock.get_fps():.0f} fps", 18, (150, 160, 180), (10, WIN_H - 28), shadow=False)

        if g.phase == "playing":
            self.text(f"{g.score}", 56, WHITE, (36, 24))
            self.text("SCORE", 24, (150, 255, 190), (40, 96))
            self.text(g.player_name, 24, (205, 220, 235), (40, 128))
            frac = st["time_left"] / st["round_seconds"] if st["round_seconds"] else 0
            bar = pygame.Rect(int(WIN_W * 0.3), 36, int(WIN_W * 0.4), 16)
            pygame.draw.rect(self.screen, (255, 255, 255, 40), bar, border_radius=8)
            fill = bar.copy()
            fill.width = max(0, int(bar.width * frac))
            pygame.draw.rect(self.screen, RED if frac < 0.25 else GREEN, fill, border_radius=8)
            self.center_text(f"{math.ceil(st['time_left'])}s", 84, 34, WHITE)
            if g.combo > 1:
                self.center_text(f"COMBO x{min(g.combo, 5)}", 150, 44, YELLOW)
            if not g.finger:
                self.center_text("Show your hand to the camera", WIN_H - 60, 28, (255, 255, 255))

        elif g.phase in ("idle", "gameover"):
            if g.phase == "idle":
                self.center_text("AIR SLICE", int(WIN_H * 0.14), 96, GREEN)
                self.center_text("Fruit Ninja with your bare hand — no controller", int(WIN_H * 0.22), 28, (205, 220, 235))
            else:
                self.center_text("TIME'S UP!", int(WIN_H * 0.10), 72, (255, 154, 61))
                self.center_text(f"{g.player_name}  ·  {g.score}", int(WIN_H * 0.18), 56, WHITE)
                if g.qualifies:
                    self.center_text("TOP 5! You're on the board!", int(WIN_H * 0.245), 34, YELLOW)
            self.draw_start_target(now, st)
            self.draw_leaderboard(st)

        elif g.phase == "entername":
            self.center_text("GET READY", int(WIN_H * 0.16), 72, GREEN)
            self.draw_name_entry()
            self.draw_leaderboard(st)

        elif g.phase == "countdown":
            n = math.ceil(st["countdown"])
            self.center_text(str(n) if n > 0 else "GO!", WIN_H // 2, 190, GREEN)

    def draw_start_target(self, now, st):
        t = st["start"]
        x, y, r = t["x"] * WIN_W, t["y"] * WIN_H, t["r"] * WIN_H
        pulse = 1 + 0.04 * math.sin(now * 3.3)
        pygame.draw.circle(self.screen, GREEN, (x, y), r * pulse, 5)
        if st["start_progress"] > 0:
            rect = pygame.Rect(0, 0, 2 * (r * pulse + 14), 2 * (r * pulse + 14))
            rect.center = (x, y)
            pygame.draw.arc(self.screen, YELLOW, rect,
                            math.pi / 2 - st["start_progress"] * math.tau, math.pi / 2, 9)
        self.center_text("HERE", y - 14, 34, WHITE)
        msg = ("Hold your finger here to play again" if self.game.phase == "gameover"
               else "Hold your fingertip in the circle to start")
        self.text(msg, 28, (221, 255, 255), (x, y + r + 44), align="center")

    def draw_leaderboard(self, st):
        rows = st["leaderboard"]
        x, y, w = WIN_W - 330, int(WIN_H * 0.32), 290
        panel = pygame.Surface((w, 78 + max(1, len(rows)) * 44), pygame.SRCALPHA)
        pygame.draw.rect(panel, (8, 12, 24, 185), panel.get_rect(), border_radius=14)
        self.screen.blit(panel, (x, y))
        self.text("TOP 5", 28, GREEN, (x + 22, y + 14))
        if not rows:
            self.text("Be the first!", 24, (136, 150, 170), (x + 22, y + 62))
        for i, r in enumerate(rows):
            color = YELLOW if i == 0 else (230, 236, 255)
            self.text(f"{i + 1}. {r['name']}", 24, color, (x + 22, y + 60 + i * 44))
            self.text(f"{r['score']}", 24, color, (x + w - 22, y + 60 + i * 44), align="topright")

    def draw_name_entry(self):
        w, h = 560, 200
        x, y = (WIN_W - w) // 2, int(WIN_H * 0.38)
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (12, 16, 30, 225), panel.get_rect(), border_radius=16)
        pygame.draw.rect(panel, GREEN, panel.get_rect(), 3, border_radius=16)
        self.screen.blit(panel, (x, y))
        self.center_text("Type your name, then Enter to start", y + 40, 28, GREEN)
        caret = "_" if int(time.monotonic() * 2) % 2 else " "
        self.center_text((self.name_text or "") + caret, y + 110, 56, WHITE)

    # -------------------------------------------------------------------- run

    def run(self):
        print("Air Slice desktop — ESC to quit, F11 for fullscreen")
        self.cam.start()
        running = True
        while running:
            dt = min(self.clock.tick(60) / 1000, 0.05)
            running = self.handle_events()
            self.tick()
            self.draw(dt)
        self.cam.stop()
        pygame.quit()


def main():
    App().run()


if __name__ == "__main__":
    main()
