#
# LiteX Ethernet stack for ULX5M-GS: reusable stack wrapper + a UDP echo engine.
# PHY-agnostic: pass a LiteEth-compatible phy (model PHY in sim, GateMate RGMII on hardware).
#
from migen import *
from litex.gen import LiteXModule
from litex.soc.interconnect import stream

from liteeth.common import eth_udp_user_description, eth_phy_description
from liteeth.core import LiteEthUDPIPCore


class TXLastBE8(LiteXModule):
    """8-bit MAC TX: last_be = last (TASK-4999, 24.9.2026).

    LiteEth 40dfb7a moved to LiteX's Packetizer, which never drives `last_be`. With core_dw ==
    phy_dw == 8 the MAC core adds no TX last-byte-enable stage (RX has LiteEthMACRXLastBE doing
    exactly this), so every IP/ARP/ICMP frame reaches the padding/CRC inserters with last_be = 0.
    Frames <= 60 B are rescued by LiteEthMACPaddingInserter (it forces last_be on the 60th byte);
    longer frames get FCS = 00000000 and the switch drops them -> "ping -s >= 19 fails".
    Proven by RTL simulation (sim/io50rtl: -s 20/100 replies with FCS 00000000, body correct).
    """
    def __init__(self):
        self.sink   = sink   = stream.Endpoint(eth_phy_description(8))
        self.source = source = stream.Endpoint(eth_phy_description(8))
        self.comb += [sink.connect(source), source.last_be.eq(sink.last)]


class EthUDPStack(LiteXModule):
    """Full L2-L4 stack (MAC/ARP/IP/ICMP/UDP), CPU-less, crossbar interface.

    ping (ICMP) is automatic. Use get_udp_port() to obtain a raw UDP port for a protocol engine.
    """
    def __init__(self, phy, mac_address, ip_address, clk_freq, dw=8, with_icmp=True,
                 with_sys_datapath=False, icmp_fifo_depth=2048, tx_last_be_fix=True,
                 interface="crossbar", endianness="big"):
        # interface="hybrid": the MAC also gets a CPU (wishbone) port for frames not addressed to mac_address
        # (BIOS netboot/TFTP, TASK-5033); the hardware ARP/ICMP/UDP path keeps mac_address.
        # icmp_fifo_depth: LiteEth default 128 B drops every ping with more than 120 B of data
        # (LiteEthICMPEcho: length > depth -> drop). 2048 covers -s 1472 (MTU 1500), TASK-4999.
        self.core = LiteEthUDPIPCore(
            phy         = phy,
            mac_address = mac_address,
            ip_address  = ip_address,
            clk_freq    = clk_freq,
            dw          = dw,
            with_icmp   = with_icmp,
            with_sys_datapath = with_sys_datapath,
            icmp_fifo_depth = icmp_fifo_depth,
            interface   = interface,
            endianness  = endianness,
        )
        # tx_last_be_fix=False: LiteX >= 7fca6dba sets last_be in the Packetizer itself (TASK-5032,
        # sim/tb_lastbe.py), so the fix is only needed on the old LiteX 52f183ef6 tree.
        if dw == 8 and tx_last_be_fix:
            # First stage after the MAC-core sink (sys domain, before the TX CDC); the pipeline is
            # connected in TXDatapath.do_finalize(), i.e. after this insert.
            self.tx_last_be_fix = fix = TXLastBE8()
            self.core.mac.core.tx_datapath.pipeline.insert(1, fix)

    def get_udp_port(self, udp_port, dw=8, cd="sys"):
        return self.core.udp.crossbar.get_port(udp_port, dw, cd=cd)


class UDPEcho(LiteXModule):
    """Echo every UDP datagram received on `udp_port` back to its sender.

    Buffers the whole datagram in a packet FIFO so RX is never backpressured by TX-side
    ARP resolution / stalls. Swaps src/dst ports and targets the sender's IP.
    """
    def __init__(self, stack, udp_port_num, dw=8, fifo_depth=2048):
        port = stack.get_udp_port(udp_port_num, dw)
        self.port = port

        fifo = stream.SyncFIFO(eth_udp_user_description(dw), fifo_depth, buffered=True)
        self.submodules.fifo = fifo

        # RX: wire source -> fifo.sink (payload + param verbatim).
        self.comb += port.source.connect(fifo.sink)

        # TX: fifo.source -> port.sink, swapping ports, replying to sender IP.
        src = fifo.source
        snk = port.sink
        self.comb += [
            snk.valid.eq(src.valid),
            src.ready.eq(snk.ready),
            snk.first.eq(src.first),
            snk.last.eq(src.last),
            snk.data.eq(src.data),
            snk.last_be.eq(src.last_be),
            snk.error.eq(src.error),
            # param: reply to the sender
            snk.src_port.eq(src.dst_port),     # our port
            snk.dst_port.eq(src.src_port),     # sender's port
            snk.ip_address.eq(src.ip_address), # sender's IP
            snk.length.eq(src.length),
        ]
