# game-copilot

Real-time, in-game help for PlayStation 1 games. The copilot watches the
game *while you play it* — through the emulator's own official
interfaces — works out where you are, and shows you the right
walkthrough hint at the right moment. No pausing to check a guide, no
second screen.

Built and used so far with **Tomb Raider III (USA v1.2)** in two
emulators:

- **DuckStation** — the copilot talks to DuckStation's built-in GDB
  debugger server (localhost) and shows hints in a small floating
  panel (Swift/AppKit) that is only visible while DuckStation is the
  front app.
- **RetroArch** (SwanStation or Beetle PSX core) — the copilot talks
  to RetroArch's Network Control Interface (UDP) and shows hints
  *inside the game window itself*, using RetroArch's on-screen
  message display. Nothing floats over your other apps.

## How it works

1. **Memory map.** The copilot reads the player character's data
   straight from the emulated console's RAM: position, facing, room
   number, air (underwater) and health. The Tomb Raider III map was
   calibrated from scratch — frozen RAM snapshots taken while the
   character stood still, turned, ran, swam and drowned, then diffed
   field by field (see `docs/memory-map.md`). The addresses are the
   game's own, so they work in any accurate PS1 emulator.
2. **Step engine.** Each level has an ordered list of walkthrough
   steps. The engine advances when the player enters a room they
   haven't visited recently, or drops fast (a dive, a slide, a big
   fall). A one-integer pin file lets a human correct the step at any
   time — the human stays the decider.
3. **Video reference.** Routes are not copied from text guides alone.
   A full walkthrough video is downloaded, indexed frame by frame,
   and the step list is written against what the video shows; key
   routes (like the first Aldwych swim) are then driven and measured
   in the actual game to check them.

## Status

- TR3 memory map: complete for position / facing / room / air /
  health, verified live on both emulator routes. (The one missing
  value — which level is loaded — is Phase 1 of the roadmap.)
- Aldwych (London): full 12-step guide, live in both trackers.
- Lud's Gate: drafted from a text walkthrough, verification pending.
- Measured tracking latency on RetroArch: a full position sample
  takes ~24 ms; the tracker samples 4×/second, so its picture of the
  player is never more than about a third of a second old.
- Everything else (more levels, more games) is in `ROADMAP.md` and
  the issues.

## Running it

You need your own copy of Tomb Raider III (USA v1.2) — no game data
is included in this repo.

**RetroArch route**

1. In RetroArch: Settings → Network → Network Commands **on**
   (port 55355), with the SwanStation or Beetle PSX core and a PS1
   BIOS in the system folder. Load the game.
2. Run: `python3 tracker_retroarch.py`
3. Play. Hints appear in the game window; the tracker also writes
   `~/duckstation-help-overlay.txt` and `~/duckstation-help-status.json`
   (shared with the panel below).

**DuckStation route**

1. In DuckStation's `settings.ini` set `EnableGDBServer = true`
   under `[Debug]`. Load the game.
2. Run: `python3 tracker_duckstation.py`
3. Build and run the panel: `swiftc overlay.swift -o overlay && ./overlay`
   It shows only while DuckStation is frontmost.

Correct the current step at any time by writing its number into
`~/duckstation-help-step.txt`.

## Layout

- `tracker_duckstation.py` — DuckStation tracker (GDB protocol client,
  step engine, overlay/status writers)
- `tracker_retroarch.py` — RetroArch tracker (same engine over the
  Network Control Interface, in-window hints via `SHOW_MSG`)
- `nci.py` — small RetroArch NCI client + pose reader (CLI)
- `overlay.swift`, `overlay.py` — the floating hint panel (macOS)
- `whereami.py`, `state_read.py` — read position/vitals from a
  DuckStation save-state file, no emulator needed
- `tools/` — the calibration and research tooling: GDB snapshot/diff
  drivers (`gdb_*`, `drive_*`, `air_probe`, `live_pos`), RetroArch
  samplers (`ra_pose_sampler`, `probe_beetle_ram`), and the
  walkthrough-video indexer/matcher (`vidindex`, `vidmatch2`)
- `docs/memory-map.md` — the calibrated TR3 map and how it was found
- `docs/aldwych-segments.md` — the Aldwych video reference, segmented
- `docs/luds-gate-steps-draft.md` — Lud's Gate step draft

Solo project by George Armah. Python 3 standard library only; the
panel is Swift/AppKit. No game ROMs, BIOS files, save states or
videos are included in this repository.

## License

MIT — see `LICENSE`.
