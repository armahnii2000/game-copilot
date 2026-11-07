#!/usr/bin/env python3
"""TR3 live tracker — RetroArch NCI (UDP) -> walkthrough step -> hints.

Runs on the SAME machine as RetroArch. Talks to
RetroArch's Network Control Interface on localhost:55355, samples
Lara's item struct via READ_CORE_RAM (SwanStation exposes no system
memory map; READ_CORE_MEMORY is tried as a fallback), maps her
position/room to the current Aldwych walkthrough step, shows the
hint inside the game window via SHOW_MSG, and also writes the
shared overlay/status files used by the floating panel.

Memory (TR3 USA v1.2, SLUS-00691 — verified 2026-11-04 on DuckStation
by differential calibration, and the read pipe verified live against
SwanStation/RetroArch 1.22.2 on this Mac the same day):
  Lara item struct @ RAM offset 0x1D6E10:
    +0x00 x (s32)  +0x04 y (s32, down-positive)  +0x08 z (s32)
    +0x0E y_rot (s16; 65536 = 360 deg)           +0x12 room (s16)
  Air s16 @ 0x9952E (max 1800); health s16 @ 0x1D6DF2 (max 1000).
  Mirror of pos (12 bytes) @ 0x99898 — used as an in-game validator:
  it only mirrors Lara while a level is actually running, which
  filters out the title-screen pointer table at the struct address.

Step engine: identical rules to the DuckStation tracker (v1,
Aldwych): advance on entering a room not among the last 4 visited
(debounced 4 s) or on a fast y-drop (>6000 u/s). Pin file
~/duckstation-help-step.txt (one integer) overrides the step.

Outputs:
  ~/duckstation-help-overlay.txt   line1=heading, rest=body (panel)
  ~/duckstation-help-status.json   last sample, for remote monitoring

Usage: tracker_ra.py [step_index_to_start_at]
Waits silently while RetroArch is not running or TR3 is not loaded.
"""
import json, os, socket, struct, sys, time

HOME = os.path.expanduser('~')
OVERLAY_FILE = os.path.join(HOME, 'duckstation-help-overlay.txt')
STATUS_FILE = os.path.join(HOME, 'duckstation-help-status.json')
PIN_FILE = os.path.join(HOME, 'duckstation-help-step.txt')
LOG_FILE = os.path.join(HOME, 'retroarch-copilot-tracker.log')

NCI = ('127.0.0.1', 55355)
LARA = 0x1D6E10
MIRROR = 0x99898
AIR_ADDR = 0x9952E
AIR_MAX = 1800
HEALTH_ADDR = 0x1D6DF2
HEALTH_MAX = 1000

STEPS = [
    ("Masonic Temple",
     "Get the ORNATE STAR behind the purple curtain if you haven't yet.\n"
     "Exit: climb/drop by the gold shaft, then dive into the water."),
    ("Swim + flooded ledges",
     "Swim the tunnel: long straight, then it zigzags -\n"
     "bend, short hop, bend again the same way. About half\n"
     "an air bar; climb out at the far end, cross the flooded\n"
     "room on the concrete ledges, then ladder up."),
    ("Turnstile + concourse",
     "Use the TICKET at the turnstile.\n"
     "Cross the big checkered concourse."),
    ("Vent rooms + climb",
     "Red fan room, a short swim, then monkey-bar ceilings.\n"
     "Climb up past the slope machinery."),
    ("The Mallet door",
     "At the bottom of the escalator, open the door with the\n"
     "MASONIC MALLET. Then drop down the gold shaft."),
    ("Trains + platform",
     "Through the train car and caged walkway to the platform.\n"
     "Watch for thugs. The Aldwych roundel is here."),
    ("Red train car",
     "Red train car: drop in through the trapdoor and press\n"
     "the button to move the car."),
    ("Tiled hallway",
     "Long yellow tiled hallway.\n"
     "Do NOT shoot the first thug - he opens a door for you."),
    ("Swims + red-carpet stairs",
     "Two swims and white rooms, then climb the\n"
     "red-carpet staircase."),
    ("Red shaft + tunnels",
     "Big slide down the red shaft.\n"
     "Then climbs, pools and rocky tunnels."),
    ("Final slide",
     "Steep slide - ride it all the way down.\n"
     "The level ends at the bottom."),
    ("The Damned - cutscene",
     "Cutscene: the Damned around the campfire.\n"
     "After the stats screen: next level is Lud's Gate."),
]

# One-line versions for the in-window SHOW_MSG display.
STEPS_SHORT = [
    "Masonic Temple - Ornate Star behind the purple curtain, then dive",
    "Swim the zigzag tunnel (about half an air bar), climb out, cross the ledges",
    "Use the TICKET at the turnstile, cross the checkered concourse",
    "Red fan room, short swim, monkey-bar ceilings, climb up",
    "Escalator bottom: open the door with the MASONIC MALLET",
    "Through the train car to the platform - watch for thugs",
    "Red train car: trapdoor in, press the button to move the car",
    "Tiled hallway - do NOT shoot the first thug, he opens a door",
    "Two swims, white rooms, climb the red-carpet staircase",
    "Big slide down the red shaft, then climbs, pools, tunnels",
    "Final slide - ride it all the way down",
    "Cutscene: the Damned campfire. Next level: Lud's Gate",
]


def log(msg):
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(time.strftime('%H:%M:%S ') + msg + '\n')
    except OSError:
        pass


