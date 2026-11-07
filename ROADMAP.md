# Roadmap

Planned independent development work, in order. Sizes are honest
estimates for one developer; the total is roughly **200 hours**.

| Phase | Work | Est. |
|---|---|---|
| 1 | **Level detection** — find the memory address that says which level is loaded (differential snapshots across level transitions), then auto-load the matching step guide and drop the manual assumption | ~12 hrs |
| 2 | **Lud's Gate, verified** — download and frame-index the walkthrough video, rewrite the draft steps against the footage, verify the key routes by driving them in-game, ship it in both trackers | ~15 hrs |
| 3 | **Rest of Tomb Raider III** — the same treatment for the remaining levels: India (Jungle, Temple Ruins, Ganges, Caves of Kaliya), London (Thames Wharf, City), Nevada (Nevada Desert, High Security Compound, Area 51), South Pacific (Coastal Village, Crash Site, Madubu Gorge, Temple of Puna), Antarctica (Antarctica, RX-Tech Mines, Lost City of Tinnos, Meteorite Cavern) | ~90 hrs |
| 4 | **Tomb Raider I + II** — calibrate the memory maps for the two earlier games (same differential method), write and verify guides for their signature levels | ~40 hrs |
| 5 | **In-emulator panel (PCSX-Redux)** — a third route where hints render as a real panel inside the emulator via its Lua/ImGui scripting, instead of a one-line message | ~25 hrs |
| 6 | **Data-driven game definitions + tests** — move addresses, level lists and step text out of the tracker code into per-game data files; unit tests for the step engine (room-change, drop detection, pin override) so new games plug in without code changes | ~20 hrs |

## Principles that don't change

- Read the game only through the emulator's official interfaces
  (debugger port, network control interface). No emulator forks, no
  memory patching, no cheats applied to the player's game.
- Every guide is verified against video footage and, for key routes,
  by driving them in the game itself — never copied blind from a
  text walkthrough.
- The human can always override the current step with one number in
  a text file.
