# LiteEth integration - CPU-less UDP endpoint

How the LiteEth core is assembled with no CPU, and how to attach your own
sys-domain application to a UDP port. Citations are `file:line` against the
LiteEth / LiteX / litex-boards checkout on your `PYTHONPATH`.

> **MDIO note.** With no MDIO bring-up the KSZ9031 stays at power-on defaults and
> negotiates **gigabit**, whose 125 MHz RXC this board cannot clock (RXC on the
> non-clock-capable `IO_EB_A7`). This design instead runs the RGMII datapath in
> fixed 100 Mbps mode (`fixed_100m=True`) and relies on the PHY's in-band status;
> it does not drive MDIO. If you need to force PHY speed/duplex, add a small
> hardware MDIO sequencer (AN on, advertise 100-FD only: reg9=0x0000,
> reg4=0x0101, reg0=0x1200) and **never** write the MMD2 pad-skew registers on
> this board revision - that has been observed to kill line transmission.

## 1. Stack assembly (no CPU)
`LiteEthUDPIPCore(phy, mac_address, ip_address, clk_freq, dw=8, with_icmp=True, ...)`
builds MAC(crossbar) -> ARP -> IP -> ICMP(auto) -> UDP as pure hardware FSMs (no
CSR/Wishbone/CPU). `ip_address` accepts a dotted string or an int.
- **Do NOT use `SoCCore.add_ethernet()`** - it hardwires `interface="wishbone"` +
  IRQ + a CPU driver. Instantiate `LiteEthUDPIPCore` directly as a submodule of a
  `SoCMini` (this is what `gateware/eth_stack.py:EthUDPStack` does).
- `interface="crossbar"` is the default and correct choice.

## 2. ICMP / ping - automatic
`with_icmp=True` (default) instantiates `LiteEthICMP`, which auto-answers ping in
hardware. No wiring, no CPU.

## 3. Getting a UDP port for your application
`port = core.udp.crossbar.get_port(udp_port, dw=8, cd="sys")` (wrapped by
`EthUDPStack.get_udp_port`).
- RX packets are routed to this port by matching **dst_port**.
- Auto data-width conversion + auto clock-domain crossing to `cd`.
- Returns an object with `.sink` (TX: app -> wire) and `.source` (RX: wire -> app).

Stream layout - `eth_udp_user_description(dw)`, identical both directions:
| field | width | notes |
|---|---|---|
| valid/ready/first/last | 1 each | stream handshake |
| src_port | 16 | param |
| dst_port | 16 | param (RX == the port you registered) |
| ip_address | 32 | TX: dest IP; RX: sender IP |
| length | 16 | **payload bytes only** (the 8-byte UDP header is added by the core) |
| data | dw | payload word |
| last_be | dw//8 | valid-byte mask of the final word (dw>8) |
| error | dw//8 | RX per-byte error |

**On TX you must set dst_port, ip_address and length explicitly per datagram** -
they are not implied by which port object you hold. The `UDPEcho` engine in
`gateware/eth_stack.py` is a minimal worked example: it swaps src/dst ports and
replies to the sender's IP.

### dw choice
- **dw=8**: one byte/cycle, simplest for a byte-oriented app. Recommended to start.
- dw=32: 4 bytes/cycle, better fabric timing at high line rate.

## 4. Custom PHY contract (what the `phy=` object must expose)
- `.sink`, `.source` - `stream.Endpoint(eth_phy_description(8))` (TX in, RX out).
- class attrs `.dw` (=8), `.tx_clk_freq`, `.rx_clk_freq` - used for period constraints.
- `.crg` submodule creating ClockDomains `cd_eth_tx`, `cd_eth_rx`.
- optional `.mdio`.
- `LiteEthPHYHWReset` = CPU-less power-on reset pulse generator; used for the PHY
  reset instead of a CSR.

The GateMate RGMII PHY in `gateware/phy_rgmii_gatemate.py` implements this contract.

## 5. Why a full migen SoC (not gen.py)
LiteEth's `gen.py` emits portable Verilog from YAML but only accepts built-in PHY
class names. The custom GateMate PHY here is migen, so the full migen SoC path is
used (plug the PHY via `phy=`, attach the application as a submodule, no Verilog
round-trip).

## 6. Simulation
`sim/tb_stack.py` swaps the GateMate PHY for LiteEth's pure-migen model PHY
(`test.model`) so the MAC/ARP/IP/ICMP/UDP datapath and the echo engine are
validated independently of RGMII I/O timing. It checks ping, ARP resolution and
UDP echo.
