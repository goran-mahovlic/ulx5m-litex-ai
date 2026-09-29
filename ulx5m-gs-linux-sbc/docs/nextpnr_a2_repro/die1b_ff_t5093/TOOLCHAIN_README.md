# nextpnr-a2fix — local GateMate A2 toolchain (TASK-5093, 29.09.2026.)

Status: **toolchain built, die-1B flip-flop cause NOT found yet** (board `gs` wedged before the decisive experiments,
waits for a power cycle). Do not treat this directory as "the fix for (D)". It is the base for the next attempt.

## Contents

| Path | What | Exact version |
|---|---|---|
| `nextpnr/` | git worktree, branch `a2fix` | YosysHQ nextpnr `ad8527f8` + `patches/0001` (fix B, clock router without CPE bridges) + `patches/0002` (fix C, die crossing only from X29) = commits `dea38a31`, `edca6396`. Same code as Jelena's `t5092-a2` (`d5bd4b3b`, `0ef67857`) **without** the DEBUG commits `d7c60c22`/`ffb7650d`. |
| `prjpeppercorn/` | clone of `~/app/regoc_system/prjpeppercorn` | YosysHQ prjpeppercorn `b1eb52f` (unmodified; its gmpack is byte-identical to oss-cad-suite 2026-09-28) |
| `bin/` | `nextpnr-himbaechel`, `gmpack`, `gmunpack` | built by `build.sh` |
| `share` | symlink to the `ad8527f8` chip database | `nextpnr-main-ad8527f/share` |
| `patches/` | `git format-patch ad8527f8..a2fix` | 2 patches |
| `exp/gmbit.py` | GateMate bitstream command parser / writer (CRC16 X25) | prints the command list of a `.bit` |
| `exp/mkvar.py` | rewrites the die-1B section end (status byte, NOPs) | **do not load its NOP output on the board, see below** |
| `exp/pos/` | H2: 8 groups of probe FFs (toggle, D=1, D=0) placed with CCF place boxes at 1A and at 6 spots of 1B | `pos.bit` sha1 `37e74aaf3b11` |
| `exp/h4/` | H4: 1B FF with async SET driven by a signal, FF with routed EN, latch G=1 | `h4.bit` sha1 `6dfc907310fd` |
| `exp/hw/run_after_powercycle.sh` | runs top_1a, top_x, pos, h4 on the Pi | copied to `fpga-klaudio@pi:~/t5092/` |
| `exp/vendor/` | Cologne Chip p_r 2025.11 runs with the hidden option `-A 2` | crashes, see below |

## Build and regression

```sh
./build.sh                       # -> BUILD_OK, bin/ + share
# regression (29.09.): CCGM1A1 die1b_ff top.json: bin/nextpnr == nextpnr-main-ad8527f  (cmp equal, sha1 58a7a6d1fd43)
#                      CCGM1A2 top_x.json:        bin/nextpnr == nextpnr-a2-t5092     (txt and gmpack --reset .bit cmp equal)
```

## What was found (details in ulx5m-gs-linux-sbc/docs/A2_CCGM1A2_TASK-5092.md §5.5)

- H1 (die 1B needs configuration clocks after its CHG_STATUS): 64/1024/16384 NOPs, and status 0x11: no change.
  **Most likely those NOP streams wedged the chip**: from then on no load is applied (top_1a, CFGRST alone, 1A-only
  stream, loads to `--index-chain 1`), while the old design keeps running and JTAG is fine (IDCODE ×2, BYPASS
  loopback shifts the pattern by exactly 2 bits). DirtyJTAG SRST/TRST pulses (200–300 ms) do nothing. Needs a
  power cycle. **Never change the filler between the die sections.**
- H3 (die-1B global clock dead): rejected on paper: CLKIN1/GLBOUT1 on 1B are configured, the 1B pad IOSEL has
  INPUT_ENABLE, DS1001 §2.6.2 says CLK0..3 and SER_CLK are bonded to both dies.
- Vendor reference: `p_r` 2025.11 (`Version 4.2`) accepts the hidden option `-A 2` (CCGM1A2), places and routes
  (0 unrouted) and then dies with `ERangeError` before writing a bitstream. Its bitstream writer
  (`Fpga_cfg::Fill_cfg_file`, disassembled) writes exactly one `CMD_PATH 0x10` and a final `CMD_CHG_STATUS`
  0x13 — a single-die writer; there is no multi-die (PATH 0x02) code in it. So no vendor A2 bitstream exists to
  compare with.
- Upstream test 127-bufg-a2 (strategy=full) places 88 FFs on die 1B; if it was checked on hardware, die-1B FFs work
  in some flow — worth asking the maintainer (issue draft §4).
