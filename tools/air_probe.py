#!/usr/bin/env python3
"""Probe the two air candidates live: read 0x8009952E and 0x800A3F44
(s16) plus the position struct, ~2 Hz, for N seconds."""
import socket, struct, sys, time

CANDS = (0x8009952E, 0x800A3F44)
LARA = 0x801D6E10

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

def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    s = socket.create_connection(('127.0.0.1', 2345), timeout=5)
    s.settimeout(5)
    try: s.recv(1024)
    except socket.timeout: pass
    t0 = time.time(); last = 0.0
    while time.time() - t0 < secs:
        st = struct.unpack_from('<hhhh', rd(s, LARA + 0x0E - 0x0E, 0x30)[0x0E:0x10] + b'\0\0' + rd(s, LARA, 0x30)[0x12:0x14] + b'\0\0', 0) if False else None
        buf = rd(s, LARA, 0x30)
        room = struct.unpack_from('<h', buf, 0x12)[0]
        y = struct.unpack_from('<i', buf, 4)[0]
        vals = []
        for a in CANDS:
            b2 = rd(s, a, 2)
            vals.append(struct.unpack('<h', b2)[0])
        send(s, b'c')
        now = time.time() - t0
        print(f'{now:6.2f}s room={room:3d} y={y:6d} cand952E={vals[0]:6d} cand3F44={vals[1]:6d}', flush=True)
        dt = time.time() - t0 - now
        try:
            s.sendall(b'\x03'); readp(s)
        except Exception:
            break
        time.sleep(max(0.05, 0.45 - dt))
    try:
        send(s, b'c')
    except Exception:
        pass

if __name__ == '__main__':
    main()
