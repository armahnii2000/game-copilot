#!/usr/bin/env python3
"""Calibration watcher: while the player plays, snapshot the game-state RAM
window every ~20 s and log which offsets change versus the paused-room
baseline and versus the previous snapshot. Room/position addresses are
the offsets that jump discretely when he crosses rooms; timers and
animation counters churn constantly and get filtered by frequency.

Window: RAM 0x80080000..0x80110000 (file offsets 0x80000..0x110000).
Baseline: states/ram_roomA_paused.bin (paused, Masonic-temple room).
Log: states/cal_watch.log  (JSON lines). Snapshots kept only when the
diff-vs-baseline cluster pattern changes materially.
"""
import json, os, socket, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdb_dump import GDB

HERE = os.path.dirname(os.path.abspath(__file__))
STATES = os.path.join(HERE, '..', 'states')
BASE_OFF, WIN = 0x80000, 0x90000
BASE_ADDR = 0x80000000 + BASE_OFF
LOG = os.path.join(STATES, 'cal_watch.log')

def read_window(g):
    out = bytearray()
    done = 0
    while done < WIN:
        n = min(0x2000, WIN - done)
        data = g.cmd(b'm%x,%x' % (BASE_ADDR + done, n))
        if data[:1] == b'E':
            raise RuntimeError('read error: %r' % data)
        out += bytes.fromhex(data.decode('ascii'))
        done += n
    return bytes(out)

def clusters(diffs, gap=16):
    out = []
    for i in diffs:
        if out and i - out[-1][1] <= gap:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out

def main():
    minutes = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    baseline = open(os.path.join(STATES, 'ram_roomA_paused.bin'), 'rb').read()[BASE_OFF:BASE_OFF + WIN]
    g = GDB('127.0.0.1', 2345)
    g.cmd(b'qSupported:multiprocess+')
    g.cmd(b'?')
    g.send(b'c')
    g.f.read(1)
    prev = None
    seen_counts = {}
    deadline = time.time() + minutes * 60
    it = 0
    with open(LOG, 'a') as log:
        log.write(json.dumps({'t': time.time(), 'event': 'watch_start', 'minutes': minutes}) + '\n')
        log.flush()
        while time.time() < deadline:
            it += 1
            try:
                snap = read_window(g)
            except Exception as e:
                log.write(json.dumps({'t': time.time(), 'event': 'read_error', 'err': str(e)}) + '\n')
                log.flush()
                time.sleep(10)
                try:
                    g = GDB('127.0.0.1', 2345)
                    g.cmd(b'?')
                    g.send(b'c')
                    g.f.read(1)
                except Exception:
                    pass
                continue
            d_base = [i for i in range(WIN) if snap[i] != baseline[i]]
            for i in d_base:
                seen_counts[i] = seen_counts.get(i, 0) + 1
            rec = {'t': time.time(), 'iter': it,
                   'changed_vs_baseline': len(d_base),
                   'clusters_vs_baseline': len(clusters(d_base))}
            if prev is not None:
                d_prev = [i for i in range(WIN) if snap[i] != prev[i]]
                rec['changed_vs_prev'] = len(d_prev)
                rec['clusters_vs_prev'] = clusters(d_prev)[:24]
            log.write(json.dumps(rec) + '\n')
            log.flush()
            # keep a snapshot every iteration is too much; keep every 6th
            if it % 6 == 1:
                open(os.path.join(STATES, f'cal_snap_{it:03d}.bin'), 'wb').write(snap)
            prev = snap
            time.sleep(20)
        # final: offsets ranked by stability (changed in few snapshots =
        # discrete state, not churn)
        freq = sorted(seen_counts.items(), key=lambda kv: kv[1])
        log.write(json.dumps({'t': time.time(), 'event': 'watch_end',
                              'iters': it,
                              'rarest_changed_offsets': [hex(BASE_OFF + i) for i, c in freq[:200] if c <= max(2, it // 3)]}) + '\n')
        log.flush()
    g.s.close()

if __name__ == '__main__':
    main()
