#!/usr/bin/env python3
"""Minimal GDB Remote Serial Protocol client for DuckStation's GDB server.

DuckStation listens on TCP 2345 (default). RSP essentials:
  packet = $payload#checksum   (checksum = sum(payload bytes) & 0xff, 2 hex)
  '+' = ack.  'm addr,len' = read memory.  'g' = read registers.
  'c' = continue.  Ctrl-C / 0x03 byte interrupts a running target.

Usage: gdb_client.py <host> <port> <hex_addr> <len> [--continue-first]
Prints the bytes read, hex + any ASCII.
"""
import socket, sys

def checksum(payload: bytes) -> bytes:
    return b'%02x' % (sum(payload) & 0xFF)

def send_packet(sock, payload: bytes):
    sock.sendall(b'$' + payload + b'#' + checksum(payload))

def read_packet(sock):
    # skip until '$'
    buf = b''
    while True:
        ch = sock.recv(1)
        if not ch:
            raise ConnectionError('socket closed')
        if ch == b'$':
            break
        if ch == b'+':
            continue
        buf += ch  # async notification bytes etc.
    payload = b''
    while True:
        ch = sock.recv(1)
        if ch == b'#':
            break
        payload += ch
    sock.recv(2)  # checksum
    sock.sendall(b'+')
    return payload

def main():
    host, port = sys.argv[1], int(sys.argv[2])
    addr, length = int(sys.argv[3], 16), int(sys.argv[4])
    s = socket.create_connection((host, port), timeout=10)
    s.settimeout(5)
    try:
        banner = s.recv(1024)
        print('on-connect recv:', banner[:120])
    except socket.timeout:
        print('on-connect: (nothing)')
    # query supported / halt reason
    for q in (b'qSupported:multiprocess+', b'?'):
        send_packet(s, q)
        try:
            print(q, '->', read_packet(s)[:300])
        except Exception as e:
            print(q, 'ERR', e)
    # read memory
    send_packet(s, b'm%x,%x' % (addr, length))
    try:
        data = read_packet(s)
        print('mem:', data[:length * 2])
        raw = bytes.fromhex(data.decode('ascii')) if data and data[:1] != b'E' else b''
        if raw:
            print('ascii:', ''.join(chr(c) if 32 <= c < 127 else '.' for c in raw))
    except Exception as e:
        print('mem ERR', e)
    # registers
    send_packet(s, b'g')
    try:
        print('regs:', read_packet(s)[:160])
    except Exception as e:
        print('regs ERR', e)
    # continue execution and close politely
    try:
        send_packet(s, b'c')
        print('continued')
    except Exception as e:
        print('continue ERR', e)
    s.close()

if __name__ == '__main__':
    main()
