#!/usr/bin/env python3
"""TR3 live tracker — DuckStation GDB -> walkthrough step -> text overlay.

Runs on the SAME machine as DuckStation. Connects to the
GDB server on localhost:2345, samples Lara's item struct, maps her
position/room to the current walkthrough step for Aldwych, and writes
the overlay text file the Swift overlay bar displays.

Memory (TR3 USA v1.2, SLUS-00691 — verified 2026-11-04 by differential
calibration + live streaming, identical on Mac and VM copies):
  Lara item struct @ 0x801D6E10:
    +0x00 x (s32)  +0x04 y (s32, down-positive)  +0x08 z (s32)
    +0x0E y_rot (s16; 65536 = 360 deg)           +0x12 room (s16)

Step engine (v1, Aldwych): an ordered step list. Advances when Lara
enters a room she hasn't visited recently, or drops fast (dive/slide).
A pin file (~/duckstation-help-step.txt, one integer) overrides the
step while present — the human-in-the-loop correction channel.

Outputs:
  ~/duckstation-help-overlay.txt   line1=heading, rest=body (overlay)
  ~/duckstation-help-status.json   last sample, for remote monitoring

Usage: tracker.py [step_index_to_start_at]
"""
import json, os, socket, struct, sys, time

HOME = os.path.expanduser('~')
OVERLAY_FILE = os.path.join(HOME, 'duckstation-help-overlay.txt')
STATUS_FILE = os.path.join(HOME, 'duckstation-help-status.json')
PIN_FILE = os.path.join(HOME, 'duckstation-help-step.txt')

LARA = 0x801D6E10
AIR_ADDR = 0x8009952E     # s16, max 1800 (found 2026-11-04, passive-drain test)
AIR_MAX = 1800
HEALTH_ADDR = 0x801D6DF2  # s16, max 1000 (found 2026-11-04, drowning diff)
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

def checksum(payload: bytes) -> bytes:
    return b'%02x' % (sum(payload) & 0xFF)

def send_packet(sock, payload: bytes):
    sock.sendall(b'$' + payload + b'#' + checksum(payload))

def read_packet(sock):
    buf = b''
    while True:
        ch = sock.recv(1)
        if not ch:
            raise ConnectionError('socket closed')
        if ch == b'$':
            break
        if ch == b'+':
            continue
        buf += ch
    payload = b''
    while True:
        ch = sock.recv(1)
        if ch == b'#':
            break
        payload += ch
    sock.recv(2)
    sock.sendall(b'+')
    return payload

def connect():
    while True:
        try:
            s = socket.create_connection(('127.0.0.1', 2345), timeout=5)
            s.settimeout(5)
            try:
                s.recv(1024)
            except socket.timeout:
                pass
            return s
        except OSError:
            time.sleep(5)

def sample(s):
    send_packet(s, b'm%x,%x' % (LARA, 0x30))
    buf = bytes.fromhex(read_packet(s).decode())
    send_packet(s, b'm%x,%x' % (AIR_ADDR, 2))
    air = struct.unpack('<h', bytes.fromhex(read_packet(s).decode()))[0]
    send_packet(s, b'm%x,%x' % (HEALTH_ADDR, 2))
    health = struct.unpack('<h', bytes.fromhex(read_packet(s).decode()))[0]
    send_packet(s, b'c')
    x, y, z = struct.unpack_from('<iii', buf, 0)
    yrot = struct.unpack_from('<h', buf, 0x0E)[0]
    room = struct.unpack_from('<h', buf, 0x12)[0]
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
    write_overlay(step)
    last_shown = (step, AIR_MAX // 90, HEALTH_MAX // 50)
    s = connect()
    visited = []          # recent rooms, most recent last
    last_advance = 0.0
    prev_y = None
    prev_t = None
    last_status = 0.0
    while True:
        try:
            x, y, z, yrot, room, air, health = sample(s)
        except Exception:
            try:
                s.close()
            except Exception:
                pass
            s = connect()
            continue
        now = time.time()
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
            if visited:  # not the very first sample
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
        # overlay refresh when step or vitals bucket changes
        shown = (step, max(0, air) // 90, max(0, health) // 50)
        if shown != last_shown:
            last_shown = shown
            write_overlay(step, air, health)
        # status heartbeat for remote monitoring
        if now - last_status > 2:
            last_status = now
            try:
                with open(STATUS_FILE, 'w') as f:
                    json.dump({'t': now, 'room': room, 'x': x, 'y': y, 'z': z,
                               'yrot': yrot, 'air': air, 'health': health,
                               'step': step,
                               'step_name': STEPS[step][0]}, f)
            except OSError:
                pass
        # halt again for the next sample
        try:
            s.sendall(b'\x03')
            read_packet(s)
        except Exception:
            try:
                s.close()
            except Exception:
                pass
            s = connect()
        time.sleep(0.25)

if __name__ == '__main__':
    main()
