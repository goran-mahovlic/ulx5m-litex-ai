#!/usr/bin/env python3
"""cpio_append.py <rootfs.cpio> <out.cpio> <path-in-rootfs>=<local file> ... (TASK-5075)

Replace files in a padded initramfs without unpacking it (unpacking as non-root loses /dev/console and root
ownership): a second newc archive (uid/gid 0, mode 0755) goes right after the first TRAILER!!!, inside the zero
padding, and the kernel unpacks it over the first one. The output keeps the input size (12 MiB initrd window of the
DVI DTS); it fails if the padding is too small.
"""
import os
import sys


def newc(name, data, mode, ino):
    name_b = name.encode() + b"\0"
    hdr = "070701" + "".join("%08x" % v for v in (ino, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name_b), 0))
    out = hdr.encode() + name_b
    out += b"\0" * (-len(out) % 4) + data
    return out + b"\0" * (-len(out) % 4)


def build(files):
    arc = b""
    for i, (name, data) in enumerate(files):
        arc += newc(name, data, 0o100755, 0x7500 + i)
    arc += newc("TRAILER!!!", b"", 0, 0)
    return arc + b"\0" * (-len(arc) % 512)


def archive_end(img):
    """offset after the TRAILER!!! entry of the first archive (walks the headers: the string also occurs in binaries)"""
    p = 0
    while img[p:p + 6] == b"070701":
        size, namesize = int(img[p + 54:p + 62], 16), int(img[p + 94:p + 102], 16)
        name = img[p + 110:p + 110 + namesize - 1]
        p = (((p + 110 + namesize + 3) & ~3) + size + 3) & ~3
        if name == b"TRAILER!!!":
            return p
    raise SystemExit("no TRAILER!!! entry (not a newc archive?)")


def append(img, files):
    end = (archive_end(img) + 511) & ~511                      # start the second archive on a 512-byte boundary
    if img[end:].strip(b"\0"):
        raise SystemExit("data after the first archive (already patched?)")
    arc = build(files)
    if end + len(arc) > len(img):
        raise SystemExit("padding too small: need %d bytes, have %d" % (len(arc), len(img) - end))
    return img[:end] + arc + img[end + len(arc):]


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    img = open(sys.argv[1], "rb").read()
    files = []
    for a in sys.argv[3:]:
        dst, src = a.split("=", 1)
        files.append((dst.lstrip("/"), open(src, "rb").read()))
    out = append(img, files)
    open(sys.argv[2], "wb").write(out)
    print("%s: %d bytes, %d file(s) appended" % (sys.argv[2], len(out), len(files)))
