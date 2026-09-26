#!/usr/bin/env python3
"""TASK-5032: minimal Etherbone read over UDP (LiteX LiteEthEtherbone, port 1234). eb_read.py <ip> <addr> [n]
Prints n 32-bit words from the SoC bus starting at addr (e.g. a CSR from csr.csv)."""
import socket, struct, sys

def eb_read(ip, addr, port=1234, timeout=2.0):
    hdr = struct.pack(">HBBI", 0x4e6f, 0x10, 0x44, 0)                    # magic, version 1, 32-bit addr/port, pad
    rec = struct.pack(">BBBB", 0x00, 0x0f, 0, 1) + struct.pack(">II", 0, addr)   # read 1 word, base_ret 0
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(timeout)
    # LiteEthEtherbone replies to dst_port = udp_port (liteeth/frontend/etherbone.py), not to our source
    # port: listen on the Etherbone port itself, like litex/tools/remote/comm_udp.py.
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("", port))
    s.sendto(hdr + rec, (ip, port))
    d, _ = s.recvfrom(2048)
    s.close()
    return struct.unpack(">I", d[-4:])[0]

if __name__ == "__main__":
    ip, a = sys.argv[1], int(sys.argv[2], 0); n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    for i in range(n):
        print("0x%08x: 0x%08x" % (a + 4*i, eb_read(ip, a + 4*i)))