class NCIClient:
    """One UDP socket, request/response matched by verb echo."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1.5)
        self.verb = 'READ_CORE_RAM'  # SwanStation: no system map

    def cmd(self, text, expect_reply=True):
        self.sock.sendto(text.encode(), NCI)
        if not expect_reply:
            return None
        data, _ = self.sock.recvfrom(65535)  # raises socket.timeout
        return data.decode(errors='replace').strip()

    def read(self, addr, n):
        for verb in (self.verb, 'READ_CORE_MEMORY' if self.verb == 'READ_CORE_RAM' else 'READ_CORE_RAM'):
            try:
                r = self.cmd('%s %X %d' % (verb, addr, n))
            except (socket.timeout, OSError):
                raise
            parts = r.split()
            if len(parts) >= 2 + n and parts[0] == verb:
                self.verb = verb
                return bytes(int(x, 16) for x in parts[2:2 + n])
            # error reply (e.g. "-1 no memory map defined") -> try other verb
        return None

    def show_msg(self, text):
        try:
            self.sock.sendto(('SHOW_MSG ' + text).encode(), NCI)
        except OSError:
            pass

    def status(self):
        return self.cmd('GET_STATUS')


def sample(cli):
    """Return (x, y, z, yrot, room, air, health) or None when not in a
    level (title/menus) or RetroArch is unreachable."""
    buf = cli.read(LARA, 0x1C)
    if not buf:
        return None
    mir = cli.read(MIRROR, 12)
    air_b = cli.read(AIR_ADDR, 2)
    hp_b = cli.read(HEALTH_ADDR, 2)
    if mir is None or air_b is None or hp_b is None:
        return None
    x, y, z = struct.unpack_from('<iii', buf, 0)
    yrot = struct.unpack_from('<h', buf, 0x0E)[0]
    room = struct.unpack_from('<h', buf, 0x12)[0]
    air = struct.unpack('<h', air_b)[0]
    health = struct.unpack('<h', hp_b)[0]
    # in-game validation: mirror must equal struct pos (only true while
    # a level runs) and vitals must be in range.
    if mir != buf[0:12]:
        return None
    if not (0 <= air <= AIR_MAX and 0 <= health <= HEALTH_MAX):
        return None
    if not (0 <= room <= 200):
        return None
    if max(abs(x), abs(y), abs(z)) > 1000000:
        return None
    return x, y, z, yrot, room, air, health


def write_overlay(step, air=AIR_MAX, health=HEALTH_MAX):
    name, body = STEPS[step]
    extra = ''
    if air < AIR_MAX:
        pct = max(0, air) * 100 // AIR_MAX
        extra += f'\nAIR {pct}%' + (' - SURFACE NOW!' if pct < 35 else '')
    if health < HEALTH_MAX:
        extra += f'\nHealth {max(0, health) * 100 // HEALTH_MAX}%'
    txt = f'{name}\n{body}{extra}\n'
    tmp = OVERLAY_FILE + '.tmp'
    with open(tmp, 'w') as f:
        f.write(txt)
    os.replace(tmp, OVERLAY_FILE)


def main():
    step = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    step = max(0, min(step, len(STEPS) - 1))
    log('tracker_ra started, step=%d' % step)
    cli = NCIClient()
    visited = []
    last_advance = 0.0
    prev_y = None
    prev_t = None
    last_status = 0.0
    last_shown = None
    in_game = False
    air_low_warned = False
    while True:
        try:
            s = sample(cli)
        except (socket.timeout, OSError):
            s = None
            time.sleep(2)  # RetroArch absent/quiet: gentle poll
        now = time.time()
        if s is None:
            if in_game:
                log('left gameplay (menu/title or RetroArch closed)')
                in_game = False
            prev_y = None
            time.sleep(0.25)
            continue
        x, y, z, yrot, room, air, health = s
        if not in_game:
            log('gameplay detected: room=%d pos=(%d,%d,%d) health=%d'
                % (room, x, y, z, health))
            in_game = True
            cli.show_msg('Copilot: ' + STEPS_SHORT[step])
            last_shown = step
        # step pin override
        try:
            with open(PIN_FILE) as f:
                pin = int(f.read().strip())
            if 0 <= pin < len(STEPS) and pin != step:
                step = pin
                last_advance = now
        except (OSError, ValueError):
            pass
        # advance: new room (not among last 4 visited), debounced
        if room not in visited[-4:] and now - last_advance > 4:
            if visited:
                step = min(step + 1, len(STEPS) - 1)
                last_advance = now
            visited.append(room)
        elif room in visited and (not visited or visited[-1] != room):
            visited.append(room)
        visited = visited[-12:]
        # advance: fast drop (dive / slide / big fall)
        if prev_y is not None and prev_t is not None:
            dt = now - prev_t
            if dt > 0 and (y - prev_y) / dt > 6000 and now - last_advance > 4:
                step = min(step + 1, len(STEPS) - 1)
                last_advance = now
        prev_y, prev_t = y, now
        # in-window message on step change
        if step != last_shown:
            last_shown = step
            cli.show_msg('Copilot: ' + STEPS_SHORT[step])
        # air warning edge
        if air < AIR_MAX * 0.35 and not air_low_warned:
            air_low_warned = True
            cli.show_msg('Copilot: AIR LOW - surface now!')
        elif air >= AIR_MAX * 0.5:
            air_low_warned = False
        # overlay/status refresh
        shown = (step, max(0, air) // 90, max(0, health) // 50)
        if shown != getattr(main, '_shown', None):
            main._shown = shown
            try:
                write_overlay(step, air, health)
            except OSError:
                pass
        if now - last_status > 2:
            last_status = now
            try:
                with open(STATUS_FILE, 'w') as f:
                    json.dump({'t': now, 'source': 'retroarch',
                               'room': room, 'x': x, 'y': y, 'z': z,
                               'yrot': yrot, 'air': air, 'health': health,
                               'step': step,
                               'step_name': STEPS[step][0]}, f)
            except OSError:
                pass
        time.sleep(0.25)


if __name__ == '__main__':
    main()
