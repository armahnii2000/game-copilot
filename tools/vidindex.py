#!/usr/bin/env python3
"""Perceptual-hash index over walkthrough video frames + matcher.

Frames are named f_<seconds>.jpg in a directory. build() writes index.json
with a 64-bit pHash and 64-bit dHash per frame. match() takes a screenshot
(PNG from DuckStation window capture), crops to the game picture, and
returns the closest frames by hamming distance.

Usage:
  vidindex.py build <frames_dir> <index_json>
  vidindex.py match <index_json> <frames_dir> <query_png> [topk]
"""
import json, os, sys
import numpy as np
from PIL import Image

# --- DCT matrix for pHash (32x32 -> top-left 8x8) ---
N = 32
_x = np.arange(N)
_u = np.arange(N)[:, None]
DCT = np.cos((2 * _x + 1) * _u * np.pi / (2 * N))
DCT[0, :] *= 1.0 / np.sqrt(2)
DCT *= np.sqrt(2.0 / N)

def phash(img_gray_32: np.ndarray) -> int:
    d = DCT @ img_gray_32 @ DCT.T
    low = d[:8, :8]
    med = np.median(low[1:, :])  # exclude DC-ish row influence
    bits = (low > med).flatten()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h

def dhash(gray: np.ndarray) -> int:
    # gray resized to 9x8; bit = left brighter than right
    h = 0
    for r in range(8):
        for c in range(8):
            h = (h << 1) | int(gray[r, c] > gray[r, c + 1])
    return h

def features(path: str):
    im = Image.open(path).convert('L')
    g32 = np.asarray(im.resize((32, 32), Image.LANCZOS), dtype=np.float64)
    g9 = np.asarray(im.resize((9, 8), Image.LANCZOS), dtype=np.float64)
    return phash(g32), dhash(g9)

def ham(a: int, b: int) -> int:
    return bin(a ^ b).count('1')

def build(frames_dir, out_json):
    rows = []
    for name in sorted(os.listdir(frames_dir)):
        if not name.startswith('f_') or not name.endswith('.jpg'):
            continue
        t = int(name[2:-4])
        p, d = features(os.path.join(frames_dir, name))
        rows.append({'t': t, 'file': name, 'phash': p, 'dhash': d})
    rows.sort(key=lambda r: r['t'])
    json.dump(rows, open(out_json, 'w'))
    print(f'indexed {len(rows)} frames -> {out_json}')

def crop_game_area(png_path, out_path=None):
    """DuckStation window screenshot -> just the 4:3 game picture.
    The capture includes title bar (~48px at 2x on a 1335px-tall shot),
    black bars, and the status bar at the bottom. We find the picture by
    scanning for the non-black content rows, then crop the central 4:3."""
    im = Image.open(png_path).convert('RGB')
    w, h = im.size
    g = np.asarray(im.convert('L'), dtype=np.int32)
    row_ink = (g > 12).sum(axis=1)
    rows = np.where(row_ink > w * 0.05)[0]
    if len(rows) == 0:
        return im
    top, bot = rows[0], rows[-1]
    # drop the bottom status strip if present: status bar rows are mostly
    # dark with sparse text; the game picture is dense. Walk up from bot
    # while rows are sparse.
    while bot > top and row_ink[bot] < w * 0.35:
        bot -= 1
    pic = im.crop((0, int(top), w, int(bot) + 1))
    # centre-crop to 4:3
    pw, ph = pic.size
    target = ph * 4 / 3
    if pw > target:
        x0 = int((pw - target) / 2)
        pic = pic.crop((x0, 0, x0 + int(target), ph))
    if out_path:
        pic.save(out_path)
    return pic

def match(index_json, frames_dir, query_png, topk=6):
    rows = json.load(open(index_json))
    q = crop_game_area(query_png)
    tmp = '/tmp/_query_game.jpg'
    q.save(tmp)
    qp, qd = features(tmp)
    scored = []
    for r in rows:
        scored.append((ham(qp, r['phash']) + ham(qd, r['dhash']), r['t'], r['file']))
    scored.sort()
    print(f'query: {query_png} (game crop saved to {tmp})')
    for s, t, f in scored[:topk]:
        print(f'  dist {s:3d}  t={t//60}:{t%60:02d}  {f}')
    return scored[:topk]

if __name__ == '__main__':
    if sys.argv[1] == 'build':
        build(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'match':
        match(sys.argv[2], sys.argv[3], sys.argv[4],
              int(sys.argv[5]) if len(sys.argv) > 5 else 6)
