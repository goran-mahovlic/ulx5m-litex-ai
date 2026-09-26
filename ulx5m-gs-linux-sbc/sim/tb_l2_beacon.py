#!/usr/bin/env python3
# L2 beacon (TASK-4999): raw broadcast Ethernet frame, ethertype 0x88B5, straight into the MAC
# crossbar (no ARP/IP/UDP). Checks on the frames leaving the MAC (model PHY):
#   1) >= 2 frames, dst ff:ff:ff:ff:ff:ff, src = DUT MAC, ethertype 0x88B5, FCS (CRC32) correct,
#      frame padded to >= 60 bytes before FCS.
#   2) payload = b"T4999L2" + tag + seq(be16) + snapshot bytes (LSB-first); seq increments.
#
# Run:  source ./env.sh && python3 sim/tb_l2_beacon.py
#
# SPDX-License-Identifier: BSD-2-Clause
import sys, os, struct, zlib
_liteeth = os.environ.get("LITEETH_TEST_ROOT") or os.path.join(os.environ.get("LXROOT", ""), "liteeth")
sys.path.insert(0, _liteeth)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from migen import *
from migen.fhdl import specials as _sp
from litex.gen import LiteXModule

# Sim-only shim (same as tb_rgmii_tx_sf.py): write-only memory ports get a dummy dat_r.
_get_port = _sp.Memory.get_port
def _get_port_sim(self, *a, **kw):
    port = _get_port(self, *a, **kw)
    if port.dat_r is None:
        port.dat_r = Signal(self.width)
    return port
_sp.Memory.get_port = _get_port_sim
from litex.gen.sim import run_simulation
from liteeth.common import convert_ip
from test.model import phy
from gateware.eth_stack import EthUDPStack
from gateware.l2_beacon import L2Beacon, ETHERTYPE_L2BEACON

dut_ip  = convert_ip("192.168.10.212"); dut_mac = 0x10e2d5000000
TAG     = 0x5A
SNAP    = 0x1_2345_6789_ABCD_EF01_2345_6789_ABCD_EF01_2345_6789_ABCD_EF01_2345_6789  # 229 bits
SNAP_W  = 231


class L2DUT(LiteXModule):
    def __init__(self, frames):
        self.phy_model = phy.PHY(8)
        self.phy_model.set_mac_callback(lambda p: frames.append(bytes(p)))
        self.stack = EthUDPStack(self.phy_model, dut_mac, dut_ip, 100000, dw=8)
        self.snap = Signal(SNAP_W, reset=SNAP)
        port = self.stack.core.mac.crossbar.get_port(ETHERTYPE_L2BEACON, dw=8)
        self.beacon = L2Beacon(port, dut_mac, self.snap, period=3000, tag=TAG)


def parse(frame):
    i = frame.index(b"\xd5") + 1 if frame[:1] == b"\x55" else 0
    f = frame[i:]
    body, fcs = f[:-4], f[-4:]
    assert struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF) == fcs, "bad FCS"
    assert len(body) >= 60, "not padded: %d" % len(body)
    assert body[0:6] == b"\xff" * 6, "dst MAC not broadcast: %s" % body[0:6].hex()
    assert body[6:12] == dut_mac.to_bytes(6, "big"), "src MAC %s" % body[6:12].hex()
    assert body[12:14] == b"\x88\xb5", "ethertype %s" % body[12:14].hex()
    return body[14:]


def main():
    frames = []
    dut = L2DUT(frames)

    def gen():
        for _ in range(9000):
            yield

    run_simulation(dut, {"sys": [gen()],
                         "eth_tx": [dut.phy_model.phy_sink.generator(), dut.phy_model.generator()],
                         "eth_rx": [dut.phy_model.phy_source.generator()]},
                   {"sys": 10, "eth_rx": 10, "eth_tx": 10})
    assert len(frames) >= 2, "expected >=2 beacons, got %d" % len(frames)
    seqs = []
    nb = (SNAP_W + 7) // 8
    for fr in frames:
        p = parse(fr)
        assert p[:7] == b"T4999L2", "magic %r" % p[:7]
        assert p[7] == TAG, "tag %02x" % p[7]
        seqs.append(struct.unpack("!H", p[8:10])[0])
        got = int.from_bytes(p[10:10 + nb], "little")
        assert got == SNAP, "snapshot %x != %x" % (got, SNAP)
    assert all(b == a + 1 for a, b in zip(seqs, seqs[1:])), "seq not incrementing: %s" % seqs
    print("PASS l2 beacon: %d frames, bcast, ethertype 0x88B5, FCS OK, seq %s, snapshot %d bits OK"
          % (len(frames), seqs, SNAP_W))


if __name__ == "__main__":
    main()
