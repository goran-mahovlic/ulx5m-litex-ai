# ULX5M-GS — flash and test of a clean build (TASK-4959, 2026-09-21)

Bitstream: `build/litex_eth_192.168.10.212.bit` — 438 085 B,
MD5 `d8a85c7cd440422f1caa565810b20077`, built from the original zip code
(git `4ca4386` + `71f7e54` CRLF fix in `env.sh`), the only parameter
change: `--ip 192.168.10.212`.

## Summary

| Step | Result |
|---|---|
| Transfer to the Pi (scp) | ✅ MD5 identical on both sides |
| SRAM flash `-c dirtyJtag … -r` | ✅ "Load SRAM via JTAG 100 % / Done", exit 0 (repeated 2×) |
| ICMP ping 192.168.10.212 from the Pi | ❌ 15/15 lost, `Destination Host Unreachable` |
| ARP resolution | ❌ `ip neigh` = `INCOMPLETE` / `FAILED` |
| UDP echo :7000 | ❌ 4× `socket.timeout` |
| LED 7 (heartbeat) / LED 1 (link) | ⛔ cannot be checked remotely — needs an eye on the board |

FINDING: after both flashes the board is **electrically silent on the network** — it does not reply
even to ARP, so this is not about the IP/UDP layer, but about the fact that not a single valid frame
reaches the switch.

## What was checked on the gateware side (and it is CORRECT)

Checks on the generated Verilog `build/eth/gateware/intergalaktik_ulx5m_gs.v`
and the CCF from the same build:

| Check | Result |
|---|---|
| IP embedded in the bitstream | `32'd3232238292` = 192.168.10.212, 4 occurrences (ARP sender, IP sender, IP rx filter, ARP rx filter) |
| MAC embedded | `45'd18566422200320` = 10:e2:d5:00:00:00, 3 occurrences |
| MD5 of the delivered `.bit` = MD5 of the freshly built `eth/gateware/*.bit` | identical — exactly that build was delivered |
| TXC output | `Net "eth_clocks_tx" Loc = "IO_EB_B2" \| SLEW=fast \| DRIVE=6` — the FPGA **gives** TXC to the PHY (PLL#1, 25 MHz, `crg.py` → `cd_tx25` → `DDROutput`) |
| RXC input | `IO_EB_A7`, not clock-capable, fabric routing (per `GATEMATE_CLOCKING.md`) |
| PHY reset is released | `eth_rst_n = ~(reset_storage \| ~counter_done)`; `reset_storage` default `1'd0`, `LiteEthPHYHWReset` gives a pulse and then releases → the PHY is **not** held in reset (ruled out as a cause) |
| SDC | `create_clock` only for `clk25` and `eth_clocks_rx` — PLL outputs deliberately not covered (trap from the documentation) |

So: the bitstream is not "built wrong", the parameters are in it, the pinmap matches
`docs/PINMAP.md`, and the PHY reset is released.

## What could NOT be measured (and why)

1. **Capturing traffic on the wire.** On the Pi, passwordless `sudo` works only for
   `openFPGALoader` and `uhubctl` (`sudo -n -l`). `tcpdump`, `ethtool` and `arping`
   are not installed, and an `AF_PACKET` sniffer needs root — the password from the skill was
   rejected (`sudo: 1 incorrect password attempt`). So we cannot tell
   "the FPGA sends nothing" apart from "the FPGA sends frames with a bad CRC that the switch
   drops" — and those are two completely different diagnoses.
2. **The LEDs.** There is no camera and no remote readout; LED 7 (~0.95 Hz heartbeat,
   `hb[23]` at 16 MHz) and LED 1 (link) are the only direct evidence that the sys clock runs and
   that the link is up. Without that we do not know whether the board is configured and awake at all.
3. **Cold start of the board.** `off_on_FPGA.sh` switches off `1-1` port 2, and
   **nothing is connected** there (`uhubctl`: `Port 2: 0100 power`, no `connect`);
   DirtyJTAG is on `1-1.1` port 2. So the FPGA board power does not depend on that
   USB port and cannot be cycled from here.
4. **Whether the FPGA board's network cable is in the same switch at all** as the Pi `eth0`
   (the Pi sees `192.168.10.1` and `192.168.10.200`, so its side works).

## Remaining hypotheses, ordered

1. **RGMII timing relationship (most likely).** `phy_rgmii_gatemate.py` has no
   DELAYG equivalent — GateMate does not have one. If the TXD/TXC skew misses the
   KSZ9031 window, the PHY receives garbage and not a single valid frame goes out on the wire. The symptom
   is exactly this: complete silence, without a single ARP reply.
2. **The link was never established** (the PHY does not see the reference/straps as
   expected, or the cable is not connected). Can be told apart with one look at LED 1.
3. **PLL bring-up hang.** `crg.py` itself warns: LiteX's `GateMatePLL`
   leaves `USR_PLL_LOCKED_STDY` unconnected and derives `locked` from the unstable
   `USR_PLL_LOCKED` — a documented, seed-dependent stall at bring-up.
   Can be told apart with LED 7: if the heartbeat does not blink, the sys clock is not running.

## Next step that rules out the hypotheses

One look at the board separates all three:

- LED 7 does not blink → hypothesis 3 (PLL/reset), the gateware never started working.
- LED 7 blinks, LED 1 off → hypothesis 2 (link/PHY/cable).
- LED 7 blinks, LED 1 on → hypothesis 1 (RGMII timing), and then it makes sense
  to invest in `tcpdump` on the Pi (needs root) or in shifting the TXC phase.

## How to reproduce this

```bash
scp build/litex_eth_192.168.10.212.bit fpga-klaudio@192.168.10.14:/home/fpga-klaudio/FPGA/
ssh fpga-klaudio@192.168.10.14 \
  'cd /home/fpga-klaudio/FPGA/ && sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag litex_eth_192.168.10.212.bit -r'
ssh fpga-klaudio@192.168.10.14 'sleep 60; ping -c 10 -W 2 192.168.10.212; ip neigh show 192.168.10.212'
```
