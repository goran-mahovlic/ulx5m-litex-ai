#!/usr/bin/env python3
"""TASK-5555 — one 16:9 slide: GS<->M2 SerDes settings, comparison, open issues.

All numbers come from ulx5m-gs-m2-serdes/docs:
  SOAK_R1_2G5_20261017.md, CHAIN4_5G_P2_20261017.md, TOOLCHAIN_20261017.md,
  RESEARCH_SERDES_USPOREDBA_20261017.md
Rendering: Playwright Chromium -> PDF (1920x1080 px page) + PNG 1920x1080.
No opacity / rgba / gradients / shadows, so Chromium emits no SMask.
"""
import math
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
NAME = "SERDES_SLIDE_20261017"

TEAL, NAVY, INK, MUTED, RULE = "#4FA3A8", "#0b3d5c", "#16202b", "#4a5d6b", "#cfd9e1"
RED, AMBER, GREEN = "#b23a3a", "#b7791f", "#2f7d4f"

# ---------- BER chart (log axis), labels only OUTSIDE the plot area ----------
X0, W, DEC_MIN, DEC_MAX = 236, 424, -14, -9
def x(ber):
    return X0 + (math.log10(ber) - DEC_MIN) / (DEC_MAX - DEC_MIN) * W

ROW_H, TOP = 54, 10
rows = [  # label, sublabel, kind, values
    ("M2 → GS", "ours · 2.5G · 2.239e12 bits", "ci", (2.23e-11, 1.66e-11, 2.94e-11), RED),
    ("GS → M2", "ours · 2.5G · 2.239e12 bits", "ci", (8.93e-13, 1.08e-13, 3.23e-12), GREEN),
    ("Cologne Chip", "1.25G, same-chip SMA loop, 10 s", "ub", (2.4e-10,), NAVY),
]
plot_h = ROW_H * len(rows)
svg = [f'<svg width="680" height="{TOP + plot_h + 64}" viewBox="0 0 680 {TOP + plot_h + 64}" '
       f'xmlns="http://www.w3.org/2000/svg" font-family="DejaVu Sans">']
# plot frame + decade grid
svg.append(f'<rect x="{X0}" y="{TOP}" width="{W}" height="{plot_h}" fill="#f6f9fa" stroke="{RULE}"/>')
for d in range(DEC_MIN, DEC_MAX + 1):
    xx = x(10.0 ** d)
    svg.append(f'<line x1="{xx:.1f}" y1="{TOP}" x2="{xx:.1f}" y2="{TOP + plot_h}" stroke="#dfe7ec"/>')
    svg.append(f'<text x="{xx:.1f}" y="{TOP + plot_h + 20}" font-size="15" fill="{MUTED}" '
               f'text-anchor="middle">10<tspan dy="-6" font-size="11">{d}</tspan></text>')
# target line 1e-12 (label below the axis, never inside the plot)
xt = x(1e-12)
svg.append(f'<line x1="{xt:.1f}" y1="{TOP}" x2="{xt:.1f}" y2="{TOP + plot_h}" stroke="{TEAL}" '
           f'stroke-width="2.5" stroke-dasharray="7 5"/>')
svg.append(f'<text x="{xt:.1f}" y="{TOP + plot_h + 46}" font-size="15" font-weight="bold" fill="{TEAL}" '
           f'text-anchor="middle">industry target BER ≤ 10<tspan dy="-6" font-size="11">-12</tspan></text>')
for i, (lab, sub, kind, v, col) in enumerate(rows):
    cy = TOP + ROW_H * i + ROW_H / 2
    svg.append(f'<text x="{X0 - 12}" y="{cy - 3}" font-size="17" font-weight="bold" fill="{INK}" '
               f'text-anchor="end">{lab}</text>')
    svg.append(f'<text x="{X0 - 12}" y="{cy + 16}" font-size="12.5" fill="{MUTED}" text-anchor="end">{sub}</text>')
    if kind == "ci":
        b, lo, hi = v
        svg.append(f'<line x1="{x(lo):.1f}" y1="{cy}" x2="{x(hi):.1f}" y2="{cy}" stroke="{col}" stroke-width="4"/>')
        for e in (lo, hi):
            svg.append(f'<line x1="{x(e):.1f}" y1="{cy - 10}" x2="{x(e):.1f}" y2="{cy + 10}" stroke="{col}" stroke-width="3"/>')
        svg.append(f'<circle cx="{x(b):.1f}" cy="{cy}" r="8" fill="{col}" stroke="#ffffff" stroke-width="2"/>')
    else:  # upper bound only: bar from the left edge to the bound, open arrow head on the left
        ub = v[0]
        svg.append(f'<line x1="{X0 + 14}" y1="{cy}" x2="{x(ub):.1f}" y2="{cy}" stroke="{col}" '
                   f'stroke-width="4" stroke-dasharray="10 6"/>')
        svg.append(f'<polyline points="{X0 + 24},{cy - 9} {X0 + 10},{cy} {X0 + 24},{cy + 9}" fill="none" '
                   f'stroke="{col}" stroke-width="3"/>')
        svg.append(f'<line x1="{x(ub):.1f}" y1="{cy - 12}" x2="{x(ub):.1f}" y2="{cy + 12}" stroke="{col}" stroke-width="4"/>')
