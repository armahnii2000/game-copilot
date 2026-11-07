#!/usr/bin/env python3
"""Tunnel survey: from the temple pool, swim the tunnel and probe each
branch direction with swim strokes, logging pose after each probe, to
find the through-route to the flooded ledges (video ~28:30 climb-out).
Rescues with F1 at the end. Air budget: entry + probes kept < ~45 s.
"""
import os, socket, struct, subprocess, time

LARA = 0x801D6E10
AIR = 0x8009952E
ENV = dict(os.environ, DISPLAY=':99')

def key(*args): subprocess.run(['xdotool'] + list(args), env=ENV, check=False)
def hold(k, secs):
    key('keydown', k); time.sleep(secs); key('keyup', k)
def cks(p): return b'%02x' % (sum(p) & 0xFF)
def send(s, p): s.sendall(b'$' + p + b'#' + cks(p))
def readp(s):
    while True:
        ch = s.recv(1)
        if ch == b'$': break
        if not ch: raise ConnectionError('closed')
    out = b''
    while True:
        ch = s.recv(1)
        if ch == b'#': break
        out += ch
    s.recv(2); s.sendall(b'+')
    return out
def rd(s, addr, n):
    send(s, b'm%x,%x' % (addr, n))
    return bytes.fromhex(readp(s).decode())
def pose(s):
    buf = rd(s, LARA, 0x30)
    x, y, z = struct.unpack_from('<iii', buf, 0)
    yrot = struct.unpack_from('<h', buf, 0x0E)[0]
    room = struct.unpack_from('<h', buf, 0x12)[0]
    air = struct.unpack('<h', rd(s, AIR, 2))[0]
    send(s, b'c')
    return x, y, z, yrot, room, air
def angdiff(target, cur):
    d = (target - cur) % 65536
    return d - 65536 if d > 32768 else d
def turn_to(s, target, label):
    for i in range(16):
        x, y, z, yrot, room, air = pose(s)
        err = angdiff(target, yrot)
        if abs(err) < 1700:
            print(f'  {label}: facing ok yrot={yrot}', flush=True)
            return
        hold('d' if err > 0 else 'a', min(0.5, max(0.15, abs(err) / 24000.0)))
    x, y, z, yrot, room, air = pose(s)
    print(f'  {label}: turn gave up yrot={yrot}', flush=True)
def stroke(s, secs, label):
    x0, y0, z0, yrot, room, air = pose(s)
    hold('j', secs)
    x, y, z, yrot, room, air = pose(s)
    moved = ((x - x0) ** 2 + (z - z0) ** 2) ** 0.5
    print(f'  {label}: ({x0},{y0},{z0}) -> ({x},{y},{z}) moved={moved:.0f} room={room} air={air}', flush=True)
    return moved, (x, y, z, room, air)

def main():
    s = socket.create_connection(('127.0.0.1', 2345), timeout=5)
    s.settimeout(5)
    try: s.recv(1024)
    except socket.timeout: pass
    key('mousemove', '--sync', '410', '350', 'click', '1')
    time.sleep(0.4)
    turn_to(s, 16384, 'face +x')
    hold('Up', 2.2)
    stroke(s, 3.5, "entry stroke +x"); turn_to(s, 0, "face +z leg"); stroke(s, 3.0, "leg +z #1"); stroke(s, 3.0, "leg +z #2")
    # probe branches from mid-tunnel
    for target, name in ((16384, "+x2"), (49152, "-x2")):
        x, y, z, yrot, room, air = pose(s)
        if air < 420:
            print('air low, skipping probes', flush=True)
            break
        turn_to(s, target, f'face {name}')
        moved, st = stroke(s, 3.0, f'probe {name}')
        if moved > 800:
            print(f'  >> branch {name} moves! following it', flush=True)
            for k in range(3):
                moved, st = stroke(s, 3.0, f'follow {name} #{k + 1}')
                if st[1] < 1400 or moved < 300:
                    break
            break
    x, y, z, yrot, room, air = pose(s)
    print(f'final: ({x},{y},{z}) room={room} air={air}', flush=True)
    key('key', 'F1')
    time.sleep(2.5)
    x, y, z, yrot, room, air = pose(s)
    print(f'rescued: ({x},{y},{z}) air={air}', flush=True)

if __name__ == '__main__':
    main()
