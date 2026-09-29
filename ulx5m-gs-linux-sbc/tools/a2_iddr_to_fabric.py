#!/usr/bin/env python3
"""Replace CC_IDDR cells by two fabric CC_DFFs (posedge Q0, negedge Q1) in a yosys JSON (TASK-5092).

Why: on a CCGM1A2 with `--vopt force_die=1A` the RGMII balls sit on die 1B. A CC_IDDR is packed into the IOSEL of the
pad, so it is clocked by the mirrored `grx_clk$die1` on die 1B, and its outputs must cross the die to the RX logic on
1A (clocked by `grx_clk`) within one 8 ns cycle: 12.2 ns measured, and nextpnr does not check the path (the two clock
nets count as unrelated). With plain fabric flip-flops the data and RXC both cross the die (RXC through CC_BUFG ->
GLBOUT USR_GLB), i.e. source-synchronously, and are sampled on 1A. The IBUF has no FF_IBF, so nextpnr does not
merge the flip-flops back into the IOSEL. Behaviour is the same as CC_IDDR in cells_sim.v (Q0 at the rising edge,
Q1 at the falling edge).

Usage: a2_iddr_to_fabric.py in.json out.json [--net-re eth_rx] [--top NAME]
"""
import argparse
import json
import re
import sys


def dff(d, clk, q, inv):
    return {
        "hide_name": 0, "type": "CC_DFF",
        "parameters": {"CLK_INV": "1" if inv else "0", "EN_INV": "0", "INIT": "x", "SR_INV": "0", "SR_VAL": "0"},
        "attributes": {"keep": "00000000000000000000000000000001"},
        "port_directions": {"CLK": "input", "D": "input", "EN": "input", "Q": "output", "SR": "input"},
        "connections": {"CLK": clk, "D": d, "EN": ["1"], "SR": ["0"], "Q": q},
    }


def convert(mod, net_re):
    names = {}
    for n, v in mod.get("netnames", {}).items():
        for b in v["bits"]:
            if isinstance(b, int):
                names.setdefault(b, []).append(n)
    rx = re.compile(net_re)
    done = []
    for name in list(mod["cells"]):
        c = mod["cells"][name]
        if c["type"] != "CC_IDDR":
            continue
        d = c["connections"]["D"]
        if not any(rx.search(n) for b in d if isinstance(b, int) for n in names.get(b, [])):
            continue
        inv = str(c["parameters"].get("CLK_INV", "0")).strip("0") != ""
        clk = c["connections"]["CLK"]
        del mod["cells"][name]
        mod["cells"][name + "$q0"] = dff(d, clk, c["connections"]["Q0"], inv)
        mod["cells"][name + "$q1"] = dff(d, clk, c["connections"]["Q1"], not inv)
        done.append(name)
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--net-re", default=r"eth_rx", help="convert only IDDRs whose D net name matches")
    ap.add_argument("--top", default=None)
    a = ap.parse_args(argv)
    j = json.load(open(a.inp))
    top = a.top or next(n for n, m in j["modules"].items() if m.get("attributes", {}).get("top"))
    done = convert(j["modules"][top], a.net_re)
    if not done:
        sys.exit("no CC_IDDR matched")
    json.dump(j, open(a.out, "w"))
    print(f"{top}: {len(done)} CC_IDDR -> 2 x CC_DFF: {', '.join(done)}")


if __name__ == "__main__":
    main()
