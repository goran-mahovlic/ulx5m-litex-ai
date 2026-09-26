#!/usr/bin/env python3
# USB 1.1 host engine (TASK-5051): runs the same cocotb tests (sim/usb_pnru/test_usb_pnru.py) against
#   ref48  - PNRU's Verilog (usb11/phy.v, sie.v, regs.v), fetched here at the pinned commit, 48 MHz,
#   mig48  - the Migen port gateware/usb_pnru.py, usb clock 48 MHz  (clock options a and c),
#   mig125 - the same port, usb clock 125 MHz = gtx0              (clock option b),
#   mig48s, mig125s - the same in the SoC configuration (with_detect=False, with_events=False),
# with Icarus Verilog. The Migen DUTs are converted to Verilog with a LiteX CSR bank in front.
#
# Run:  source tools/sbc_env.sh && python3 sim/tb_usb_pnru.py [ref48 mig48 mig125]
# Out:  sim/usb_pnru/build/<config>/results.json (bit rate, jitter, SOF period ...), exit 1 on any failure.
#
# SPDX-License-Identifier: BSD-2-Clause

import json
import os
import subprocess
import sys

HERE  = os.path.dirname(os.path.abspath(__file__))
TBDIR = os.path.join(HERE, "usb_pnru")
BUILD = os.path.join(TBDIR, "build")
sys.path.insert(0, os.path.join(HERE, "..", "gateware"))

PNRU_URL    = "https://github.com/emard/usb_host"
PNRU_COMMIT = "47408bb"
SYS_FREQ    = 20e6
# name: (kind, usb clock, small = the SoC configuration: no connect detect, no EventManager)
CONFIGS     = {"ref48": ("ref", 48e6, False), "mig48": ("mig", 48e6, False), "mig125": ("mig", 125e6, False),
               "mig48s": ("mig", 48e6, True), "mig125s": ("mig", 125e6, True)}


def fetch_pnru():
    d = os.path.join(BUILD, "pnru_usb_host")
    if not os.path.isdir(d):
        os.makedirs(BUILD, exist_ok=True)
        subprocess.check_call(["git", "clone", "-q", PNRU_URL, d])
    subprocess.check_call(["git", "-C", d, "checkout", "-q", PNRU_COMMIT])
    return [os.path.join(d, "usb11", f) for f in ("phy.v", "sie.v", "regs.v")]


def gen_migen(usb_freq, outdir, small):
    from migen import Module, Signal, ClockDomain
    from migen.fhdl.verilog import convert
    from litex.soc.interconnect.csr_bus import CSRBankArray
    from usb_pnru import USBHostPNRU

    class DUT(Module):
        def __init__(self):
            self.clock_domains.cd_sys = ClockDomain("sys")
            self.clock_domains.cd_usb = ClockDomain("usb")
            self.submodules.usb_pnru = u = USBHostPNRU(None, usb_freq, SYS_FREQ, detect_bits=8,
                                                       with_detect=not small, with_events=not small)
            self.submodules.csrbankarray = banks = CSRBankArray(
                self, lambda name, memory: 0 if name == "usb_pnru" else None, data_width=32, address_width=14)
            bank = banks.get_rmaps()[0]
            self.ios = {}
            for n, w, sig in [("csr_adr", 14, bank.bus.adr), ("csr_we", 1, bank.bus.we),
                              ("csr_dat_w", 32, bank.bus.dat_w), ("csr_re", 1, bank.bus.re)]:
                s = Signal(w, name=n)
                self.comb += sig.eq(s)
                self.ios[n] = s
            for n, w, sig in [("csr_dat_r", 32, bank.bus.dat_r), ("irq", 1, u.ev.irq if not small else 0),
                              ("usb_dp_o", 1, u.engine.phy.dp_o), ("usb_dn_o", 1, u.engine.phy.dn_o),
                              ("usb_oe", 1, u.engine.phy.oe)]:
                s = Signal(w, name=n)
                self.comb += s.eq(sig)
                self.ios[n] = s
            for n, sig in [("usb_dp_i", u.engine.phy.dp_i), ("usb_dn_i", u.engine.phy.dn_i)]:
                s = Signal(name=n)
                self.comb += sig.eq(s)
                self.ios[n] = s
            self.comb += u.engine.phy.dif_i.eq(self.ios["usb_dp_i"])
            self.csr_map = {c.name.replace("usb_pnru_", ""): i for i, c in enumerate(bank.simple_csrs)}

    dut = DUT()
    ios = set(dut.ios.values()) | {dut.cd_sys.clk, dut.cd_sys.rst, dut.cd_usb.clk, dut.cd_usb.rst}
    convert(dut, ios=ios, name="usb_pnru_dut").write(os.path.join(outdir, "usb_pnru_dut.v"))
    json.dump(dut.csr_map, open(os.path.join(outdir, "csr_map.json"), "w"), indent=1)


def run(cfg):
    from cocotb_tools.runner import get_runner
    kind, freq, small = CONFIGS[cfg]
    out = os.path.join(BUILD, cfg)
    os.makedirs(out, exist_ok=True)
    res = os.path.join(out, "results.json")
    if os.path.exists(res):
        os.remove(res)
    if kind == "ref":
        sources, top = fetch_pnru() + [os.path.join(TBDIR, "tb_ref_top.v")], "tb_ref_top"
        env = {}
        build_args = ["-gno-strict-declaration"]    # PNRU uses nets before their declaration
    else:
        gen_migen(freq, out, small)
        sources, top = [os.path.join(out, "usb_pnru_dut.v"), os.path.join(TBDIR, "tb_mig_top.v")], "tb_mig_top"
        env = {"CSR_MAP": os.path.join(out, "csr_map.json")}
        build_args = []
    env.update({"DUT_KIND": kind, "USB_FREQ": str(freq), "RESULTS_JSON": res, "DUT_SMALL": "1" if small else "0"})
    r = get_runner("icarus")
    r.build(sources=sources, hdl_toplevel=top, build_dir=out, always=True, timescale=("1ns", "1ps"),
            build_args=build_args)
    xml = r.test(hdl_toplevel=top, test_module="test_usb_pnru", test_dir=TBDIR, build_dir=out,
                 extra_env=env, results_xml=os.path.join(out, "results.xml"))
    from cocotb_tools.runner import get_results
    ntests, nfail = get_results(xml)
    return ntests, nfail, (json.load(open(res)) if os.path.exists(res) else {})


def main():
    cfgs = sys.argv[1:] or list(CONFIGS)
    summary, bad = {}, 0
    for c in cfgs:
        n, f, res = run(c)
        summary[c] = {"tests": n, "fail": f, **res}
        bad += f
    print(json.dumps(summary, indent=1))
    for c, s in summary.items():
        print("%-7s %d tests, %d fail" % (c, s["tests"], s["fail"]))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
