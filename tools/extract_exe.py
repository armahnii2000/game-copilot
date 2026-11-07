#!/usr/bin/env python3
"""Extract a file from a PS1 .bin disc image (MODE2/XA, 2352-byte sectors).
Usage: extract_exe.py <bin_path> <FILENAME;1>  -> writes file to stdout (binary)
Runs on the host Mac with system python3."""
import sys, struct

SECTOR = 2352
DATA_OFF = 24  # MODE2/XA Form1 user data offset
DATA_LEN = 2048

def sector(f, n):
    f.seek(n * SECTOR + DATA_OFF)
    return f.read(DATA_LEN)

def read_extent(f, lba, size):
    out = bytearray()
    remaining = size
    s = lba
    while remaining > 0:
        chunk = sector(f, s)
        take = min(DATA_LEN, remaining)
        out += chunk[:take]
        remaining -= take
        s += 1
    return bytes(out)

def parse_dir(data):
    entries = []
    i = 0
    while i < len(data):
        ln = data[i]
        if ln == 0:
            # skip to next 2048 block boundary
            i = ((i // DATA_LEN) + 1) * DATA_LEN
            if i >= len(data):
                break
            continue
        rec = data[i:i+ln]
        lba = struct.unpack_from('<I', rec, 2)[0]
        size = struct.unpack_from('<I', rec, 10)[0]
        flags = rec[25]
        nlen = rec[32]
        name = rec[33:33+nlen].decode('ascii', 'replace')
        entries.append((name, lba, size, flags))
        i += ln
    return entries

def main():
    bin_path, want = sys.argv[1], sys.argv[2].upper()
    f = open(bin_path, 'rb')
    pvd = sector(f, 16)
    assert pvd[1:6] == b'CD001', 'not an ISO'
    root = pvd[156:156+34]
    root_lba = struct.unpack_from('<I', root, 2)[0]
    root_size = struct.unpack_from('<I', root, 10)[0]
    root_data = read_extent(f, root_lba, root_size)
    for name, lba, size, flags in parse_dir(root_data):
        sys.stderr.write(f'{name} lba={lba} size={size} dir={bool(flags & 2)}\n')
        if name.upper() == want:
            sys.stdout.buffer.write(read_extent(f, lba, size))
            return
    sys.stderr.write('NOT FOUND\n')
    sys.exit(1)

if __name__ == '__main__':
    main()
