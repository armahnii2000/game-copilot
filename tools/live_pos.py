#!/usr/bin/env python3
"""Live position probe for TR3 (DuckStation GDB server).

Samples Lara's candidate item struct at 0x801D6E10 (and the work copy at
0x80099898) while the game runs: halt -> tiny read -> continue, ~5 Hz.

Fields (ITEM_INFO layout, verified empirically 2026-11-04 on the VM copy):
  +0x00 x (s32)  +0x04 y (s32)  +0x08 z (s32)
  +0x0C x_rot (s16)  +0x0E y_rot (s16)  +0x10 z_rot (s16)
  +0x12 room_number (s16)

Usage: live_pos.py [seconds]
"""
import socket, struct, sys, time

sys.path.insert(0, 'src')
from gdb_client import send_packet, read_packet

LARA = 0x801D6E10
COPY = 0x80099898

def parse(buf, base_has_room=True):
    x, y, z = struct.unpack_from('<iii', buf, 0)
    xr, yr, zr = struct.unpack_from('<hhh', buf, 0x0C)
    room = struct.unpack_from('<h', buf, 0x12)[0] if base_has_room else -1
    return x, y, z, xr, yr, zr, room

def main():
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    s = socket.create_connection(('127.0.0.1', 2345), timeout=10)
    s.settimeout(5)
    try:
        try:
            s.recv(1024)  # banner / stop reply on connect
        except socket.timeout:
            pass
        t0 = time.time()
        n = 0
        while time.time() - t0 < dur:
            send_packet(s, b'm%x,%x' % (LARA, 0x30))
            buf = bytes.fromhex(read_packet(s).decode())
            send_packet(s, b'm%x,%x' % (COPY, 0x14))
            buf2 = bytes.fromhex(read_packet(s).decode())
            x, y, z, xr, yr, zr, room = parse(buf)
            x2, y2, z2 = struct.unpack_from('<iii', buf2, 0)
            yr2 = struct.unpack_from('<h', buf2, 0x0E)[0]
            print(f'{time.time()-t0:6.2f}s room={room:3d} x={x:7d} y={y:6d} z={z:7d} '
                  f'yrot={yr:6d} | copy x={x2} z={z2} yrot={yr2}', flush=True)
            n += 1
            send_packet(s, b'c')
            time.sleep(0.15)
            s.sendall(b'\x03')  # halt again
            try:
                read_packet(s)  # stop reply
            except Exception:
                pass
        print(f'{n} samples in {time.time()-t0:.1f}s')
    finally:
        try:
            send_packet(s, b'c')
        except Exception:
            pass
        s.close()

if __name__ == '__main__':
    main()
