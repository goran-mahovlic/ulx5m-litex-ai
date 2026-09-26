#!/usr/bin/env python3
"""gm_cfgrst_check.py — je li GateMate bitstream pakiran s `gmpack --reset` (CMD_CFGRST)?

Bez CMD_CFGRST rijetki bitstream (samo korišteni okviri) upisuje se preko ostataka
prethodnog dizajna, a `openFPGALoader -r` ih ne počisti (LESSONS_GATEMATE H1/H9/H10).

Potpis (mjereno nad parovima isti .cfg s/bez --reset, gmpack v1.13-6):
16-bajtna preambula, zatim prva naredba. S --reset ona je CMD_CFGRST = c3 01 0c;
bez njega prvo dolazi dd 01 (PLL/konfiguracija).

Uporaba:  gm_cfgrst_check.py <f.bit|mapa> ...   exit 0 = svi imaju CFGRST, 1 = neki nemaju, 2 = nije GateMate
"""
import os
import sys

PREAMBLE_LEN = 16
CFGRST = bytes.fromhex("c3010c")


def classify(path):
    with open(path, "rb") as f:
        head = f.read(PREAMBLE_LEN + len(CFGRST))
    if len(head) < PREAMBLE_LEN + len(CFGRST) or head[:2] != b"\xd9\x01":
        return "NOT_GATEMATE"
    return "CFGRST" if head[PREAMBLE_LEN:] == CFGRST else "NO_CFGRST"


def iter_bits(args):
    for a in args:
        if os.path.isdir(a):
            for root, _, files in os.walk(a):
                for n in sorted(files):
                    if n.endswith(".bit"):
                        yield os.path.join(root, n)
        else:
            yield a


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    worst = 0
    for p in iter_bits(argv):
        c = classify(p)
        print(f"{c:12s} {p}")
        worst = max(worst, {"CFGRST": 0, "NO_CFGRST": 1, "NOT_GATEMATE": 2}[c])
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
