#!/usr/bin/env python3
"""Find Beetle PSX's 2MB PS1 RAM inside the RetroArch process (/proc/<pid>/mem)
and read the calibrated TR3 addresses from it.
Candidate RAM base must satisfy ALL:
  s16 @ +0x9952E  (AIR)    == 1800
  s16 @ +0x1D6DF2 (HEALTH) == 1000
  3 x s32 @ +0x99898 (mirror pos) == 3 x s32 @ +0x1D6E10 (Lara struct pos)
  room s16 @ struct+0x12 in [0, 200]
"""
import struct, sys
pid = sys.argv[1]
LARA, MIRROR, HEALTH, AIR = 0x1D6E10, 0x99898, 0x1D6DF2, 0x9952E
def s16(b, o): return struct.unpack_from("<h", b, o)[0]
def s32(b, o): return struct.unpack_from("<i", b, o)[0]
regions = []
for line in open(f"/proc/{pid}/maps"):
    p = line.split()
    if p[1][0] != 'r': continue
    a, b = (int(x, 16) for x in p[0].split('-'))
    if b - a >= 0x200000: regions.append((a, b))
print(f"{len(regions)} readable regions >= 2MB")
mem = open(f"/proc/{pid}/mem", "rb")
hits = []
for a, b in regions:
    try:
        mem.seek(a); data = mem.read(b - a)
    except OSError:
        continue
    start = 0
    while True:
        i = data.find(b'\x08\x07', start)
        if i < 0: break
        base = i - AIR
        if base >= 0 and base + 0x1D6E30 <= len(data):
            if s16(data, base + HEALTH) == 1000 and \
               all(s32(data, base + MIRROR + 4*k) == s32(data, base + LARA + 4*k) for k in range(3)) and \
               0 <= s16(data, base + LARA + 0x12) <= 200:
                hits.append((a + base, data, base))
        start = i + 1
for addr, data, o in hits:
    print(f"RAM base @ host 0x{addr:X}")
    print(f"  pos=({s32(data,o+LARA)}, {s32(data,o+LARA+4)}, {s32(data,o+LARA+8)}) "
          f"yrot={s16(data,o+LARA+0xE)} room={s16(data,o+LARA+0x12)} "
          f"health={s16(data,o+HEALTH)} air={s16(data,o+AIR)}")
print(f"{len(hits)} candidate(s)")
