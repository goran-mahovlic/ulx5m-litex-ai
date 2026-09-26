#!/usr/bin/env python3
# TASK-5032: does the LiteEth TX path produce a valid FCS for frames > 60 B without TXLastBE8?
# Ping with 18/19/100/1000/1472 B of data through EthUDPStack (LiteEth model PHY/MAC: a bad FCS raises
# ValueError in the model MAC). Run with the LiteX tree under test:
#   source sim/lastbe_env.sh <LXROOT>; python3 sim/tb_lastbe.py fix|nofix       -> "LASTBE <mode> PASS" or "LASTBE <mode> FAIL ..."
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.environ["LXROOT"], "liteeth"))   # liteeth/test/model
from migen import *
import migen.fhdl.simplify as _simp
from migen.fhdl.structure import Signal as _Sig
# migen sim: LiteX creates write-only memory ports (dat_r = None); MemoryToArray needs a sink for them.
_orig = _simp.MemoryToArray.transform_fragment
def _tf(self, sf, f):
    from migen.fhdl.specials import Memory
    for m in f.specials:
        if isinstance(m, Memory):
            for p in m.ports:
                if p.dat_r is None: p.dat_r = _Sig(m.width)
    return _orig(self, sf, f)
_simp.MemoryToArray.transform_fragment = _tf
from litex.gen import LiteXModule
from litex.gen.sim import run_simulation
from liteeth.common import *
from test.model import phy, mac, arp, ip, icmp
from gateware.eth_stack import EthUDPStack

model_ip, model_mac = convert_ip("192.168.10.1"), 0x12345678abcd
dut_ip, dut_mac     = convert_ip("192.168.10.212"), 0x10e2d5000000

class Cap(icmp.ICMP):
    def __init__(self, ip_, a, box): self.box = box; icmp.ICMP.__init__(self, ip_, a)
    def process(self, packet): self.box.append(packet)

class DUT(LiteXModule):
    def __init__(self, fix):
        self.replies = []
        self.phy_model = phy.PHY(8)
        self.mac_model = mac.MAC(self.phy_model, loopback=False)
        self.arp_model = arp.ARP(self.mac_model, model_mac, model_ip)
        self.ip_model  = ip.IP(self.mac_model, model_mac, model_ip, loopback=False)
        self.icmp_model = Cap(self.ip_model, model_ip, self.replies)
        self.dut = EthUDPStack(self.phy_model, dut_mac, dut_ip, 100000, dw=8, tx_last_be_fix=fix)

def ping(fix, n):
    d = DUT(fix)
    payload = [(i*7 + 3) & 0xff for i in range(n)]
    res = {}
    def gen(d):
        r = icmp.ICMPPacket(payload); r.msgtype = icmp_type_ping_request; r.code = 0; r.checksum = 0
        r.quench = 0x50320001
        d.icmp_model.send(r, target_ip=dut_ip)
        for _ in range(20000):
            if d.replies: break
            yield
        res["ok"] = len(d.replies) == 1 and list(d.replies[0]) == payload
    try:
        run_simulation(d, {"sys": [gen(d)], "eth_tx": [d.phy_model.phy_sink.generator(), d.phy_model.generator()],
                           "eth_rx": [d.phy_model.phy_source.generator()]},
                       {"sys": 10, "eth_rx": 10, "eth_tx": 10})
    except ValueError:
        return "FCS/preamble error"
    return "OK" if res.get("ok") else "no/bad reply"

if __name__ == "__main__":
    mode = sys.argv[1]
    out = {n: ping(mode == "fix", n) for n in (18, 19, 100, 1000, 1472)}
    print(out)
    print("LASTBE %s %s" % (mode, "PASS" if all(v == "OK" for v in out.values()) else "FAIL"))
