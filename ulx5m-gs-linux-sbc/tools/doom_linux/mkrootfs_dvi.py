#!/usr/bin/env python3
"""mkrootfs_dvi.py <in.cpio> <out.cpio> - REGOČ rootfs (mkrootfs.py: eth0 .213, banner) + DOOM (TASK-5040):
/usr/bin/doom, /usr/bin/csrpeek, /usr/share/doom/doom1.wad (shareware v1.9, sha1 5b2e249b...).
~8,4 MB > 8 MB initrd of rv32.dtb, so the DVI DTB (mkdts.py) reserves 0x41000000-0x41a00000."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rootfs"))
import mkrootfs
here = os.path.dirname(os.path.abspath(__file__))
wad = os.environ.get("WAD", os.path.expanduser("~/.tmp/t5040/doom1.wad"))
# a directory entry must precede the files in it (initramfs does not create parents)
empty = os.path.join(here, ".empty")
open(empty, "wb").close()
mkrootfs.ADD.update({
    "usr/share/doom":            (0o040755, empty),
    "usr/bin/doom":              (0o100755, os.path.join(here, "doom")),
    "usr/bin/csrpeek":           (0o100755, os.path.join(here, "csrpeek")),
    "usr/share/doom/doom1.wad":  (0o100644, wad),
    # TASK-5047: USB keyboard daemon + getty on tty1 (tools/usbhidd)
    "usr/bin/usbhidd":           (0o100755, os.path.join(here, "usbhidd")),
    "etc/init.d/S90usbhidd":     (0o100755, os.path.join(here, "..", "usbhidd", "S90usbhidd")),
})
mkrootfs.main()
