# Air Slice 🍉✋

Fruit Ninja you play with your bare hand in the air — no controller, no hardware.
Built for the **IEEE RAS freshers orientation stall**.

A webcam watches the player, **MediaPipe** tracks their index fingertip in real
time, and they slice fruit flying across the screen. Native **pygame** UI at
60 fps, so input lag is just camera + inference time.

- ⏱️ 20-second rounds — constant throughput at the stall
- 🔥 Combo multiplier (up to ×5) for chained slices
- 💣 Bombs cost 30 points and kill your combo
- 🏆 Leaderboard in SQLite (`data/leaderboard.db`) — every play is recorded,
  top 5 shown on screen; a legacy `leaderboard.json` is migrated automatically
- 🔊 Real arcade sound effects — knife slices, squishy splats, explosions
  ([Kenney](https://kenney.nl) CC0 packs, see `assets/sounds/CREDITS.md`);
  drop your own WAV/OGG/MP3s into `assets/sounds/` to replace any of them,
  and anything missing falls back to numpy-synthesized sounds
- ✋ Fully touchless between players: hold your fingertip in the circle to start

## Stall laptop setup (Windows — recommended)

**Requires Python 3.9–3.12** (MediaPipe does not support 3.13/3.14):

```
winget install Python.Python.3.12
```

Then, in the project folder:

```
setup.bat    # one time: creates .venv and installs dependencies
run.bat      # starts the game
```

Or manually:

```
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m app.desktop
```

**F11** = fullscreen (do this at the stall), **ESC** = quit.
Close anything else using the webcam first — only one app can hold it.

## Docker (Linux hosts only)

⚠️ **A container cannot reach the webcam or open a window on Windows/macOS** —
that's a Docker limitation, not a bug in this project. On the stall laptop,
use the native setup above. On a Linux machine, webcam + display passthrough
works:

```bash
xhost +local:            # allow the container to use your X display
docker compose up --build
```

(`docker-compose.yml` passes through `/dev/video0`, the X11 socket, and mounts
`./data` so the leaderboard survives restarts. Wayland users need XWayland.)

## How to play

1. Hold your index fingertip inside the green circle for 1 second.
2. Type your name and press Enter → countdown starts.
3. Slice fruit by swiping your fingertip through it — slow touches don't cut.
4. Chain slices within 0.6 s to build the combo multiplier (up to ×5).
5. Don't hit the 💣 — −30 points and your combo resets.
6. Time's up: your score is saved automatically; top-5 scores hit the board.

## Configuration (env vars)

| Variable        | Default | Meaning                        |
|-----------------|---------|--------------------------------|
| `ROUND_SECONDS` | `20`    | Round length in seconds        |
| `DATA_DIR`      | `data`  | Where the leaderboard database lives |

Gameplay tuning (slice speed threshold, spawn rates, bomb chance, points) is
all constants at the top of [`app/game.py`](app/game.py).

## Project layout

```
app/
  desktop.py       pygame UI: window, sprites, HUD, effects
  tracker.py       MediaPipe index-fingertip tracking (the "blade")
  game.py          Fruit physics, slice detection, combos, round state machine
  leaderboard.py   SQLite score store (full history, top-5 view)
  sounds.py        Sound effects: assets/sounds/ files + synthesized fallback
assets/sounds/     CC0 audio (Kenney packs) — swap in your own to customize
setup.bat / run.bat   One-command setup + launch for the stall laptop
```

Camera capture + hand tracking run on a background thread; the game loop
renders at 60 fps and never blocks on inference.

## Stall-day tips

- Face the webcam toward the player, not the crowd — single-hand fingertip
  tracking stays robust even with people clustered behind the player.
- Good lighting on the player's hand improves tracking a lot.
- Delete `data/leaderboard.db` to reset the leaderboard before the event
  (or `sqlite3 data/leaderboard.db "DELETE FROM scores"` to keep the file).
- 20-second rounds + the leaderboard = people queue up to beat their friends.
  That queue is the stall.
