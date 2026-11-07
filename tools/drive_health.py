#!/usr/bin/env python3
"""Health hunt v2 — same proven GDB pattern as drive_test.py (pose-only,
no explicit halts). Submerge Lara, sample air until low, snapshot full
RAM with gdb_snap.py (fresh connection, frozen), let drowning damage
accrue ~14 s at zero air, snapshot again, rescue with F1.
Diffing vm_H1 (health full) vs vm_H2 (health draining) isolates health.
"""
import os, socket, struct, subprocess, time

LARA = 0x801D6E10
AIR = 0x8009952E
ENV = dict(os.environ, DISPLAY=':99')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

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
    air = struct.unpack('<h', rd(s, AIR, 2))[0]
    send(s, b'c')
    return x, y, z, yrot, air
def angdiff(target, cur):
    d = (target - cur) % 65536
    return d - 65536 if d > 32768 else d
def connect():
    s = socket.create_connection(('127.0.0.1', 2345), timeout=5)
    s.settimeout(5)
    try: s.recv(1024)
    except socket.timeout: pass
    return s
def snap(path):
    r = subprocess.run(['.venv/bin/python', 'src/gdb_snap.py', path],
                       cwd=ROOT, env=ENV, capture_output=True, text=True,
                       timeout=60)
    print(r.stdout.strip() or r.stderr.strip(), flush=True)

def main():
    s = connect()
    key('mousemove', '--sync', '410', '350', 'click', '1')
    time.sleep(0.4)
    for i in range(14):
        x, y, z, yrot, air = pose(s)
        err = angdiff(16384, yrot)
        print(f'  turn{i}: yrot={yrot} err={err}', flush=True)
        if abs(err) < 1600: break
        hold('d' if err > 0 else 'a', min(0.55, max(0.18, abs(err) / 26000.0)))
    hold('Up', 2.2)
    hold('j', 3.5)
    x, y, z, yrot, air = pose(s)
    print(f'submerged at ({x},{y},{z}) air={air}', flush=True)
    if y < 1400:
        print('NOT SUBMERGED, abort', flush=True)
        key('key', 'F1'); return
    # passive drain until air < 260
    t0 = time.time()
    while time.time() - t0 < 120:
        x, y, z, yrot, air = pose(s)
        print(f'  drain air={air}', flush=True)
        if air < 260: break
        time.sleep(1.0)
    s.close()
    snap('states/vm_H1.bin')           # frozen ~12 s, air does not drain
    s = connect()
    # drowning phase: wait until air == 0, then ~14 s more
    zero_t = None
    t0 = time.time()
    while time.time() - t0 < 90:
        x, y, z, yrot, air = pose(s)
        print(f'  drown air={air}', flush=True)
        if air <= 0:
            if zero_t is None: zero_t = time.time()
            if time.time() - zero_t > 14: break
        time.sleep(1.0)
    s.close()
    snap('states/vm_H2.bin')
    key('key', 'F1')
    time.sleep(2.5)
    s = connect()
    x, y, z, yrot, air = pose(s)
    print(f'rescued: ({x},{y},{z}) air={air}', flush=True)

if __name__ == '__main__':
    main()
