#
# Raw Ethernet (L2) status beacon (TASK-4999).
#
# Sends one broadcast frame per `period` sys cycles straight into the LiteEth MAC crossbar
# (ethertype 0x88B5, IEEE "local experimental"), bypassing ARP/IP/UDP: seeing it on the wire
# (tcpdump on the Pi: `ether proto 0x88b5`) proves MAC TX + PHY TX + TXC + link, and the payload
# carries the probe snapshot (RX counters, first bytes of the last received frame, clock meters)
# -> an observation channel that needs neither UART nor JTAG.
#
# Payload: b"T4999L2" + tag(1) + seq(2, big endian) + snapshot bytes (LSB-first packing of
# `snapshot`), zero-padded to the 46-byte minimum by the MAC.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import LiteXModule

ETHERTYPE_L2BEACON = 0x88B5


class L2Beacon(LiteXModule):
    def __init__(self, mac_port, mac_address, snapshot, period, tag=0):
        sink = mac_port.sink
        self.sink_valid, self.sink_ready, self.sink_last = sink.valid, sink.ready, sink.last
        # Drain anything the crossbar routes to this ethertype (nobody sends it to us).
        self.comb += mac_port.source.ready.eq(1)

        magic = b"T4999L2"
        seq   = Signal(16)
        nsnap = (len(snapshot) + 7) // 8
        snap  = Signal(8 * nsnap)
        body  = [C(b, 8) for b in magic] + [C(tag, 8), seq[8:16], seq[0:8]] + \
                [snap[8*i:8*i + 8] for i in range(nsnap)]
        n     = len(body)

        idx   = Signal(max=n + 1)
        tick  = Signal(max=period + 1)
        busy  = Signal()
        byte  = Signal(8)
        self.comb += byte.eq(Array(body)[idx])

        self.sync += [
            If(~busy,
                tick.eq(tick + 1),
                If(tick == period - 1,
                    tick.eq(0),
                    snap.eq(snapshot),
                    idx.eq(0),
                    busy.eq(1),
                )
            ).Elif(sink.valid & sink.ready,
                idx.eq(idx + 1),
                If(idx == n - 1,
                    busy.eq(0),
                    seq.eq(seq + 1),
                )
            )
        ]
        self.comb += [
            sink.valid.eq(busy),
            sink.first.eq(idx == 0),
            sink.last.eq(idx == n - 1),
            sink.last_be.eq(1),
            sink.data.eq(byte),
            sink.target_mac.eq(0xFFFFFFFFFFFF),
            sink.sender_mac.eq(mac_address),
            sink.ethernet_type.eq(ETHERTYPE_L2BEACON),
        ]
