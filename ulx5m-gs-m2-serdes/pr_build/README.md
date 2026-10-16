# pr_build — GS↔M2 bits with the Cologne Chip p_r (TASK-5546)

Same design as `../gateware/ber/` (sources are read from there), built with CC yosys + p_r 4.2 instead of nextpnr.
Result and traps: [`../docs/PR_BUILD_20261016.md`](../docs/PR_BUILD_20261016.md).

| path | what |
|---|---|
| `build_pr.sh <gs\|m2> <name> [chparam …]` | CC yosys `-nomx8 -vlog` → p_r `-tm 3` → `gm_add_cfgrst.py` → `gm_cfgrst_check.py` (output in `build/`, git-ignored) |
| `tools/serdes_cmp.py a.bit b.bit` | raw CMD_SERDES block (CRC checked) from two bitstreams, decoded field by field (prjpeppercorn table) |
| `tools/pr_clocks.py <dir> g` | p_r final STA Fmax per clock, with the clock named via the netlist |
| `tools/tests/` | `cd tools && python3 -m unittest tests.test_serdes_cmp` |
| `bitstreams/` | `gs_2g5_pr.bit`, `m2_2g5_pr.bit` (CFGRST) + SHA256SUMS + README.txt; copy on Pi `/home/pi/fpga/pr/` |
| `cmp/` | nextpnr vs p_r: `{gs,m2}_serdes.md` (all 252 fields), `{gs,m2}_config.txt` (.config words) |
| `logs/` | p_r logs, clock table, top 40 paths |
| `try/` | probe runs (bisect of the p_r exit 4), git-ignored |
