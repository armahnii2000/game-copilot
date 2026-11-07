#!/usr/bin/env python3
"""Frozen RAM snapshot via DuckStation GDB: connect (target halts), read all
2 MB WITHOUT continuing, then continue + detach. The game is frozen for the
whole read, so the snapshot is a true instant — no drift during the dump.

Usage: gdb_snap.py <outfile> [host] [port]
"""
import socket, sys, time

def checksum(p): return b'%02x' % (sum(p) & 0xFF)

class GDB:
    def __init__(self, host, port):
        self.s = socket.create_connection((host, port), timeout=15)
        self.s.settimeout(15)
        self.f = self.s.makefile('rb')
    def send(self, payload):
        self.s.sendall(b'$' + payload + b'#' + checksum(payload))
    def read_pkt(self):
        f = self.f
        while True:
            ch = f.read(1)
            if ch == b'$':
                break
            if not ch:
                raise ConnectionError('closed')
        payload = b''
        while True:
            ch = f.read(1)
            if ch == b'#':
                break
            payload += ch
        f.read(2)
        self.s.sendall(b'+')
        return payload
    def read_mem(self, addr, length):
        out = bytearray()
        while length > 0:
            n = min(length, 0x2000)
            self.send(b'm%x,%x' % (addr, n))
            r = self.read_pkt()
            if r.startswith(b'E'):
                raise RuntimeError('read error %s at %x' % (r, addr))
            out += bytes.fromhex(r.decode())
            addr += n
            length -= n
        return bytes(out)

def main():
    out = sys.argv[1]
    host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 2345
    g = GDB(host, port)
    g.send(b'?')
    print('stop reply:', g.read_pkt())
    t0 = time.time()
    data = g.read_mem(0x80000000, 0x200000)
    dt = time.time() - t0
    # resume the game before leaving
    g.send(b'c')
    g.s.close()
    with open(out, 'wb') as fh:
        fh.write(data)
    print('snapped %d bytes in %.1fs (frozen) -> %s' % (len(data), dt, out))

if __name__ == '__main__':
    main()
