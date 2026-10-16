#!/usr/bin/env python3
"""pr_clocks.py <p_r out dir> <prefix> — p_r final STA: Fmax per clock, clock named via yosys netlist.

p_r names clocks by an internal component number (e.g. "CLK 8716 (8716/3)"). We take the start component of the
longest path, look its name up in <prefix>.refcomp, find the FF that this cell drives in the -vlog netlist and print
that FF's CLK net (u.tclk / u.rclk / u.clk_i). Output: one line per clock, the last STA block of pr.log only.
"""
import re, sys, os

d, pre = sys.argv[1], sys.argv[2]
log = open(os.path.join(d, 'pr.log'), errors='replace').read()
last = log[log.rfind('Static Timing Analysis'):]
blocks = re.findall(r'Longest Path from Q of Component (\d+)_\d+ to D-Input of Component (\S+) Delay: (\d+) ps\n'
                     r'Maximum Clock Frequency on CLK (\d+) \((\S+)\):\s+([\d.]+) MHz', last)
comp = {}
for line in open(os.path.join(d, pre + '.refcomp'), errors='replace'):
    m = re.match(r'\s*\(\d+\)\s+(\d+)\s+CC_\w+\s+\S+\s+(\S+)', line)
    if m: comp[m.group(1)] = m.group(2)
net = open(os.path.join(d, 's.v')).read()
cells = {}
for t, n, b in re.findall(r'\n  (CC_\w+)\s+(?:#\((?:.|\n)*?\)\s*)?(\\?\S+)\s*\(\n((?:.|\n)*?)\n  \);', net):
    cells[n.lstrip('\\')] = (t, dict(re.findall(r'\.(\w+)\((.*?)\)\s*,?\n?', b)))
dffs = [(n, p) for n, (t, p) in cells.items() if t == 'CC_DFF']

def clk_of(cname):
    c = cells.get(cname.lstrip('\\'))
    if not c: return '?'
    t, p = c
    if t == 'CC_DFF': return p.get('CLK', '?').strip()
    outs = {p[k].strip() for k in ('O', 'S', 'CO') if k in p}   # LUT/MX: O, ADDF: S/CO
    for n, q in dffs:
        if q.get('D', '').strip() in outs: return q.get('CLK', '?').strip()
    return '?'

for src, dst, dly, ck, edge, f in blocks:
    print(f"CLK {ck} ({edge}) = {clk_of(comp.get(src, '?')):12s} Fmax {f} MHz  longest {int(dly)/1000:.2f} ns")