svg.append('</svg>')
CHART = "\n".join(svg)

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
@page {{ size: 1920px 1080px; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 1920px; height: 1080px; background: #ffffff; }}
body {{ font-family: "DejaVu Sans", sans-serif; color: {INK}; font-size: 16px; line-height: 1.34; }}
.slide {{ width: 1920px; height: 1080px; padding: 34px 48px 0 48px; position: relative; }}
header {{ display: flex; justify-content: space-between; align-items: flex-end;
          border-bottom: 4px solid {TEAL}; padding-bottom: 12px; }}
h1 {{ font-size: 38px; color: {NAVY}; letter-spacing: -0.5px; }}
.sub {{ font-size: 18px; color: {MUTED}; margin-top: 4px; }}
.tag {{ text-align: right; font-size: 15px; color: {MUTED}; }}
.tag b {{ color: {NAVY}; font-size: 22px; letter-spacing: 3px; }}
.grid {{ display: grid; grid-template-columns: 540px 1fr 510px; gap: 28px; margin-top: 20px; }}
h2 {{ font-size: 15px; letter-spacing: 2.5px; color: #ffffff; background: {NAVY}; padding: 6px 12px; margin-bottom: 12px; }}
h3 {{ font-size: 18px; color: {NAVY}; margin: 12px 0 6px; }}
h3 .pill {{ font-size: 12.5px; color: #ffffff; padding: 2px 8px; margin-left: 8px; vertical-align: 2px; }}
.ok {{ background: {GREEN}; }} .bad {{ background: {RED}; }} .warn {{ background: {AMBER}; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14.5px; }}
td, th {{ border-bottom: 1px solid {RULE}; padding: 4px 6px; text-align: left; vertical-align: top; }}
th {{ background: #eef4f7; color: {NAVY}; font-size: 13px; letter-spacing: 0.5px; }}
td.k {{ color: {MUTED}; width: 31%; }}
code, .mono {{ font-family: "DejaVu Sans Mono", monospace; font-size: 13.5px; }}
.note {{ font-size: 13.5px; color: {MUTED}; margin-top: 6px; }}
.strike {{ color: {RED}; font-weight: bold; }}
.chartbox {{ border: 1px solid {RULE}; padding: 10px 0 2px; text-align: center; }}
.vals td {{ font-size: 14px; }}
.dot {{ display: inline-block; width: 12px; height: 12px; border-radius: 6px; margin-right: 6px; vertical-align: -1px; }}
.issue {{ display: grid; grid-template-columns: 40px 1fr; gap: 12px; padding: 16px 0 17px;
          border-bottom: 1px solid {RULE}; }}
.num {{ width: 36px; height: 36px; color: #ffffff; font-weight: bold; font-size: 19px;
        display: flex; align-items: center; justify-content: center; }}
.issue h4 {{ font-size: 18.5px; color: {INK}; margin-bottom: 3px; }}
.issue p {{ font-size: 16px; color: #2b3b47; }}
.big {{ font-size: 15px; }}
.proof {{ border-left: 5px solid {TEAL}; background: #eef6f6; padding: 8px 12px; margin-top: 10px; font-size: 14.5px; }}
footer {{ position: absolute; left: 48px; right: 48px; bottom: 18px; border-top: 1px solid {RULE};
          padding-top: 8px; font-size: 12.5px; color: {MUTED}; display: flex; justify-content: space-between; }}
</style></head><body><div class="slide">
<header>
  <div><h1>GS ↔ M2 SerDes link: settings, measurements, open issues</h1>
  <div class="sub">ULX5M-GS ↔ ULX5M-M2 · GateMate CC_SERDES · board-to-board, 8b/10b + PRBS checker · status 17 Oct 2026</div></div>
  <div class="tag"><b>REGOČ</b><br>PRJ-051 · ULX5M-M2 SerDes/PCIe</div>
</header>
<div class="grid">

<!-- ===================== 1. SETTINGS ===================== -->
<section>
  <h2>1 · SETTINGS</h2>
  <h3>2.5 Gb/s — recipe R1 <span class="pill ok">LINKS</span></h3>
  <table>
    <tr><td class="k">Rate / bits</td><td>N1·N2·N3 = 1·5·5, OUTDIV 2, PROFILE 1, TX_NEG 1 · Pi bits <code>gs/m2_2g5_auto</code></td></tr>
    <tr><td class="k">CAL0</td><td>RX/TX_CALIB_OVR 1, CALIB_VAL 0 (JTAG, after load)</td></tr>
    <tr><td class="k">TX_SEL_PRE</td><td>0 (POST 5)</td></tr>
    <tr><td class="k">DFE / EQA reset</td><td>strobe 0x2B after load</td></tr>
    <tr><td class="k">TX_AMP</td><td>12</td></tr>
    <tr><td class="k">RX_EQA_CKP_OFFSET</td><td>intended 0 → readback <span class="strike">1</span>: R1 ran with 1</td></tr>
    <tr><td class="k">RX</td><td>EQA on · AFE PEAK 24, GAIN 0 · CDR CKP 0x3E</td></tr>
  </table>
  <h3>Toolchain <span class="pill ok">DEFAULT</span></h3>
  <table>
    <tr><td class="k">Suite</td><td><code>oss-cad-suite-20261016</code></td></tr>
    <tr><td class="k">Versions</td><td>yosys 0.70+145 · nextpnr-himbaechel 0.11.1-63 · gmpack v1.13-6 · openFPGALoader v1.1.1</td></tr>
    <tr><td class="k">Qualified</td><td>CC_SERDES 0/252 fields vs lab bits · CFGRST ✓ · 0 hold violations</td></tr>
    <tr><td class="k">R1 baked</td><td>gs <code>79b07795</code> / m2 <code>4a94fc99</code> (4 fields) — not yet loaded</td></tr>
  </table>
  <h3>5 Gb/s — P2 <span class="pill bad">NO LOCK</span></h3>
  <div class="note" style="margin:0 0 4px">PROFILE 2 bits gs <code>bec33f07</code> / m2 <code>ac8132bd</code>, SET_ACC 2→0 · gate: ≥ 99 % of 1000 samples PEER</div>
  <table>
    <tr><th>VARIANT</th><th>TX_AMP</th><th>OTHER M2→GS</th><th>OTHER GS→M2</th></tr>
    <tr><td>CAL0</td><td>31</td><td>6.9 % [5.9, 8.1]</td><td>8.0 % [6.8, 9.2]</td></tr>
    <tr><td>R1</td><td>12</td><td>10.3 % [9.3, 11.5]</td><td>23.9 % [22.4, 25.5]</td></tr>
    <tr><td>R1</td><td>16</td><td>9.4 % [8.4, 10.5]</td><td>15.2 % [13.9, 16.5]</td></tr>
  </table>
  <div class="note">OTHER = sample without K28.5 + peer ID · Wilson 95 % CI</div>
</section>

<!-- ===================== 2. MEASUREMENTS ===================== -->
<section>
  <h2>2 · 2.5G BER PER DIRECTION vs PUBLISHED DATA</h2>
  <div class="chartbox">{CHART}</div>
  <table class="vals" style="margin-top:8px">
    <tr><th>LINK</th><th>BIT ERRORS</th><th>BER</th><th>95 % CI (Poisson)</th><th>ERR. WINDOWS</th></tr>
    <tr><td><span class="dot" style="background:{RED}"></span>M2 → GS</td><td>50</td><td><b>2.23e-11</b></td><td>[1.66e-11, 2.94e-11]</td><td>18 / 177</td></tr>
    <tr><td><span class="dot" style="background:{GREEN}"></span>GS → M2</td><td>2</td><td><b>8.93e-13</b></td><td>[1.08e-13, 3.23e-12]</td><td>2 / 177</td></tr>
    <tr><td><span class="dot" style="background:{NAVY}"></span>Cologne Chip</td><td>0 in 1.25e10</td><td>—</td><td>upper bound &lt; 2.4e-10</td><td>—</td></tr>
  </table>
  <div class="note">Our soak: R1, 1800 s (177 × 10 s windows), 0 sync losses, 17 Oct 00:26. 40 checked bits per word.</div>
  <h3>What others publish</h3>
  <table>
    <tr><th>CHIP / SOURCE</th><th>RATE · CHANNEL</th><th>PUBLISHED RESULT</th></tr>
    <tr><td>Cologne Chip GateMate</td><td>2.5G / 5G</td><td>no BER, eye or duration (DS1001, UG1001, talks, repos)</td></tr>
    <tr><td>Xilinx Artix-7 GTP · WP428</td><td>6.25G · 30" FR4</td><td>eye scan to 1e-8, extrapolated to 1e-15</td></tr>
    <tr><td>Gowin GW5AT · WP1157</td><td>to 12G · cables</td><td>target 1e-12, PRBS15, "eye collapse"; no duration</td></tr>
    <tr><td>CESYS Artix-7 · WP-101</td><td>6.25G · HDMI cable</td><td>"0E0 errors", eye &gt; 75 %; no duration</td></tr>
    <tr><td>Lattice ECP5 · Intel C10GX · Efinix</td><td>—</td><td>specs at 1e-12 or tools only; no bit counts</td></tr>
    <tr><td colspan="3"><b>Attempts-to-link:</b> published by nobody — our 5/15 has no public reference.</td></tr>
  </table>
  <div class="proof"><b>Proof rule:</b> BER ≤ 1e-12 @ 95 % = 3.0e12 error-free bits = <b>40 min</b> on our 2.5G checker
  (with 2 errors: 6.3e12 bits, 84 min). <b>GS→M2</b>: upper bound 2.8e-12, ≈ 54 min more without a new error.
  <b>M2→GS</b>: ≈ 22× above target, no duration can prove it.</div>
</section>

<!-- ===================== 3. OPEN ISSUES ===================== -->
<section>
  <h2>3 · OPEN ISSUES</h2>
  <div class="issue"><div class="num" style="background:{RED}">1</div><div>
    <h4>2.5G link gate passes 5 / 15</h4>
    <p>L3: 33 % [15 %, 58 %] (Wilson). Soak gate passed on attempt 9: 7 × "Q errors &gt; 8", 1 × m2 RX_CDR_LOCKED = 0.
    No reset level (L1, L1b, L2tx, L2rx) shown to work.</p></div></div>
  <div class="issue"><div class="num" style="background:{AMBER}">2</div><div>
    <h4>RX_EQA_CKP_OFFSET is not written</h4>
    <p>set 0 → readback 1; set 2 → readback 1 (0x04[7:0], both boards). <code>link_gate.py</code> does not check readback,
    so all "R1" data is with OFFSET = 1.</p></div></div>
  <div class="issue"><div class="num" style="background:{RED}">3</div><div>
    <h4>M2 → GS is the weaker direction</h4>
    <p>50 vs 2 bit errors in 2.239e12 bits; worst 10 s window <span style="white-space:nowrap">5.6e-10</span>. 5 of 7 gate "Q" failures were M2 → GS.</p></div></div>
  <div class="issue"><div class="num" style="background:{RED}">4</div><div>
    <h4>5G: no CDR lock, 9 / 9 attempts fail</h4>
    <p>All fail health/PEER before BER (no soak). gs RX_CDR_LOCKED mostly 0; 7–24 % invalid samples.
    PLL locked, CAP_FT_OF/UF = 0, RX_EQA_LOCKED 1: the 5G eye is not open.</p></div></div>
  <div class="issue"><div class="num" style="background:{AMBER}">5</div><div>
    <h4>VDD_SER not measured</h4>
    <p>VDD_SER / VDD_SER_PLL (R105/R106 = 2 Ω) not measured in this lab; supply can be neither confirmed nor ruled out.
    Next: TP10 / TP8 on both boards while the 5G bit runs.</p></div></div>
</section>
</div>
<footer>
  <span>Sources: ulx5m-gs-m2-serdes/docs/ SOAK_R1_2G5_20261017 · CHAIN4_5G_P2_20261017 · TOOLCHAIN_20261017 · RESEARCH_SERDES_USPOREDBA_20261017</span>
  <span>REGOČ · TASK-5555 · 17 Oct 2026</span>
</footer>
</div></body></html>"""

OUT.mkdir(parents=True, exist_ok=True)
(OUT / f"{NAME}.html").write_text(HTML, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    pg.set_content(HTML, wait_until="load")
    over = pg.evaluate("""() => { const s = document.querySelector('.slide');
        const f = document.querySelector('footer').getBoundingClientRect();
        let worst = 0; document.querySelectorAll('section').forEach(e => {
          worst = Math.max(worst, e.getBoundingClientRect().bottom); });
        return {sectionsBottom: worst, footerTop: f.top, scrollH: s.scrollHeight}; }""")
    print("layout", over)
    pg.screenshot(path=str(OUT / f"{NAME}.png"), full_page=False)
    pg.pdf(path=str(OUT / f"{NAME}.pdf"), width="1920px", height="1080px",
           print_background=True, page_ranges="1")
    b.close()
print("written", OUT)
