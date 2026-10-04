#!/usr/bin/env python3
"""TASK-5234: target_soc.py --sdcard {spi,native} --sd-pins j8 -> generated .ccf and CSR map (no P&R).

The SD core must sit on the J8 header pins of gateware/sd_pins.py with the FPGA pull-ups on (CMD/DAT lines, never CLK),
keep the CSR name the BIOS and Linux expect (spisdcard / sdcard), and leave the old slot pins unused.
Run in the tools/sbc_env.sh environment:  python3 sim/test_sd_gen.py [outdir]
"""
import json, os, re, subprocess, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "gateware"))
from sd_pins import SD_PINS  # noqa: E402
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.tmp/t5234/sd_gen")

J8, SLOT = SD_PINS["j8"], SD_PINS["slot"]
# case -> (args, {ccf net: (pin, pull-up)}, CSR region that must exist)
CASES = {
    "spi_j8": (["--sdcard", "spi", "--sd-pins", "j8", "--boot", "sdnet"],
               {"spisdcard_j8_clk": (J8["clk"], False), "spisdcard_j8_mosi": (J8["mosi"], True),
                "spisdcard_j8_cs_n": (J8["cs_n"], True), "spisdcard_j8_miso": (J8["miso"], True)}, "spisdcard"),
    "native_j8": (["--sdcard", "native", "--sd-pins", "j8", "--boot", "netboot"],
                  {"sdcard_j8_clk": (J8["clk"], False), "sdcard_j8_cmd": (J8["mosi"], True),
                   "sdcard_j8_data[0]": (J8["miso"], True), "sdcard_j8_data[1]": (J8["dat1"], True),
                   "sdcard_j8_data[2]": (J8["dat2"], True), "sdcard_j8_data[3]": (J8["cs_n"], True)}, "sdcard"),
}

fails = 0
for name, (extra, want, csr) in CASES.items():
    out = os.path.join(OUT, name)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "gateware", "target_soc.py"), "--output-dir", out,
                        "--with-gbe", "--cpu-type", "vexriscv_smp", "--cpu-variant", "linux"] + extra,
                       capture_output=True, text=True)
    if r.returncode:
        print("FAIL %-10s generation exit %d: %s" % (name, r.returncode, r.stderr.strip().splitlines()[-1:]))
        fails += 1
        continue
    ccf = open(os.path.join(out, "gateware", "intergalaktik_ulx5m_gs.ccf")).read()
    got = {m.group(1): (m.group(2), "PULLUP=true" in m.group(3))
           for m in re.finditer(r'Net\s+"([^"]+)"\s+Loc\s*=\s*"(IO_\w+)"([^;]*);', ccf)}
    bad = ["%s: %s (want %s)" % (k, got.get(k), v) for k, v in want.items() if got.get(k) != v]
    bad += ["slot pin %s used by %s" % (p, n) for n, (p, _) in got.items() if p in SLOT.values()]
    regions = json.load(open(os.path.join(out, "csr.json")))["csr_bases"]
    bad += [] if csr in regions else ["no CSR %s" % csr]
    print("%s %-10s %s" % ("FAIL" if bad else "PASS", name, "; ".join(bad)))
    fails += bool(bad)
print("%d/%d PASS" % (len(CASES) - fails, len(CASES)))
sys.exit(1 if fails else 0)
