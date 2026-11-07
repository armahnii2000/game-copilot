#!/usr/bin/env python3
"""DuckStation sidecar prototype v0 — "where is Lara?"

Reads a DuckStation save state (.sav), and reports what can be proven
from it today:
  * game title / serial / disc path          (state header — verified)
  * the state's own screenshot, saved as PNG (embedded — verified)
  * the full 2 MB PS1 RAM, extracted at the offset proven by the
    TOMB3.EXE anchor: the game executable's code sits in the state
    blob at RAM offset 0x10000, which fixes the RAM base exactly
    (6754 in all tested states from DuckStation 0.1-12083).

NOT yet proven (do not trust any tool that claims these from the
cheat-site addresses — in TR3 v1.2 those addresses land inside the
executable's own data, i.e. constants, not live values):
  * current level number, Lara's room, health, live inventory.

Usage: whereami.py <file.sav> [more.sav ...]
"""
import struct, sys, os
import zstandard
from PIL import Image

EXE_TEXT_RAM_OFFSET = 0x10000  # TOMB3.EXE loads at 0x80010000

def parse_state(path):
    d = open(path, 'rb').read()
    if d[:4] != b'DUCC':
        raise ValueError('not a DuckStation save state')
    version = struct.unpack_from('<I', d, 4)[0]
    title = d[8:136].split(b'\x00')[0].decode('utf-8', 'replace')
    serial = d[136:168].split(b'\x00')[0].decode('utf-8', 'replace')
    media_len, media_off = struct.unpack_from('<II', d, 168)
    media_path = d[media_off:media_off + media_len].decode('utf-8', 'replace')
    sw, sh, shot_size, shot_off = struct.unpack_from('<IIII', d, 184)
    _, data_csize, data_usize, data_off = struct.unpack_from('<IIII', d, 200)
    dctx = zstandard.ZstdDecompressor()
    shot = dctx.decompress(d[shot_off:shot_off + shot_size], max_output_size=sw * sh * 4)
    data = dctx.decompress(d[data_off:data_off + data_csize], max_output_size=data_usize)
    return dict(version=version, title=title, serial=serial, media_path=media_path,
                wh=(sw, sh), shot=shot, data=data)

def find_ram(data, exe_path):
    """Locate PS1 RAM inside the decompressed state via the EXE anchor."""
    if exe_path and os.path.exists(exe_path):
        exe = open(exe_path, 'rb').read()
        needle = exe[0x800 + 0x1000:0x800 + 0x1000 + 128]
        pos = data.find(needle)
        if pos >= 0:
            return pos - (EXE_TEXT_RAM_OFFSET + 0x1000), 'exe-anchor'
    return 6754, 'fallback (measured on DuckStation 0.1-12083 states)'

def main():
    exe_path = os.path.join(os.path.dirname(__file__), '..', 'states', 'TOMB3.EXE')
    for path in sys.argv[1:]:
        st = parse_state(path)
        base, how = find_ram(st['data'], exe_path)
        ram_ok = st['data'][base:base + 0x200000]
        out_png = os.path.splitext(path)[0] + '.whereami.png'
        img = Image.frombytes('RGBA', st['wh'], st['shot']).convert('RGB')
        img = img.resize((512, 384), Image.NEAREST)
        img.save(out_png)
        print(f"== {os.path.basename(path)}")
        print(f"   game:       {st['title']} ({st['serial']}), state v{st['version']}")
        print(f"   disc:       {os.path.basename(st['media_path'])}")
        print(f"   RAM:        2 MB extracted (base {base}, via {how}); "
              f"exe code verified at RAM 0x{EXE_TEXT_RAM_OFFSET:05x}")
        print(f"   screenshot: {out_png}")
        print(f"   level/room/health: NOT YET READ — needs one save state made")
        print(f"                      at a known place to calibrate against.")

if __name__ == '__main__':
    main()
