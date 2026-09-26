#!/usr/bin/env python3
"""TASK-5048 (instruction #69/#70): gateware/mdio_core.py (Migen) against the former gateware/verilog/mdio_core.v.

Both run side by side in Icarus Verilog, each with its own KSZ9031 MDIO slave model (PHY ID 0x0022/0x1622 at one
PHYAD, register file reset by RESET_N, writes stored, reads answered after TA). Every sys clock the testbench
compares MDC, the resolved MDIO line, the MDIO output enable and data, RESET_N and the 256-bit snap bus. RXC runs
on an unrelated period and RX_CTL toggles pseudo-randomly, so rfreq/frames and their gray-code crossing are
compared too. The old Verilog is taken from git (it is no longer in the tree).

Run: source tools/sbc_env.sh && python3 sim/tb_mdio_core_equiv.py [--rev <git rev>]
     -> one line per parameter set, "ALL EQUAL" at the end (exit 0)
"""
import argparse, os, re, subprocess, sys, tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "gateware"))
from migen import *
from migen.fhdl.verilog import convert
from mdio_core import MDIOCore

OLD_PATH = "ulx5m-gs-linux-sbc/gateware/verilog/mdio_core.v"
OSS = os.environ.get("OSS_CAD_SUITE", "/home/klaudio/app/raid/tools/oss-cad-suite-20260923")

# name, WRITE_AFTER, REG9, REG4, REG0, PHYAD of the model, passes to run
CASES = [
    ("soc (grec_3)", 0, 0x0200, 0x0001, 0x1200, 3, 2),
    ("write_after=2", 2, 0x0000, 0x0101, 0x1200, 0, 3),
]

PHY_MODEL = r"""
module phy_model #(parameter MYAD = 3) (input mdc, inout mdio, input rst_n);
  reg [15:0] regs [0:31];
  integer i;
  task defaults; begin
    for (i = 0; i < 32; i = i + 1) regs[i] = 16'h0000;
    regs[0] = 16'h1140; regs[1] = 16'h7949; regs[2] = 16'h0022; regs[3] = 16'h1622;
    regs[4] = 16'h01E1; regs[9] = 16'h0300; regs[10] = 16'h3C00; regs[31] = 16'h0348;
  end endtask
  initial defaults;
  always @(negedge rst_n) defaults;
  reg [45:0] sh = 0; reg [45:0] nsh; reg active = 0; reg [4:0] k = 0; reg [4:0] kk;
  reg [1:0] op; reg [4:0] pa, rg; reg drv_en = 0, drv_val = 0;
  assign mdio = drv_en ? drv_val : 1'bz;
  always @(posedge mdc) begin
    nsh = {sh[44:0], mdio}; sh <= nsh;
    if (!active) begin
      if (nsh[45:14] == 32'hFFFFFFFF && nsh[13:12] == 2'b01) begin
        active <= 1; k <= 0; op <= nsh[11:10]; pa <= nsh[9:5]; rg <= nsh[4:0]; drv_en <= 0;
      end
    end else begin
      kk = k + 1; k <= kk;
      if (op == 2'b10 && pa == MYAD) begin
        if (kk == 1) begin drv_en <= 1; drv_val <= 0; end                         // TA: second bit 0
        else if (kk >= 2 && kk <= 17) begin drv_en <= 1; drv_val <= regs[rg][17 - kk]; end
        else drv_en <= 0;
      end
      if (kk == 18) begin
        active <= 0; drv_en <= 0;
        if (op == 2'b01 && pa == MYAD) regs[rg] <= nsh[15:0];
      end
    end
  end
endmodule
"""

TB = r"""
`timescale 1ns/1ps
module tb;
  reg clk = 0, rxc = 0, rx_ctl = 0; reg [15:0] lfsr = 16'hACE1;
  always #25 clk = ~clk;          // 20 MHz
  always #37.3 rxc = ~rxc;        // unrelated to clk (the real RXC is 125 MHz; the ratio does not matter here)
  always @(posedge rxc) begin lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]}; rx_ctl <= lfsr[0] & lfsr[3]; end
  wire mdc_o, rst_o, mdc_n, rst_n; tri1 mdio_o, mdio_n; wire [255:0] snap_o, snap_n;
  mdio_core #(.WRITE_AFTER(%(wa)d), .REG9(16'h%(r9)04x), .REG4(16'h%(r4)04x), .REG0(16'h%(r0)04x)) old (
    .clk25(clk), .uart_a(), .uart_b(), .mdc(mdc_o), .mdio(mdio_o), .rst_n(rst_o), .rxc(rxc), .rx_ctl(rx_ctl),
    .snap_bus(snap_o), .dbg(64'd0));
  mdio_new nw (%(newports)s);
  phy_model #(%(ad)d) p_o (mdc_o, mdio_o, rst_o);
  phy_model #(%(ad)d) p_n (mdc_n, mdio_n, rst_n);
  integer cyc = 0, mism = 0, mdc_edges = 0, rd_ok = 0; reg mdc_d = 0; reg rst_seen = 0;
  always @(negedge clk) begin
    cyc = cyc + 1;
    if ({mdc_o, rst_o, mdio_o, old.moe, old.mdo, snap_o} !== {mdc_n, rst_n, mdio_n, nw.%(moe)s, nw.%(mdo)s, snap_n}) begin
      mism = mism + 1;
      if (mism <= 5) $display("MISMATCH cyc=%%0d mdc %%b/%%b rst %%b/%%b mdio %%b/%%b moe %%b/%%b snap %%h / %%h", cyc,
        mdc_o, mdc_n, rst_o, rst_n, mdio_o, mdio_n, old.moe, nw.%(moe)s, snap_o[255:80], snap_n[255:80]);
    end
    if (mdc_o && !mdc_d) mdc_edges = mdc_edges + 1;
    mdc_d = mdc_o;
    if (rst_o) rst_seen = 1;
    if (cyc %% 2000000 == 0) $display("PROGRESS cyc=%%0d mism=%%0d passes=%%0d", cyc, mism, snap_o[255:248]);
    if (snap_o[255:248] == %(passes)d) begin
      $display("RESULT cycles=%%0d mismatches=%%0d mdc_edges=%%0d rst_n_high=%%0d passes=%%0d idm=%%02h wrote=%%0d addr=%%0d r0=%%04h r1=%%04h r4=%%04h r5=%%04h r9=%%04h ra=%%04h rf=%%04h rfreq=%%06h frames=%%04h",
        cyc, mism, mdc_edges, rst_seen, snap_o[255:248], snap_o[247:240], snap_o[239], snap_o[234:232],
        snap_o[231:216], snap_o[215:200], snap_o[199:184], snap_o[183:168], snap_o[167:152], snap_o[151:136],
        snap_o[135:120], snap_o[119:96], snap_o[95:80]);
      $finish;
    end
  end
endmodule
"""


