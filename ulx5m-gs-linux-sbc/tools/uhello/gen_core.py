#!/usr/bin/env python3
"""Regenerate mdio_core.v (beacon core) from mdioprobe.v (TASK-4999)."""
import re
src = open("mdioprobe.v").read()
hdr = re.search(r"module top\(.*?\);", src, re.S).group(0)
new_hdr = hdr.replace("module top(", "module mdio_core(").replace(");", ",\n           output [255:0] snap_bus);")
core = src.replace(hdr, new_hdr, 1)
core = core.replace("endmodule", "  // bus for the Ethernet beacon (TASK-4999): quasi-static, re-sampled per frame\n"
    "  assign snap_bus = {passes, idm, {wrote, 4'b0, addr}, r0, r1, r4, r5, r9, ra, rf, rfreq, frames, 80'h0};\nendmodule")
assert "module mdio_core" in core and "snap_bus" in core
open("mdio_core.v", "w").write(core)
