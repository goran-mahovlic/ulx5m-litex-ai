#!/usr/bin/env python3
"""TASK-5033: target_soc.py --boot {none,serial,netboot,sdcard} -> BIOS boot defines in the generated soc.h.

Generates each SoC without place & route (target_soc.py without --build: gateware + BIOS only) and checks
the header the BIOS is compiled against. Run: tools/soc_build.sh environment, then
    python3 sim/test_boot_option.py [outdir]
"""
import os, re, subprocess, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT  = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.tmp/t5033/boot_opt")

# mode -> (defines that must be present, defines that must be absent)
EXPECT = {
    "none":    ({"CONFIG_BIOS_NO_BOOT"}, {"CSR_ETHMAC_BASE"}),
    "serial":  ({"SDCARD_BOOT_DISABLE", "NET_BOOT_DISABLE"}, {"CONFIG_BIOS_NO_BOOT"}),
    "sdcard":  ({"SDCARD_BOOT_PRIORITY", "NET_BOOT_DISABLE"}, {"CONFIG_BIOS_NO_BOOT", "SDCARD_BOOT_DISABLE"}),
    "netboot": ({"CSR_ETHMAC_BASE", "NET_BOOT_PRIORITY", "SDCARD_BOOT_DISABLE", "ETH_PHY_NO_RESET",
                 "LOCALIP4", "REMOTEIP4", "MACADDR6", "CONFIG_BIOS_PRINT_IDENT"},
                {"CONFIG_BIOS_NO_BOOT", "NET_BOOT_DISABLE"}),
}
# extra cases: (name, extra args, present, absent) - --eth-mode mac: CPU-only MAC (Linux SoC), no hardware stack
EXTRA = [
    ("netboot_mac", ["--eth-mode", "mac"], {"CSR_ETHMAC_BASE", "NET_BOOT_PRIORITY", "LOCALIP4", "REMOTEIP4"},
     {"CONFIG_BIOS_NO_BOOT"}),
]
# BIOS banner (SoC ident) must name both addresses when the CPU has its own port (uputa #32)
IDENT = {"netboot": ["HW ping/Etherbone 192.168.10.212", "10:e2:d5:00:00:00", "CPU/TFTP 192.168.10.213",
                     "10:e2:d5:00:00:01"],
         "none":    ["HW ping/Etherbone 192.168.10.212"]}
VALUES = {"netboot": {"NET_BOOT_PRIORITY": "-1", "LOCALIP4": "213", "REMOTEIP4": "14"},
          "sdcard":  {"SDCARD_BOOT_PRIORITY": "-1"}}


def defines(path):
    d = {}
    for l in open(path):
        m = re.match(r"#define\s+(\w+)(?:\s+(.*))?", l)
        if m:
            d[m.group(1)] = (m.group(2) or "").strip()
    return d


CASES = [(m, ["--boot", m], p, a) for m, (p, a) in EXPECT.items()] + \
        [(n, ["--boot", "netboot"] + x, p, a) for n, x, p, a in EXTRA]
fails = 0
for mode, extra, present, absent in CASES:
    out = os.path.join(OUT, mode)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "gateware", "target_soc.py"), "--output-dir", out,
                        "--with-gbe", "--with-sdcard"] + extra, capture_output=True, text=True)
    if r.returncode:
        print("FAIL %-8s generation exit %d: %s" % (mode, r.returncode, r.stderr.strip().splitlines()[-1:]))
        fails += 1
        continue
    d = {}
    for h in ("soc.h", "csr.h"):
        d.update(defines(os.path.join(out, "software", "include", "generated", h)))
    bad = ["missing " + k for k in sorted(present - d.keys())] + ["unexpected " + k for k in sorted(absent & d.keys())]
    if mode.endswith("_mac"):   # CPU-only MAC: the hardware stack (Etherbone, ICMP) must be gone from the RTL
        v = open(os.path.join(out, "gateware", "intergalaktik_ulx5m_gs.v")).read().lower()
        bad += ["rtl contains " + k for k in ("etherbone", "icmp") if k in v]
    bad += ["ident lacks '%s'" % k for k in IDENT.get(mode, []) if k not in d.get("CONFIG_IDENTIFIER", "")]
    bad += ["%s=%s (want %s)" % (k, d.get(k), v) for k, v in VALUES.get(mode, {}).items() if d.get(k) != v]
    print("%s %-8s %s" % ("FAIL" if bad else "PASS", mode, "; ".join(bad)))
    fails += bool(bad)
print("%d/%d PASS" % (len(CASES) - fails, len(CASES)))
sys.exit(1 if fails else 0)
