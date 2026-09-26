#!/usr/bin/env python3
# LiteEth stack verification on the pure-migen host model (no hardware, no PHY I/O timing):
#   1) ICMP ping   -> DUT auto-replies (exercises MAC RX/TX, ARP, IP, ICMP)
#   2) ARP resolve -> DUT resolves the model MAC (exercises the ARP requester/table)
#   3) UDP echo    -> DUT UDPEcho engine echoes a datagram back to the sender
#
# Run:
#   source ./env.sh
#   python3 sim/tb_stack.py
#
# SPDX-License-Identifier: BSD-2-Clause
import sys, os
# liteeth ships its simulation models under `test.model`; add the liteeth checkout to the
# path (env.sh exports LITEETH_TEST_ROOT; fall back to $LXROOT/liteeth).
_liteeth = os.environ.get("LITEETH_TEST_ROOT") or os.path.join(os.environ.get("LXROOT", ""), "liteeth")
if _liteeth:
    sys.path.insert(0, _liteeth)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # repo root -> `gateware` package
from migen import *
from litex.gen import LiteXModule
from litex.gen.sim import run_simulation
from liteeth.common import *
from liteeth.core import LiteEthIPCore
from test.model import phy, mac, arp, ip, icmp, udp
from gateware.eth_stack import EthUDPStack, UDPEcho

model_ip  = convert_ip("192.168.10.1");   model_mac = 0x12345678abcd
dut_ip    = convert_ip("192.168.10.50");  dut_mac   = 0x12345678ffff
CLK = {"sys": 10, "eth_rx": 10, "eth_tx": 10}

def phy_gens(dut):
    return {
        "eth_tx": [dut.phy_model.phy_sink.generator(), dut.phy_model.generator()],
        "eth_rx": [dut.phy_model.phy_source.generator()],
    }

# ---- capturing models ----
class CapICMP(icmp.ICMP):
    def __init__(self, ip, ip_address, box, debug=False):
        self.box = box; icmp.ICMP.__init__(self, ip, ip_address, debug=debug)
    def process(self, packet): self.box.append(packet)

class CapUDP(udp.UDP):
    def __init__(self, ip, ip_address, box, debug=False):
        self.box = box; udp.UDP.__init__(self, ip, ip_address, debug=debug, loopback=False)
    def process(self, packet): self.box.append(packet)

# ========================= TEST 1: PING =========================
class PingDUT(LiteXModule):
    def __init__(self):
        self.replies = []
        self.phy_model  = phy.PHY(8)
        self.mac_model  = mac.MAC(self.phy_model, loopback=False)
        self.arp_model  = arp.ARP(self.mac_model, model_mac, model_ip)
        self.ip_model   = ip.IP(self.mac_model, model_mac, model_ip, loopback=False)
        self.icmp_model = CapICMP(self.ip_model, model_ip, self.replies)
        self.dut = EthUDPStack(self.phy_model, dut_mac, dut_ip, 100000, dw=8)

def test_ping():
    dut = PingDUT()
    payload = list(b"Hello World 123456"); quench = 0x69b30001
    def gen(dut):
        req = icmp.ICMPPacket(payload)
        req.msgtype = icmp_type_ping_request; req.code = 0; req.checksum = 0; req.quench = quench
        dut.icmp_model.send(req, target_ip=dut_ip)
        for _ in range(4096):
            if dut.replies: break
            yield
        assert len(dut.replies) == 1, "no ping reply"
        r = dut.replies[0]
        assert r.msgtype == icmp_type_ping_reply, f"bad type {r.msgtype}"
        assert r.quench == quench, "quench mismatch"
        assert list(r) == payload, "payload mismatch"
        print("  [ping] OK: reply type/quench/payload match")
    run_simulation(dut, {"sys": [gen(dut)], **phy_gens(dut)}, CLK)

