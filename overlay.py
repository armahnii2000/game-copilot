#!/usr/bin/env python3
"""DuckStation help overlay — prototype (text only).

A slim always-on-top bar that sits over the top of the DuckStation
window and shows the current hint. It re-reads its message file every
500 ms, so the watcher (separate process) can update what the player sees
live just by writing the file.

Message file format (~/duckstation-help-overlay.txt):
    line 1: heading   (e.g. "ALDWYCH — NEXT")
    rest:   the hint text

Usage: overlay.py [seconds_to_live]   (0 = run until killed)
Runs on the host Mac with the system python3 (tkinter).
"""
import sys, os, time
import tkinter as tk

MSG_FILE = os.path.expanduser('~/duckstation-help-overlay.txt')

# DuckStation window measured live 2026-11-03: pos (618,33), size 894x874
# on a 1512x982 logical screen. Bar spans the top of that window.
BAR_W = 880
BAR_X = 625
BAR_Y = 42

def read_msg():
    try:
        with open(MSG_FILE) as f:
            lines = f.read().strip().split('\n')
        head = lines[0] if lines else ''
        body = ' '.join(l.strip() for l in lines[1:]) if len(lines) > 1 else ''
        return head, body
    except OSError:
        return 'DUCKSTATION HELP', 'watching…'

def main():
    ttl = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    root = tk.Tk()
    root.overrideredirect(True)                 # no title bar / borders
    root.attributes('-topmost', True)           # stay above the game
    try:
        root.attributes('-alpha', 0.88)         # slightly see-through
    except tk.TclError:
        pass
    root.geometry(f'{BAR_W}x64+{BAR_X}+{BAR_Y}')
    root.configure(bg='#101418')
    head_lbl = tk.Label(root, text='', fg='#ffd76a', bg='#101418',
                        font=('Helvetica', 13, 'bold'), anchor='w')
    head_lbl.pack(fill='x', padx=12, pady=(6, 0))
    body_lbl = tk.Label(root, text='', fg='#ffffff', bg='#101418',
                        font=('Helvetica', 14), anchor='w', wraplength=BAR_W - 24,
                        justify='left')
    body_lbl.pack(fill='x', padx=12)
    start = time.time()
    def tick():
        h, b = read_msg()
        if head_lbl.cget('text') != h:
            head_lbl.config(text=h)
        if body_lbl.cget('text') != b:
            body_lbl.config(text=b)
        if ttl and time.time() - start > ttl:
            root.destroy()
            return
        root.after(500, tick)
    tick()
    root.mainloop()

if __name__ == '__main__':
    main()
