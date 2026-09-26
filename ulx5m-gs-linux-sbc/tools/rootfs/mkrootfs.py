#!/usr/bin/env python3
"""mkrootfs.py <orig.cpio> <out.cpio> — ULX5M-GS rootfs.cpio (newc) s dodacima:
  - /etc/network/interfaces: eth0 statički 192.168.10.213 odmah na bootu
  - /bin/banner, /bin/banner_ascii: banner programi (rv32ima Linux, statički)
  /etc/motd ostaje originalni LiteX banner (Goran, 25.09.2026.).
Postojeće datoteke istog imena zamjenjuju se, nove se dodaju prije TRAILER-a."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADD = {  # ime u arhivi -> (mode, datoteka u ovoj mapi)
    "etc/network/interfaces": (0o100644, "interfaces"),
    "bin/banner":             (0o100755, "banner"),
    "bin/banner_ascii":       (0o100755, "banner_ascii"),
}


def parse(d):
    i, ents = 0, []
    while d[i:i + 6] == b"070701":
        h = d[i:i + 110]
        ns, fs = int(h[94:102], 16), int(h[54:62], 16)
        name = d[i + 110:i + 110 + ns - 1].decode()
        p = (i + 110 + ns + 3) & ~3
        if name == "TRAILER!!!":
            return ents, h
        ents.append((h, name, d[p:p + fs]))
        i = (p + fs + 3) & ~3
    raise SystemExit("nije newc cpio ili nema TRAILER-a")


def fields(h):
    return [int(h[6 + 8 * k:14 + 8 * k], 16) for k in range(13)]


def entry(f, name, data):
    f = list(f)
    f[6], f[11], f[12] = len(data), len(name) + 1, 0
    b = b"070701" + b"".join(b"%08X" % v for v in f) + name.encode() + b"\0"
    b += b"\0" * ((4 - len(b) % 4) % 4)
    return b + data + b"\0" * ((4 - len(data) % 4) % 4)


def main():
    src, out = sys.argv[1], sys.argv[2]
    ents, trailer = parse(open(src, "rb").read())
    add = {k: (m, open(os.path.join(HERE, fn), "rb").read()) for k, (m, fn) in ADD.items()}
    ino = max(fields(h)[0] for h, _, _ in ents) + 1
    res = b""
    for h, name, data in ents:
        f = fields(h)
        if name in add:
            mode, data = add.pop(name)
            f[1] = mode
            print("zamijenjeno:", name, len(data), "B")
        res += entry(f, name, data)
    tmpl = fields(ents[0][0])  # uid/gid/mtime/dev kao u izvorniku (root)
    for name, (mode, data) in add.items():
        f = list(tmpl)
        f[0], f[1], f[4] = ino, mode, 1
        ino += 1
        res += entry(f, name, data)
        print("dodano:     ", name, len(data), "B")
    res += entry(fields(trailer), "TRAILER!!!", b"")
    res += b"\0" * ((512 - len(res) % 512) % 512)
    open(out, "wb").write(res)
    print(out, len(res), "B")


if __name__ == "__main__":
    main()
