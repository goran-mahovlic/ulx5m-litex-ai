#!/usr/bin/env python3
#
# Host-side smoke test for the UDP echo design. Sends N datagrams to the board's
# UDP echo port and checks each one comes back unchanged.
#
# Usage:
#   python3 test_script/udp_echo_test.py [--ip 10.10.10.50] [--port 7000] [--count 50]
#
# Set your host NIC to the same subnet first, e.g.:
#   sudo ip addr add 10.10.10.1/24 dev <iface>
#
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import socket
import sys
import time


def main():
    ap = argparse.ArgumentParser(description="UDP echo smoke test")
    ap.add_argument("--ip",    default="10.10.10.50", help="Board IP address.")
    ap.add_argument("--port",  default=7000, type=int, help="UDP echo port.")
    ap.add_argument("--count", default=50, type=int,   help="Number of datagrams to send.")
    ap.add_argument("--timeout", default=0.5, type=float, help="Per-packet reply timeout (s).")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(args.timeout)

    ok = 0
    for i in range(args.count):
        payload = f"echo-{i:04d}-".encode() + bytes((i * 7 + j) & 0xff for j in range(16))
        try:
            sock.sendto(payload, (args.ip, args.port))
            data, _ = sock.recvfrom(2048)
            if data == payload:
                ok += 1
            else:
                print(f"  [{i}] MISMATCH: sent {len(payload)}B, got {len(data)}B")
        except socket.timeout:
            print(f"  [{i}] TIMEOUT (no reply)")
        time.sleep(0.005)

    pct = 100.0 * ok / args.count if args.count else 0.0
    print(f"echo: {ok}/{args.count} round-trips OK ({pct:.0f}%)")
    sock.close()
    sys.exit(0 if ok == args.count else 1)


if __name__ == "__main__":
    main()
