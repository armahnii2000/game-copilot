#!/usr/bin/env python3
"""Closed-loop driver + passive-submersion air test.

Steers Lara by reading her struct over GDB and pulsing keys via xdotool:
  1. turn_to(+x) from wherever she faces
  2. run forward into the temple pool, swim-stroke to submerge
  3. NO input for 40 s while sampling the two air candidates
     (0x8009952E, 0x800A3F44) — true air must keep draining while she
     hangs motionless; a stroke/effort gauge will freeze
  4. reload the current save-state slot (host F1) to rescue her

Prints a timeline. Run with DISPLAY=:99 set.
"""
import os, socket, struct, subprocess, sys, time

LARA = 0x801D6E10
CANDS = (0x8009952E, 0x800A3F44)
ENV = dict(os.environ, DISPLAY=':99')

def key(*args):
    subprocess.run(['xdotool'] + list(args), env=ENV, check=False)

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
def halt(s):
    s.sendall(b'\x03'); readp(s)
def pose(s):
    buf = rd(s, LARA, 0x30)
    x, y, z = struct.unpack_from('<iii', buf, 0)
    yrot = struct.unpack_from('<h', buf, 0x0E)[0]
    room = struct.unpack_from('<h', buf, 0x12)[0]
    a = struct.unpack('<h', rd(s, CANDS[0], 2))[0]
    b = struct.unpack('<h', rd(s, CANDS[1], 2))[0]
    send(s, b'c')
    return x, y, z, yrot, room, a, b

def angdiff(target, cur):
    d = (target - cur) % 65536
    return d - 65536 if d > 32768 else d

def main():
    s = socket.create_connection(('127.0.0.1', 2345), timeout=5)
    s.settimeout(5)
    try: s.recv(1024)
    except socket.timeout: pass
    key('mousemove', '--sync', '410', '350', 'click', '1')
    time.sleep(0.4)
    x, y, z, yrot, room, a, b = pose(s)
    print(f'start: ({x},{y},{z}) yrot={yrot} room={room} cand=({a},{b})', flush=True)
    # 1) closed-loop turn to +x (16384)
    for i in range(14):
        x, y, z, yrot, room, a, b = pose(s)
        err = angdiff(16384, yrot)
        print(f'  turn{i}: yrot={yrot} err={err}', flush=True)
        if abs(err) < 1600:
            break
        hold('d' if err > 0 else 'a', min(0.55, max(0.18, abs(err) / 26000.0)))
        halt(s)
    # 2) run in + stroke to submerge
    hold('Up', 2.2)
    halt(s)
    x, y, z, yrot, room, a, b = pose(s)
    print(f'after run: ({x},{y},{z}) yrot={yrot}', flush=True)
    hold('j', 3.5)
    halt(s)
    x, y, z, yrot, room, a, b = pose(s)
    print(f'after stroke: ({x},{y},{z}) yrot={yrot} cand=({a},{b})', flush=True)
    if y < 1400:
        print('NOT SUBMERGED - aborting test', flush=True)
    else:
        # 3) passive sampling, no input
        t0 = time.time()
        while time.time() - t0 < 40:
            halt(s)
            x, y, z, yrot, room, a, b = pose(s)
            print(f'  passive {time.time()-t0:5.1f}s y={y} cand952E={a} cand3F44={b}', flush=True)
            time.sleep(1.2)
    # 4) rescue: reload current slot
    key('key', 'F1')
    time.sleep(2.5)
    halt(s)
    x, y, z, yrot, room, a, b = pose(s)
    print(f'rescued: ({x},{y},{z}) room={room} cand=({a},{b})', flush=True)

if __name__ == '__main__':
    main()
