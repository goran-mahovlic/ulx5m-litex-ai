#!/usr/bin/env python3
"""Put cells whose name ends in .ub / .ul (and LUTs that only feed them) on die 1B, the rest on 1A (TASK-5092)."""
import collections, json, sys
j = json.load(open(sys.argv[1])); m = j["modules"]["top"]; cells = m["cells"]
skip = {"CC_IBUF", "CC_OBUF", "CC_BUFG", "CC_USR_RSTN"}
sinks = collections.defaultdict(list)
for n, c in cells.items():
    for p, bits in c["connections"].items():
        if c["port_directions"].get(p) != "output":
            for b in bits:
                if isinstance(b, int): sinks[b].append(n)
die = {n: ("1B" if n.endswith((".ub", ".ul")) else "1A") for n, c in cells.items() if c["type"] not in skip}
changed = True
while changed:
    changed = False
    for n, c in cells.items():
        if die.get(n) != "1A" or c["type"] == "CC_DFF": continue
        outs = [b for p, bits in c["connections"].items() if c["port_directions"].get(p) == "output" for b in bits if isinstance(b, int)]
        us = [u for b in outs for u in sinks[b]]
        if us and all(die.get(u) == "1B" for u in us): die[n] = "1B"; changed = True
for n, d in die.items(): cells[n]["attributes"]["GATEMATE_DIE"] = d
json.dump(j, open(sys.argv[2], "w"))
print(collections.Counter((d, cells[n]["type"]) for n, d in die.items() if d == "1B"))
