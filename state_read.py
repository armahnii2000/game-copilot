#!/usr/bin/env python3
"""Prototype v0: parse a DuckStation .sav save state.

Reads the header, decompresses the embedded screenshot and the main
state data (both zstd), and saves them next to the state file.
Header layout verified empirically against SLUS-00691_1.sav
(DuckStation 0.1-12083, save state version 87).
"""
import struct, sys, os
import zstandard

def parse(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'DUCC', 'not a DuckStation state'
    version = struct.unpack_from('<I', d, 4)[0]
    title = d[8:136].split(b'\x00')[0].decode('utf-8', 'replace')
    serial = d[136:168].split(b'\x00')[0].decode('utf-8', 'replace')
    media_len, media_off = struct.unpack_from('<II', d, 168)
    media_path = d[media_off:media_off+media_len].decode('utf-8', 'replace')
    shot_ctype = struct.unpack_from('<I', d, 180)[0]
    sw, sh, shot_size, shot_off = struct.unpack_from('<IIII', d, 184)
    data_ctype, data_csize, data_usize, data_off = struct.unpack_from('<IIII', d, 200)
    out = {'version': version, 'title': title, 'serial': serial,
           'media_path': media_path, 'screenshot_wh': (sw, sh),
           'shot_ctype': shot_ctype, 'data_ctype': data_ctype,
           'data_csize': data_csize, 'data_usize': data_usize}
    dctx = zstandard.ZstdDecompressor()
    shot_raw = dctx.decompress(d[shot_off:shot_off+shot_size], max_output_size=sw*sh*4)
    data = dctx.decompress(d[data_off:data_off+data_csize], max_output_size=data_usize)
    out['shot_raw_len'] = len(shot_raw)
    out['data_len'] = len(data)
    return out, shot_raw, data

if __name__ == '__main__':
    path = sys.argv[1]
    info, shot, data = parse(path)
    for k, v in info.items():
        print(f'{k}: {v}')
    base = os.path.splitext(path)[0]
    open(base + '.shot.raw', 'wb').write(shot)
    open(base + '.state.bin', 'wb').write(data)
    print('wrote', base + '.shot.raw', 'and', base + '.state.bin')
