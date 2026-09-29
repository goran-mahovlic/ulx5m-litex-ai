#!/usr/bin/env python3
"""mkvar.py in.bit out.bit [--stat1b HEX] [--nops1b N]: rewrite the die-1B section end of a CCGM1A2 bitstream."""
import sys, argparse, gmbit
ap = argparse.ArgumentParser(); ap.add_argument('inp'); ap.add_argument('out')
ap.add_argument('--stat1b', type=lambda x: int(x, 0)); ap.add_argument('--nops1b', type=int, default=0)
a = ap.parse_args()
b = open(a.inp, 'rb').read(); recs = gmbit.parse(b)
st = [i for i, r in enumerate(recs) if r[1] == 'cmd' and r[2] == 0xdb and len(r[3]) == 12]
first = st[0]; out = bytearray()
for i, (o, k, c, d, raw) in enumerate(recs):
    if i == first and a.stat1b is not None:
        raw = gmbit.mk(0xdb, bytes([a.stat1b]) + d[1:])
    out += raw
    if i == first + 1 and a.nops1b: out += bytes(a.nops1b)
open(a.out, 'wb').write(out); print(a.out, len(b), '->', len(out))
