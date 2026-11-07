#!/usr/bin/env python3
"""Matcher v2: brightness-normalised, overlay-masked hashing.

Differences from v1: frames and query are histogram-equalised before
hashing (fights the video's washed-out gamma vs DuckStation's dark
render), the top-left corner of video frames is masked out (the
walkthrough's map overlay lives there), and a coarse 4x4 colour-grid
distance is combined with the hash distance.

Usage: vidmatch2.py <frames_dir> <query_png> [tmin tmax] [topk]
"""
import os, sys
import numpy as np
from PIL import Image, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vidindex import phash, dhash, ham, crop_game_area

def prep(im: Image.Image, mask_map: bool) -> Image.Image:
    im = im.convert('RGB')
    if mask_map:
        # black out top-left 30% x 30% (map overlay corner)
        w, h = im.size
        blank = Image.new('RGB', (int(w * 0.30), int(h * 0.30)), (0, 0, 0))
        im.paste(blank, (0, 0))
    return im

def feats(im: Image.Image, mask_map: bool):
    p = prep(im, mask_map)
    g = ImageOps.equalize(p.convert('L'))
    g32 = np.asarray(g.resize((32, 32), Image.LANCZOS), dtype=np.float64)
    g9 = np.asarray(g.resize((9, 8), Image.LANCZOS), dtype=np.float64)
    # 4x4 colour grid on the un-equalised (but masked) image, /16 scale
    small = np.asarray(p.resize((4, 4), Image.BILINEAR), dtype=np.float64)
    return phash(g32), dhash(g9), small

def main():
    frames_dir, query = sys.argv[1], sys.argv[2]
    tmin = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    tmax = int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 9
    topk = int(sys.argv[5]) if len(sys.argv) > 5 else 8
    q_im = crop_game_area(query)
    qp, qd, qgrid = feats(q_im, mask_map=False)
    scored = []
    for name in sorted(os.listdir(frames_dir)):
        if not name.startswith('f_'):
            continue
        t = int(name[2:-4])
        if t < tmin or t > tmax:
            continue
        fp, fd, fgrid = feats(Image.open(os.path.join(frames_dir, name)), mask_map=True)
        hdist = ham(qp, fp) + ham(qd, fd)
        cdist = float(np.abs(qgrid - fgrid).mean()) / 16.0
        scored.append((hdist + cdist, hdist, round(cdist, 1), t))
    scored.sort()
    print(f'query {query}  window {tmin}-{tmax}s')
    for tot, h, c, t in scored[:topk]:
        print(f'  score {tot:6.1f} (hash {h:3d}, colour {c:5.1f})  t={t//60}:{t%60:02d}')

if __name__ == '__main__':
    main()
