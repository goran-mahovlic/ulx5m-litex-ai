#
# UDP broadcast beacon for ULX5M-GS bring-up (TASK-4999).
#
# Every `period` sys cycles one UDP datagram goes to `dst_ip` (the subnet broadcast address, so
# LiteEth's IP TX uses ff:ff:ff:ff:ff:ff and needs no ARP). Payload:
#     b"T4999" | tag (1 B) | seq (be16) | fields (1 B each, sampled at send time)
# A host on the LAN receives it with a plain UDP socket (no root): it proves the whole TX path
# and carries internal status (PLL lock, MDIO done, RX/TX frame counters) without UART or JTAG.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from litex.gen import LiteXModule

MAGIC = b"T4999"


class UDPBeacon(LiteXModule):
    def __init__(self, stack, udp_port, dst_ip, period, tag=0, fields=()):
        port = stack.get_udp_port(udp_port, dw=8)
        self.port = port
        self.comb += port.source.ready.eq(1)    # drain anything addressed to our port

        seq = Signal(16)
        payload = [C(b, 8) for b in MAGIC] + [C(tag, 8), seq[8:16], seq[0:8]]
        payload += [f[:8] if len(f) >= 8 else Cat(f, C(0, 8 - len(f))) for f in fields]
        n = len(payload)

        # Freeze the fields for the whole datagram.
        snap  = Array([Signal(8, name="beacon_b%d" % i) for i in range(n)])
        timer = Signal(max=max(period, 2))
        idx   = Signal(max=max(n, 2))

        sink = port.sink
        self.comb += [
            sink.src_port.eq(udp_port),
            sink.dst_port.eq(udp_port),
            sink.ip_address.eq(dst_ip),
            sink.length.eq(n),
            sink.data.eq(snap[idx]),
            sink.last.eq(idx == n - 1),
            sink.last_be.eq(idx == n - 1),
        ]

        self.fsm = fsm = FSM(reset_state="WAIT")
        fsm.act("WAIT",
            NextValue(timer, timer + 1),
            If(timer == period - 1,
                NextValue(timer, 0),
                NextValue(idx, 0),
                *[NextValue(snap[i], payload[i]) for i in range(n)],
                NextState("SEND"),
            )
        )
        fsm.act("SEND",
            sink.valid.eq(1),
            If(sink.ready,
                NextValue(idx, idx + 1),
                If(sink.last,
                    NextValue(seq, seq + 1),
                    NextState("WAIT"),
                )
            )
        )
