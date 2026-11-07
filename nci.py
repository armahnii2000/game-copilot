#!/usr/bin/env python3
"""RetroArch Network Control Interface (UDP) client + TR3 pose reader.

Sends text commands to RetroArch's NCI (default UDP 55355) and decodes
replies. The `pose` command reads the calibrated TR3 (USA v1.2) addresses:
  Lara struct @ 0x801D6E10: x s32 +0, y s32 +4, z s32 +8, yrot s16 +0xE, room s16 +0x12
  HEALTH s16 @ 0x801D6DF2 (struct - 0x1E), max 1000
  AIR    s16 @ 0x8009952E, max 1800
Tries READ_CORE_MEMORY (system map) first, falls back to READ_CORE_RAM
(cheevos map, address = PS1 addr - 0x80000000).
"""
import socket, struct, sys

HOST, PORT = "127.0.0.1", 55355

LARA = 0x801D6E10
HEALTH = 0x801D6DF2
AIR = 0x8009952E

def cmd(text, expect_reply=True, timeout=2.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    s.sendto(text.encode(), (HOST, PORT))
    if not expect_reply:
        return None
    try:
        data, _ = s.recvfrom(65535)
        return data.decode(errors="replace").strip()
    except socket.timeout:
        return None
    finally:
        s.close()

def read_mem(addr, nbytes):
    """Return bytes or None. System-map path first, cheevos path as fallback."""
    r = cmd(f"READ_CORE_MEMORY {addr:X} {nbytes}")
    if r and " -1" not in r:
        parts = r.split()
        # reply: READ_CORE_MEMORY <addr> <b0> <b1> ...
        try:
            return bytes(int(b, 16) for b in parts[2:2 + nbytes])
        except (ValueError, IndexError):
            pass
    r = cmd(f"READ_CORE_RAM {addr - 0x80000000:X} {nbytes}")
    if r and " -1" not in r:
        parts = r.split()
        try:
            return bytes(int(b, 16) for b in parts[2:2 + nbytes])
        except (ValueError, IndexError):
            pass
    return None

def pose():
    raw = read_mem(LARA, 0x14)
    if raw is None or len(raw) < 0x14:
        return None
    x, y, z = struct.unpack_from("<iii", raw, 0)
    yrot, room = struct.unpack_from("<hh", raw, 0x0E)
    h = read_mem(HEALTH, 2)
    a = read_mem(AIR, 2)
    health = struct.unpack("<h", h)[0] if h and len(h) == 2 else None
    air = struct.unpack("<h", a)[0] if a and len(a) == 2 else None
    return dict(x=x, y=y, z=z, yrot=yrot, room=room, health=health, air=air)

if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "pose"
    if what == "pose":
        p = pose()
        print(p if p else "NO READ (both memory paths failed)")
    elif what == "status":
        print(cmd("GET_STATUS"))
    elif what == "version":
        print(cmd("VERSION"))
    elif what == "msg":
        # fire-and-forget in most builds; print any reply just in case
        print(cmd("SHOW_MSG " + " ".join(sys.argv[2:]), timeout=0.7))
    elif what == "raw":
        print(cmd(" ".join(sys.argv[2:])))
    else:
        print("usage: nci.py [pose|status|version|msg <text>|raw <cmd...>]")
