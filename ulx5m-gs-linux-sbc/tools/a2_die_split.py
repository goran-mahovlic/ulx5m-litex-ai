#!/usr/bin/env python3
"""Split a synthesized GateMate netlist between the two dies of a CCGM1A2 (TASK-5092).

On the CCGM1A2 (A2) the RGMII / USB balls EA*/EB* are bonded only to die 1B, while SDRAM, UART, DVI and
clk25 sit on die 1A. With `--vopt force_die=1A` every register of the 125 MHz RGMII domains lands on 1A,
so the IOSEL (1B, clocked by the mirrored `grx_clk$die1` / `gtx0_clk$die1`) -> CPE (1A) path crosses the die
inside one 8 ns cycle (12.2 ns measured) and nextpnr does not check it (different clock nets).

This tool writes the yosys JSON back with a `GATEMATE_DIE` attribute on every placeable cell:
  1B  = registers and block RAMs clocked by one of --clk (the fast PHY domains), plus the combinational
        cells whose every sink is already on 1B (fixpoint over the backward cone);
  1A  = everything else (CPU, SDRAM, video, USB, sys-side of the PHY).
IO buffers, IDDR/ODDR, PLL, BUFG, USR_RSTN, CFG_CTRL are left alone (the packer fixes them to their pad/die).
The clock crossing then happens only in the sys domain (20 MHz) through the PHY's frame BRAMs and MultiRegs.

With --from-io only the fast-clock registers connected to the IDDR/ODDR cells on nets matching --seed-net go to
1B (on ULX5M-GS the DVI serializer shares gtx0 and has its own ODDRs on die 1A).

Usage: a2_die_split.py in.json out.json [--clk grx_clk --clk gtx0_clk ...] [--from-io [--seed-net eth_]] [--top NAME]
"""
import argparse
import collections
import json
import re
import sys

SKIP_TYPES = {
    "CC_IBUF", "CC_OBUF", "CC_TOBUF", "CC_IOBUF", "CC_LVDS_IBUF", "CC_LVDS_OBUF", "CC_LVDS_TOBUF",
    "CC_LVDS_IOBUF", "CC_IDDR", "CC_ODDR", "CC_PLL", "CC_PLL_ADV", "CC_BUFG", "CC_USR_RSTN", "CC_CFG_CTRL",
    "CC_SERDES",
}
RAM_TYPES = {"CC_BRAM_20K", "CC_BRAM_40K", "CC_FIFO_40K"}
CLK_PORTS = {"CLK", "CLKA", "CLKB", "A_CLK", "B_CLK", "CLKW", "CLKR"}


def split(mod, clk_bits, fast_die="1B", slow_die="1A", from_io=False, max_fanout=64, seed_net=r"eth_"):
    cells = mod["cells"]
    drivers, sinks = {}, collections.defaultdict(list)
    for name, c in cells.items():
        dirs = c.get("port_directions", {})
        for port, bits in c["connections"].items():
            for b in bits:
                if not isinstance(b, int):
                    continue
                if dirs.get(port) == "output":
                    drivers[b] = name
                else:
                    sinks[b].append(name)

    clocked = set()
    for name, c in cells.items():
        t = c["type"]
        if t == "CC_DFF" or t in RAM_TYPES:
            for port, bits in c["connections"].items():
                if port in CLK_PORTS and any(b in clk_bits for b in bits if isinstance(b, int)):
                    clocked.add(name)

    if not from_io:
        fast = set(clocked)
    else:
        # Only the part of the fast domains that is connected to the DDR IO cells: another block may share a fast
        # clock (on ULX5M-GS the DVI path runs in gtx0) and must stay on the slow die. Walk the netlist from the
        # IDDR/ODDR cells through fast registers/RAMs and combinational cells, never through a clock net or a net
        # with more than max_fanout sinks (resets, enables).
        comb_types = lambda t: t not in SKIP_TYPES and t != "CC_DFF" and t not in RAM_TYPES
        netname = collections.defaultdict(list)
        for nn, v in mod.get("netnames", {}).items():
            for b in v["bits"]:
                if isinstance(b, int):
                    netname[b].append(nn)
        seed_re = re.compile(seed_net)
        seeds = [n for n, c in cells.items() if c["type"] in ("CC_IDDR", "CC_ODDR")
                 and any(seed_re.search(nn) for p, bits in c["connections"].items() if p not in CLK_PORTS
                         for b in bits if isinstance(b, int) for nn in netname[b])]
        fast, todo = set(), list(seeds)
        seen = set(seeds)
        while todo:
            n = todo.pop()
            for port, bits in cells[n]["connections"].items():
                if port in CLK_PORTS:
                    continue
                for b in bits:
                    if not isinstance(b, int) or b in clk_bits:
                        continue
                    peers = sinks.get(b, []) + ([drivers[b]] if b in drivers else [])
                    if len(peers) > max_fanout:
                        continue
                    for q in peers:
                        if q in seen:
                            continue
                        t = cells[q]["type"]
                        if q in clocked or comb_types(t):
                            # walk through combinational cells, but only registers/RAMs are placed here;
                            # combinational cells follow their sinks in the backward-cone pass below
                            seen.add(q)
                            todo.append(q)
                            if q in clocked:
                                fast.add(q)

    # Backward cone: a combinational cell goes to the fast die if all its sinks are there.
    comb = {n for n, c in cells.items()
            if c["type"] not in SKIP_TYPES and c["type"] != "CC_DFF" and c["type"] not in RAM_TYPES}
    changed = True
    while changed:
        changed = False
        for n in comb - fast:
            c = cells[n]
            outs = [b for p, bits in c["connections"].items()
                    if c.get("port_directions", {}).get(p) == "output" for b in bits if isinstance(b, int)]
            users = [u for b in outs for u in sinks.get(b, [])]
            if users and all(u in fast for u in users):
                fast.add(n)
                changed = True

    count = collections.Counter()
    for name, c in cells.items():
        if c["type"] in SKIP_TYPES:
            continue
        die = fast_die if name in fast else slow_die
        c.setdefault("attributes", {})["GATEMATE_DIE"] = die
        count[die] += 1
    return fast, count


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--clk", action="append", default=[], help="clock net of the fast (die 1B) domain")
    ap.add_argument("--top", default=None)
    ap.add_argument("--fast-die", default="1B")
    ap.add_argument("--slow-die", default="1A")
    ap.add_argument("--from-io", action="store_true",
                    help="only the fast-clock logic connected to the IDDR/ODDR cells goes to the fast die")
    ap.add_argument("--max-fanout", type=int, default=64)
    ap.add_argument("--seed-net", default=r"eth_", help="regex: DDR cells on nets matching it seed --from-io")
    a = ap.parse_args(argv)
    clks = a.clk or ["grx_clk", "gtx0_clk"]

    j = json.load(open(a.inp))
    top = a.top or next(n for n, m in j["modules"].items() if m.get("attributes", {}).get("top"))
    mod = j["modules"][top]
    clk_bits = set()
    for n in clks:
        if n not in mod["netnames"]:
            sys.exit(f"clock net '{n}' not in module {top}")
        clk_bits.update(b for b in mod["netnames"][n]["bits"] if isinstance(b, int))
    fast, count = split(mod, clk_bits, a.fast_die, a.slow_die, a.from_io, a.max_fanout, a.seed_net)
    json.dump(j, open(a.out, "w"))
    types = collections.Counter(mod["cells"][n]["type"] for n in fast)
    print(f"{top}: {a.fast_die}={count[a.fast_die]} {a.slow_die}={count[a.slow_die]} fast types {dict(types)}")


if __name__ == "__main__":
    main()
