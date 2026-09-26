#!/usr/bin/env python3
"""TASK-4999: check beacon frames printed by tb_ethbeacon (hex per line): preamble, header, FCS."""
import sys, zlib
ok = True
lines = [l.strip() for l in open(sys.argv[1]) if l.strip() and all(c in "0123456789abcdef" for c in l.strip())]
for l in lines:
    fr = bytes.fromhex(l); body, fcs = fr[8:-4], fr[-4:]
    good = (fr[:8] == b"\x55" * 7 + b"\xd5" and len(body) >= 60 and body[:6] == b"\xff" * 6
            and body[12:14] == b"\x88\xb5" and body[14:18] == b"T499"
            and zlib.crc32(body).to_bytes(4, "little") == fcs)
    print("frame %d B: %s" % (len(fr), "OK" if good else "BAD"))
    ok &= good
print("RESULT:", "PASS" if ok and lines else "FAIL"); sys.exit(0 if ok and lines else 1)
