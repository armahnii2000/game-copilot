# TR3 memory map — how it was found, and what is known

Game: **Tomb Raider III — Adventures of Lara Croft (USA) (v1.2)**,
SLUS-00691. All addresses are PS1 RAM addresses; every accurate PS1
emulator maps the same 2 MB of RAM, so the map transfers between
emulators unchanged (verified: DuckStation ↔ RetroArch/SwanStation).

## The map

| What | Address | Type | Notes |
|---|---|---|---|
| Lara item struct | `0x801D6E10` | struct | +0x00 x, +0x04 y, +0x08 z (s32; 1024 = 1 sector; y is down-positive) |
| Facing (y rotation) | struct +0x0E | s16 | 65536 = 360° |
| Room number | struct +0x12 | s16 | e.g. the Aldwych Masonic temple is room 62 |
| Health | `0x801D6DF2` (struct − 0x1E) | s16 | max 1000; mirrored at `0x80096B24` |
| Air | `0x8009952E` | s16 | max 1800 ≈ 60 game-seconds underwater |
| Position mirror | `0x80099898` | 12 bytes | working copy of pos+rotation (no room); only mirrors Lara while a level is running — the trackers use it as an in-game validator |

## Method (differential calibration)

1. Freeze full 2 MB RAM snapshots through DuckStation's GDB server
   (`tools/gdb_snap.py`) in controlled states: standing still,
   turned 90°, after a short run, submerged and motionless, and
   while drowning.
2. Diff the snapshots field by field. Real candidates move exactly
   when the matching in-game quantity moves, and only then.
3. Cross-check on a second, independent save file and live-stream
   the winners at 4 Hz while playing.

Two traps this method caught:

- **Cheat-site GameShark addresses are not live values** for this
  build — they are constants from the game executable, not the
  runtime fields. Anything sourced from a cheat list must be
  re-proven by experiment.
- A family of addresses that rose ~+824 per action burst turned out
  to be a **time counter** (it also rises ~+33/second at idle).
  Single-experiment "it changed when I moved" evidence is not
  enough; idle controls matter.

Air was pinned by a closed-loop experiment: holding Lara motionless
underwater, the true air value drains perfectly linearly (−35 per
~1.3 s sample) while a rival candidate (a stroke/effort gauge)
zeroes at rest. Health was pinned by a drowning diff: only one
sensible candidate fell from 1000 as she drowned, and it read back
correctly (885) on an unrelated real-world save.

## Reading it from RetroArch

RetroArch's Network Control Interface (UDP 55355) answers in ~4–5 ms
per command on the same machine (measured; replies quantize to the
frame clock). A full pose sample — struct, mirror, air, health —
takes ~24 ms median.

Core quirk: SwanStation defines no *system* memory map, so
`READ_CORE_MEMORY` replies `-1 no memory map defined`; use
`READ_CORE_RAM` (the RetroAchievements map) with the KSEG0 prefix
stripped (address − `0x80000000`). Beetle PSX answers on the other
path. `nci.py` tries both.

## Still unknown

- **Which level is loaded.** No address has been isolated yet; it
  needs a snapshot pair across a real level transition (ROADMAP
  Phase 1). Until then the trackers assume the level they were
  started for, with the pin file as the correction channel.