def new_verilog(wa, r9, r4, r0):
    class Pads:
        def __init__(self):
            self.mdc, self.mdio, self.rst_n = Signal(name="pads_mdc"), Signal(name="pads_mdio"), Signal(name="pads_rst_n")
    pads, rx_ctl = Pads(), Signal(name="rx_ctl")
    m = MDIOCore(pads, write_after=wa, reg9=r9, reg4=r4, reg0=r0, rxc_domain="grx", rx_ctl=rx_ctl)
    m.clock_domains.cd_sys = ClockDomain("sys")
    m.clock_domains.cd_grx = ClockDomain("grx")
    snap = Signal(256, name="snap")
    m.comb += snap.eq(m.snap)
    ios = {pads.mdc, pads.mdio, pads.rst_n, rx_ctl, snap, m.cd_sys.clk, m.cd_sys.rst, m.cd_grx.clk, m.cd_grx.rst}
    return str(convert(m, ios=ios, name="mdio_new"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev", default="251bcb7", help="git revision that still has %s" % OLD_PATH)
    ap.add_argument("--mutate", action="store_true", help="negative control: new module gets REG4 ^ 0x0400 (must differ)")
    args = ap.parse_args()
    old = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (args.rev, OLD_PATH)], check=True,
                         capture_output=True, text=True).stdout
    fails = 0
    with tempfile.TemporaryDirectory(dir=os.path.expanduser("~/.tmp")) as d:
        for name, wa, r9, r4, r0, ad, passes in CASES:
            v = new_verilog(wa, r9, r4 ^ (0x0400 if args.mutate else 0), r0)
            ports = re.search(r"module mdio_new\((.*?)\);", v, re.S).group(1)
            conn = {"sys_clk": "clk", "sys_rst": "1'b0", "grx_clk": "rxc", "grx_rst": "1'b0", "pads_mdc": "mdc_n",
                    "pads_mdio": "mdio_n", "pads_rst_n": "rst_n", "rx_ctl": "rx_ctl", "snap": "snap_n"}
            names = [p.split()[-1] for p in ports.replace("\n", " ").split(",") if p.strip()]
            newports = ", ".join(".%s(%s)" % (n, conn[n]) for n in names)
            moe, mdo = (re.search(r"reg\s+(\w*%s)\b" % n, v).group(1) for n in ("moe", "mdo"))
            files = {"old.v": old, "new.v": v, "phy.v": PHY_MODEL,
                     "tb.v": TB % dict(wa=wa, r9=r9, r4=r4, r0=r0, ad=ad, passes=passes, newports=newports,
                                       moe=moe, mdo=mdo)}
            for f, s in files.items():
                open(os.path.join(d, f), "w").write(s)
            env = dict(os.environ, PATH=os.path.join(OSS, "bin") + ":" + os.environ["PATH"])
            subprocess.run(["iverilog", "-g2012", "-o", "sim.vvp", "tb.v", "old.v", "new.v", "phy.v"], cwd=d,
                           check=True, env=env)
            out = subprocess.run(["vvp", "-n", "sim.vvp"], cwd=d, capture_output=True, text=True, env=env).stdout
            res = [l for l in out.splitlines() if l.startswith(("RESULT", "MISMATCH", "PROGRESS"))]
            print("== %s: WRITE_AFTER=%d REG9=%04x REG4=%04x REG0=%04x PHYAD=%d" % (name, wa, r9, r4, r0, ad))
            print("\n".join(res) if res else out[-2000:])
            m = re.search(r"RESULT .*mismatches=(\d+)", out)
            ok = m and m.group(1) == "0" and "rst_n_high=1" in out
            print("%s %s" % ("EQUAL" if ok else "DIFFERENT", name))
            fails += not ok
    print("ALL EQUAL" if not fails else "%d DIFFERENT" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
