#!/usr/bin/env python3
"""Dump full PS1 RAM (2 MB at 0x80000000) from DuckStation via GDB,
while the game keeps running. Saves raw binary + prints timing.
Usage: gdb_dump.py <outfile> [host] [port]"""
import socket, sys, time

def checksum(p): return b'%02x' % (sum(p) & 0xFF)

class GDB:
    def __init__(self, host, port):
        self.s = socket.create_connection((host, port), timeout=10)
        self.s.settimeout(10)
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
    def cmd(self, payload):
        self.send(payload)
        return self.read_pkt()

def main():
    out = sys.argv[1]
    host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 2345
    g = GDB(host, port)
    g.cmd(b'qSupported:multiprocess+')
    g.cmd(b'?')            # initial halt state
    g.send(b'c')           # resume; consume ack only
    g.f.read(1)
    base, total = 0x80000000, 0x200000
    chunk = 0x2000         # 8 KB per packet (larger reads return E01)
    ram = bytearray()
    t0 = time.time()
    done = 0
    while done < total:
        n = min(chunk, total - done)
        data = g.cmd(b'm%x,%x' % (base + done, n))
        if data[:1] == b'E':
            raise RuntimeError('read error at %x: %r' % (base + done, data))
        ram += bytes.fromhex(data.decode('ascii'))
        done += n
    dt = time.time() - t0
    open(out, 'wb').write(ram)
    print(f'dumped {len(ram)} bytes in {dt:.1f}s -> {out}')
    g.s.close()

if __name__ == '__main__':
    main()
