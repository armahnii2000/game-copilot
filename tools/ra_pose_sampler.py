import socket, struct, time, sys

def rd(addr, n):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(5.0)
    s.sendto(f"READ_CORE_RAM {addr:X} {n}".encode(), ("127.0.0.1", 55355))
    try:
        d, _ = s.recvfrom(65535)
        parts = d.decode(errors="replace").split()
        if len(parts) < 2 + n or parts[0] != "READ_CORE_RAM":
            return None
        return bytes(int(x, 16) for x in parts[2:2 + n])
    except Exception:
        return None
    finally:
        s.close()

def pose():
    st = rd(0x1D6E10, 24); air = rd(0x9952E, 2); hp = rd(0x1D6DF2, 2)
    if not st or air is None or hp is None:
        return None
    x, y, z = struct.unpack_from("<iii", st, 0)
    yrot = struct.unpack_from("<h", st, 0xE)[0]
    room = struct.unpack_from("<h", st, 0x12)[0]
    return (x, y, z, yrot, room,
            struct.unpack("<h", air)[0], struct.unpack("<h", hp)[0])

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    gap = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
    for i in range(n):
        p = pose()
        if p:
            print(f"sample {i}: pos=({p[0]},{p[1]},{p[2]}) yrot={p[3]} room={p[4]} air={p[5]} health={p[6]}", flush=True)
        else:
            print(f"sample {i}: no data", flush=True)
        if i < n - 1:
            time.sleep(gap)
