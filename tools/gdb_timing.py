#!/usr/bin/env python3
"""Measure the cost of a GDB read cycle against DuckStation:
connect, then N times (interrupt -> read 256 bytes -> continue),
timing each phase. If a cycle costs only a few ms of halt, polling
once or twice a second is invisible in a 30 FPS game."""
import socket, sys, time

def checksum(p): return b'%02x' % (sum(p) & 0xFF)

class GDB:
    def __init__(self, host, port):
        self.s = socket.create_connection((host, port), timeout=10)
        self.s.settimeout(5)
        self.buf = b''
    def send(self, payload):
        self.s.sendall(b'$' + payload + b'#' + checksum(payload))
    def read_pkt(self):
        while True:
            ch = self.s.recv(1)
            if ch == b'$':
                break
            if not ch:
                raise ConnectionError('closed')
        payload = b''
        while True:
            ch = self.s.recv(1)
            if ch == b'#':
                break
            payload += ch
        self.s.recv(2)
        self.s.sendall(b'+')
        return payload
    def cmd(self, payload):
        self.send(payload)
        return self.read_pkt()
    def cont(self):
        # 'c' gets only a '+' ack now; the next packet is the stop reply
        # when the target halts again. Consume just the ack.
        self.send(b'c')
        self.s.settimeout(2)
        try:
            while True:
                ch = self.s.recv(1)
                if ch == b'+':
                    break
        finally:
            self.s.settimeout(5)
    def interrupt(self):
        self.s.sendall(b'\x03')
        return self.read_pkt()  # stop reply Txx

def main():
    host, port = sys.argv[1], int(sys.argv[2])
    addr = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x80010000
    g = GDB(host, port)
    print('supported:', g.cmd(b'qSupported:multiprocess+')[:60])
    print('halt reason:', g.cmd(b'?'))
    cycles = []
    for i in range(10):
        t0 = time.perf_counter()
        g.cont()                        # resume (ack only)
        t_resume = time.perf_counter()
        time.sleep(0.25)                # let the game run ~15 frames
        stop = g.interrupt()            # halt again
        t_halt = time.perf_counter()
        data = g.cmd(b'm%x,100' % addr) # read 256 bytes while halted
        cycles.append(((t_halt - t_resume) * 1000, len(data)))
    g.cont()
    g.s.close()
    print('interrupt->stop+read cycles (ms, reply hex chars):')
    for c in cycles:
        print(f'  {c[0]:.1f} ms, {c[1]}')
    # verify bytes match TOMB3.EXE text
    import os
    exe_path = os.path.join(os.path.dirname(__file__), '..', 'states', 'TOMB3.EXE')
    if os.path.exists(exe_path):
        exe = open(exe_path, 'rb').read()
        expect = exe[0x800:0x800 + 32].hex()
        g2 = GDB(host, port)
        g2.cmd(b'?')
        got = g2.cmd(b'm%x,20' % addr).decode()
        g2.cont()
        g2.s.close()
        print('exe expect:', expect)
        print('gdb got   :', got)
        print('MATCH' if expect == got else 'MISMATCH')

if __name__ == '__main__':
    main()
