#!/usr/bin/env python3
"""TASK-5032: decode the ULX5M-GS GbE L2 beacons (ethertype 0x88B5, magic T4999L2, tag 0x32) from a pcap.
Also counts ARP/ICMP frames from the board. Usage: beacon.py <file.pcap>"""
import struct, sys, collections

def frames(path):
    d = open(path, "rb").read()
    magic = struct.unpack("<I", d[:4])[0]
    ns = magic == 0xa1b23c4d
    off = 24
    while off + 16 <= len(d):
        ts, tf, incl, orig = struct.unpack("<IIII", d[off:off+16]); off += 16
        yield ts + tf / (1e9 if ns else 1e6), d[off:off+incl]; off += incl

def main(path):
    bmac = bytes.fromhex("10e2d5000000")
    per_sel = collections.Counter(); last = None; n = 0; kinds = collections.Counter(); t0 = None
    for t, f in frames(path):
        if len(f) < 14: continue
        t0 = t0 or t
        src, et = f[6:12], f[12:14].hex()
        if src != bmac:
            continue
        if et == "88b5" and f[14:21] == b"T4999L2" and f[21] == 0x32:
            p = f[24:]
            sel = p[0]; rxf = struct.unpack(">H", p[1:3])[0]; drops = p[3]; rsel = p[4]; flips = p[5]
            txf = struct.unpack(">H", p[6:8])[0]; passes = p[8]
            r1, ra, rf = [struct.unpack(">H", p[i:i+2])[0] for i in (9, 11, 13)]
            rfreq = int.from_bytes(p[15:18], "big")
            per_sel[sel] += 1; n += 1
            last = (t - t0, sel, rxf, drops, rsel, flips, txf, passes, r1, ra, rf, rfreq)
        else:
            kinds[et] += 1
    print("beacons from board: %d, per TXC sel: %s" % (n, dict(sorted(per_sel.items()))))
    print("other frames from board by ethertype: %s" % dict(kinds))
    if last:
        t, sel, rxf, drops, rsel, flips, txf, passes, r1, ra, rf, rfreq = last
        spd = {0: "?", 1: "10", 2: "100", 4: "1000"}.get((rf >> 4) & 7, "?")
        print("last beacon t=%.1fs sel=%d rx_frames=%d rx_drops=%d rx_sel=%d rx_flips=%d tx_frames=%d mdio_passes=%d"
              % (t, sel, rxf, drops, rsel, flips, txf, passes))
        print("  R1=%04X (link %d) RA=%04X (LP 1000FD %d) R1F=%04X (speed bits %s, duplex %d) RXC count=%06X (~%.1f MHz @20 MHz sys)"
              % (r1, (r1 >> 2) & 1, ra, (ra >> 11) & 1, rf, spd, (rf >> 3) & 1, rfreq, rfreq / 2**20 * 20))

if __name__ == "__main__":
    main(sys.argv[1])
