#!/usr/bin/env python3
"""TASK-4999: RGMII RX stimuli for the io50 RTL sim (ICMP echo requests of several sizes + ARP reply)
and the checker for the frames the design transmits (frames_tx.txt, one hex frame per line incl.
preamble/SFD/FCS)."""
import sys, struct, zlib
PI_MAC, PI_IP = bytes.fromhex("b827ebb2b02c"), bytes([192, 168, 10, 14])
BD_MAC, BD_IP = bytes.fromhex("10e2d5000000"), bytes([192, 168, 10, 212])

def csum(b):
    if len(b) % 2: b += b"\0"
    s = sum(struct.unpack("!%dH" % (len(b)//2), b)); s = (s & 0xFFFF) + (s >> 16); s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF

def wire(frame):
    if len(frame) < 60: frame += b"\0" * (60 - len(frame))
    return b"\x55"*7 + b"\xd5" + frame + zlib.crc32(frame).to_bytes(4, "little")

def icmp_req(s, seq):
    data = bytes((i + 8) & 0xFF for i in range(s))
    icmp = struct.pack("!BBHHH", 8, 0, 0, 0x4999, seq) + data
    icmp = icmp[:2] + struct.pack("!H", csum(icmp)) + icmp[4:]
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(icmp), seq, 0x4000, 64, 1, 0, PI_IP, BD_IP)
    ip = ip[:10] + struct.pack("!H", csum(ip)) + ip[12:]
    return wire(BD_MAC + PI_MAC + b"\x08\x00" + ip + icmp)

def arp_reply():
    arp = struct.pack("!HHBBH6s4s6s4s", 1, 0x800, 6, 4, 2, PI_MAC, PI_IP, BD_MAC, BD_IP)
    return wire(BD_MAC + PI_MAC + b"\x08\x06" + arp)

import os
SIZES = [int(x) for x in os.environ.get('SIZES', '10,18,19,20,100,1000').split(',')]
ICMP_DEPTH = int(os.environ.get('ICMP_DEPTH', '128'))

def gen():
    with open("rx_frames.hex", "w") as f:
        f.write(arp_reply().hex() + "\n")
        for i, s in enumerate(SIZES):
            f.write(icmp_req(s, i + 1).hex() + "\n")
    print("wrote rx_frames.hex: arp_reply + ICMP sizes", SIZES)

def check(path):
    ok = True; replies = {}
    for line in open(path):
        line = line.strip()
        if not line: continue
        fr = bytes.fromhex(line)
        pre_ok = fr[:8] == b"\x55"*7 + b"\xd5"; body, fcs = fr[8:-4], fr[-4:]
        fcs_ok = zlib.crc32(body).to_bytes(4, "little") == fcs
        et = body[12:14].hex() if len(body) > 14 else "?"
        desc = "len %d et %s pre %s fcs %s" % (len(body), et, pre_ok, fcs_ok)
        if et == "0800" and len(body) > 34 and body[23] == 1 and body[34] == 0:
            seq = struct.unpack("!H", body[40:42])[0]; s = SIZES[seq - 1]
            good = pre_ok and fcs_ok and len(body) == max(60, 14 + 20 + 8 + s) and body[42:42 + s] == bytes((i + 8) & 0xFF for i in range(s))
            replies[s] = good; desc += "  ICMP reply seq %d (-s %d): %s" % (seq, s, "OK" if good else "BAD")
        print(desc)
    for s in SIZES:
        print("-s %-4d: %s" % (s, {True: "REPLY OK", False: "REPLY BAD"}.get(replies.get(s), "NO REPLY")))
    return all(replies.get(s) for s in SIZES if s + 8 <= ICMP_DEPTH)   # icmp_fifo_depth=128: bigger pings are dropped by design

if __name__ == "__main__":
    if sys.argv[1] == "gen": gen()
    else: sys.exit(0 if check(sys.argv[2]) else 1)
