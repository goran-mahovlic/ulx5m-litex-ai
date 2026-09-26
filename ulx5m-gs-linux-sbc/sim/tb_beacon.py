#!/usr/bin/env python3
# UDP broadcast beacon (TASK-4999): the design periodically sends a UDP datagram to the subnet
# broadcast address, carrying status fields. Any host on the LAN receives it with a plain UDP
# socket (no root, no ARP, no ICMP) -> an observation channel that proves the whole TX path
# (MAC -> PHY -> wire) and reports internal state, independent of UART/JTAG.
#
# Checks on the raw frames leaving the MAC:
#   1) at least 2 beacons, dst MAC ff:ff:ff:ff:ff:ff, EtherType IPv4, valid IPv4 header checksum,
#      dst IP 192.168.10.255, UDP dst port 4999, FCS (CRC32) correct.
#   2) payload = b"T4999" + tag + seq(be16) + status bytes; seq increments; status bytes match.
#
# Run:  source ./env.sh && python3 sim/tb_beacon.py
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
from gateware.beacon import UDPBeacon

dut_ip  = convert_ip("192.168.10.212"); dut_mac = 0x10e2d5000000
BCAST   = convert_ip("192.168.10.255")
TAG     = 0x5A
STATUS  = [0xA1, 0x00, 0xFF, 0x3C]


class BeaconDUT(LiteXModule):
    def __init__(self, frames):
        self.phy_model = phy.PHY(8)
        self.phy_model.set_mac_callback(lambda p: frames.append(bytes(p)))
        self.stack = EthUDPStack(self.phy_model, dut_mac, dut_ip, 100000, dw=8)
        self.status = [Signal(8, reset=v) for v in STATUS]
        self.beacon = UDPBeacon(self.stack, udp_port=4999, dst_ip=BCAST, period=3000,
                                tag=TAG, fields=self.status)


def ip_checksum(hdr):
    s = sum(struct.unpack("!10H", hdr))
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return s


def parse(frame):
    # The model PHY hands over the MAC output byte stream: preamble + SFD + frame + FCS.
    i = frame.index(b"\xd5") + 1 if frame[:1] == b"\x55" else 0
    f = frame[i:]
    body, fcs = f[:-4], f[-4:]
    assert struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF) == fcs, "bad FCS"
    assert body[0:6] == b"\xff" * 6, "dst MAC not broadcast: %s" % body[0:6].hex()
    assert body[12:14] == b"\x08\x00", "not IPv4"
    iph = body[14:34]
    assert ip_checksum(iph) == 0xFFFF, "bad IPv4 header checksum"
    assert iph[16:20] == bytes([192, 168, 10, 255]), "dst IP %s" % iph[16:20].hex()
    assert iph[12:16] == bytes([192, 168, 10, 212]), "src IP %s" % iph[12:16].hex()
    assert iph[9] == 17, "not UDP"
    udph = body[34:42]
    sport, dport, ulen, _ = struct.unpack("!4H", udph)
    assert dport == 4999, "UDP dst port %d" % dport
    return body[42:42 + ulen - 8]


def main():
    frames = []
    dut = BeaconDUT(frames)

    def gen():
        for _ in range(12000):
            yield

    run_simulation(dut, {"sys": [gen()],
                         "eth_tx": [dut.phy_model.phy_sink.generator(), dut.phy_model.generator()],
                         "eth_rx": [dut.phy_model.phy_source.generator()]},
                   {"sys": 10, "eth_rx": 10, "eth_tx": 10})
    assert len(frames) >= 2, "expected >=2 beacons, got %d" % len(frames)
    seqs = []
    for fr in frames:
        p = parse(fr)
        assert p[:5] == b"T4999", "magic %r" % p[:5]
        assert p[5] == TAG, "tag %02x" % p[5]
        seqs.append(struct.unpack("!H", p[6:8])[0])
        assert list(p[8:8 + len(STATUS)]) == STATUS, "status %s" % p[8:].hex()
    assert all(b == a + 1 for a, b in zip(seqs, seqs[1:])), "seq not incrementing: %s" % seqs
    print("PASS beacon: %d frames, bcast MAC/IP, IPv4 csum + FCS OK, seq %s, status %s"
          % (len(frames), seqs, bytes(STATUS).hex()))


if __name__ == "__main__":
    main()