# ========================= TEST 2: ARP RESOLVE (DUT as requester) =========================
# NOTE: we do NOT poke ipcore.arp.table.request directly -- inside LiteEthIPCore that
# endpoint is already driven by the IP TX path's own MAC-resolution requester, so an
# external poke fights the core's arbitration and never handshakes. Instead we make the
# DUT *originate* an IP datagram to model_ip: the IP TX must ARP-resolve model_ip's MAC
# (cold cache -> who-has over the wire -> model reply -> cache) before the frame can
# egress. Delivery to the model's IP layer therefore proves the DUT-side ARP requester.
class ArpDUT(LiteXModule):
    def __init__(self, box):
        self.phy_model = phy.PHY(8)
        self.mac_model = mac.MAC(self.phy_model, loopback=False)
        self.arp_model = arp.ARP(self.mac_model, model_mac, model_ip)
        self.ip_model  = ip.IP(self.mac_model, model_mac, model_ip, loopback=False)
        self.ip_model.set_udp_callback(lambda p: box.append(p))  # capture DUT-originated payload
        self.ipcore    = LiteEthIPCore(self.phy_model, dut_mac, dut_ip, 100000, dw=8)
        # IP-layer TX injection port (protocol-muxed via the IP crossbar; the direct
        # ipcore.sink does not exist -- traffic enters through a per-protocol port).
        self.ip_port   = self.ipcore.ip.crossbar.get_port(udp_protocol, dw=8)

def test_arp():
    got = []
    dut = ArpDUT(got)
    payload = list(b"ARP-REQ-PROOF-0123")
    def gen(dut):
        sink = dut.ip_port.sink
        # Datagram-level params held for the whole packet.
        yield sink.ip_address.eq(model_ip)
        yield sink.protocol.eq(udp_protocol)     # 0x11 -> model routes to udp_callback
        yield sink.length.eq(len(payload))
        for i, b in enumerate(payload):
            last = (i == len(payload) - 1)
            yield sink.data.eq(b)
            yield sink.last.eq(1 if last else 0)
            yield sink.last_be.eq(1 if last else 0)
            yield sink.valid.eq(1)
            accepted = False
            for _ in range(20000):                # bounded: ARP resolve can take a while cold
                yield
                if (yield sink.ready) == 1:
                    accepted = True; break
            assert accepted, f"IP sink stalled on byte {i} (ARP resolve failed?)"
        yield sink.valid.eq(0)
        for _ in range(4096):                     # bounded: wait for model delivery
            if got: break
            yield
        assert got, "DUT IP datagram never reached model IP layer (ARP resolve failed)"
        print(f"  [arp]  OK: DUT ARP-resolved model MAC; {len(payload)}B IP datagram delivered")
    run_simulation(dut, {"sys": [gen(dut)], **phy_gens(dut)}, CLK)

# ========================= TEST 3: UDP ECHO =========================
class EchoDUT(LiteXModule):
    def __init__(self):
        self.replies = []
        self.phy_model = phy.PHY(8)
        self.mac_model = mac.MAC(self.phy_model, loopback=False)
        self.arp_model = arp.ARP(self.mac_model, model_mac, model_ip)
        self.ip_model  = ip.IP(self.mac_model, model_mac, model_ip, loopback=False)
        self.udp_model = CapUDP(self.ip_model, model_ip, self.replies)
        self.dut  = EthUDPStack(self.phy_model, dut_mac, dut_ip, 100000, dw=8)
        self.echo = UDPEcho(self.dut, udp_port_num=0x5678, dw=8)

def test_udp_echo():
    dut = EchoDUT()
    payload = list(b"UDP-ECHO-payload-abcdefghijklmnop")
    def gen(dut):
        pkt = udp.UDPPacket(payload)
        pkt.src_port = 0x2222; pkt.dst_port = 0x5678
        pkt.length   = len(payload) + udp_header.length; pkt.checksum = 0
        dut.udp_model.send(pkt, target_ip=dut_ip)
        for _ in range(8192):
            if dut.replies: break
            yield
        assert len(dut.replies) >= 1, "no UDP echo reply"
        r = dut.replies[0]
        assert list(r) == payload, f"echo payload mismatch: {bytes(list(r))!r}"
        assert r.src_port == 0x5678, f"echo src_port {r.src_port:#x}"
        assert r.dst_port == 0x2222, f"echo dst_port {r.dst_port:#x}"
        print(f"  [echo] OK: {len(payload)}B echoed, ports swapped (5678->2222)")
    run_simulation(dut, {"sys": [gen(dut)], **phy_gens(dut)}, CLK)

if __name__ == "__main__":
    print("== LiteEth stack verification ==")
    test_ping()
    test_arp()
    test_udp_echo()
    print("ALL TESTS PASSED")
