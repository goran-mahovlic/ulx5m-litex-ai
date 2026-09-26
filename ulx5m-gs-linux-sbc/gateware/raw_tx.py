#
# Raw TX frame generator straight into the PHY sink (TASK-4999): isolates PHY TX + TXC + pins +
# link from the whole LiteEth MAC/ARP/IP stack. The frame (preamble + SFD + frame + FCS) is a
# constant computed at build time, so nothing in fabric can corrupt it except the PHY path.
#
# SPDX-License-Identifier: BSD-2-Clause

import struct
import zlib

from migen import *

from litex.gen import LiteXModule

ETHERTYPE_RAW = 0x88B6


def build_frame(src_mac, tag=0, payload_len=46, bad_fcs=False):
    body = b"\xff" * 6 + src_mac.to_bytes(6, "big") + struct.pack("!H", ETHERTYPE_RAW)
    payload = (b"T4999RAW" + bytes([tag])).ljust(payload_len, b"\x00")
    body += payload
    fcs = struct.pack("<I", (zlib.crc32(body) ^ (0xA5A5A5A5 if bad_fcs else 0)) & 0xFFFFFFFF)
    return b"\x55" * 7 + b"\xd5" + body + fcs


class RawTXFrames(LiteXModule):
    """Sends the constant frame every `period` cycles of clock domain `cd` into `sink`
    (a LiteEth PHY sink: data 8 bit, last)."""
    def __init__(self, sink, frame, period, cd="eth_tx", enable=True):
        n    = len(frame)
        rom  = Array([C(b, 8) for b in frame])
        idx  = Signal(max=n + 1)
        tick = Signal(max=period + 1)
        busy = Signal()
        self.frames = Signal(8)
        self.start  = Signal()   # 1 cycle when a frame starts (first byte accepted)
        sync = getattr(self.sync, cd)
        sync += [
            self.start.eq(0),
            If(~busy,
                tick.eq(tick + 1),
                If(tick == period - 1, tick.eq(0), idx.eq(0), busy.eq(1))
            ).Elif(sink.valid & sink.ready,
                self.start.eq(idx == 0),
                idx.eq(idx + 1),
                If(idx == n - 1, busy.eq(0), self.frames.eq(self.frames + 1))
            )
        ]
        self.comb += [
            sink.valid.eq(busy & enable),
            sink.data.eq(rom[idx]),
            sink.last.eq(idx == n - 1),
            sink.last_be.eq(1) if hasattr(sink, "last_be") else [],
        ]
