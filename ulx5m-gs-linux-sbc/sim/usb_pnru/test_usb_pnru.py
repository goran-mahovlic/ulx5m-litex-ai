# cocotb tests of the USB 1.1 host engine, TASK-5051. The SAME tests run against the PNRU reference Verilog
# (DUT_KIND=ref, tb_ref_top.v, 48 MHz) and the Migen port gateware/usb_pnru.py (DUT_KIND=mig, tb_mig_top.v,
# usb clock USB_FREQ = 48e6 or 125e6, sys 20 MHz). Only the register access differs (PNRU bus vs LiteX CSR bus);
# the register bit layout is the same. Started by sim/tb_usb_pnru.py.
#
# The USB side is a Python device model on the resolved D+/D- lines: every line transition is recorded and
# decoded offline (edge-to-edge intervals -> bits, NRZI, de-stuffing), which also gives the bit rate and the
# edge jitter of the host transmitter. Device responses are driven with exact bit times.
#
# SPDX-License-Identifier: BSD-2-Clause

import json
import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge, FallingEdge, First, Event
from cocotb.utils import get_sim_time

KIND     = os.environ.get("DUT_KIND", "mig")
USB_FREQ = float(os.environ.get("USB_FREQ", "48e6"))
SYS_FREQ = 20e6
RESULTS  = os.environ.get("RESULTS_JSON")
SMALL    = os.environ.get("DUT_SMALL") == "1"     # no connect detect in the DUT (software debounces dp/dn)

# Register bits (ultraembedded/PNRU layout, identical in both DUTs).
CTL_SOF_EN, CTL_TERMSEL, CTL_DP_PULLD, CTL_DN_PULLD, CTL_TX_FLSH = 0x1, 0x20, 0x40, 0x80, 0x100
XCVR = {"fs": 1, "ls": 2, "pre": 3}
TKN_START, TKN_IN, TKN_HS, TKN_DATA1 = 1 << 31, 1 << 30, 1 << 29, 1 << 28
RX_QUEUED, RX_CRCERR, RX_TIMEOUT, SIE_IDLE = 1 << 31, 1 << 30, 1 << 29, 1 << 28
STAT_DETECT = 0x8

PID_OUT, PID_IN, PID_SOF, PID_SETUP = 0xe1, 0x69, 0xa5, 0x2d
PID_DATA0, PID_DATA1, PID_ACK, PID_NAK, PID_PRE = 0xc3, 0x4b, 0xd2, 0x5a, 0x3c

FS_T = 1e12/12e6      # ps
LS_T = 1e12/1.5e6


def even_ps(f):
    return 2*round(1e12/f/2)


# Reference CRCs (bitwise, LSB first) ---------------------------------------------------------------------------

def crc5(v, n=11):
    c = 0x1f
    for i in range(n):
        c = (c >> 1) ^ 0x14 if ((c ^ (v >> i)) & 1) else c >> 1
    return c ^ 0x1f


def crc16(data):
    c = 0xffff
    for b in data:
        for i in range(8):
            c = (c >> 1) ^ 0xa001 if ((c ^ (b >> i)) & 1) else c >> 1
    return c ^ 0xffff


def token_bytes(pid, addr, ep):
    v = addr | (ep << 7)
    v |= crc5(v) << 11
    return [pid, v & 0xff, v >> 8]


def data_packet(pid, payload):
    c = crc16(payload)
    return [pid] + list(payload) + [c & 0xff, c >> 8]


# Line decoder --------------------------------------------------------------------------------------------------

def level(dp, dn, ls_pol):
    if dp == dn:
        return "0" if dp == 0 else "1"
    j = (dn == 1) if ls_pol else (dp == 1)
    return "J" if j else "K"


def decode(trans, ls_pol=False, t_end=None):
    """trans: [(t_ps, dp, dn, by_dev)]. Returns packets [{kind, bytes, rate, t0, t1, jitter, dev}]."""
    # Merge events at the same time (both lines switching), drop zero-length segments.
    segs = []
    for t, dp, dn, dev in trans:
        lv = level(dp, dn, ls_pol)
        if segs and abs(t - segs[-1][0]) < 500:
            segs[-1] = (segs[-1][0], lv, dev)
        elif segs and segs[-1][1] == lv:
            continue
        else:
            segs.append((t, lv, dev))
    if t_end is None:
        t_end = segs[-1][0] + 1e9 if segs else 0
    durs = [(segs[i][1], (segs[i + 1][0] if i + 1 < len(segs) else t_end) - segs[i][0], segs[i][0], segs[i][2])
            for i in range(len(segs))]
    pkts, i = [], 0
    while i < len(durs):
        lv, d, t0, dev = durs[i]
        if lv == "0" and (i == 0 or durs[i - 1][0] == "J"):
            # SE0 from idle: keep-alive (LS EOP) or bus reset
            pkts.append({"kind": "se0", "dur": d, "t0": t0, "dev": dev})
            i += 1
            continue
        if lv != "K":
            i += 1
            continue
        # Start of packet: the first K of SYNC is one bit long -> rate.
        T = FS_T if d < 2.5*FS_T else LS_T
        levels, jit, prev, edges, pos = [], [], "J", [], 0
        bits, ones, out, stuffed = [], 0, [], 0
        kind = "pkt"
        j = i
        while j < len(durs):
            lv, d, tt, _ = durs[j]
            n = int(round(d/T))
            if lv in "01":
                break
            if n > 7:           # idle (after a PRE PID) or bit stuffing violation
                n = min(n, 8)
            jit.append(d - n*T)
            edges.append((tt, pos))
            pos += n
            for _ in range(n):
                b = 1 if lv == prev else 0
                prev = lv
                if ones == 6:
                    stuffed += 1
                    ones = 0
                    if b != 0:
                        kind = "stufferr"
                    continue
                ones = ones + 1 if b else 0
                bits.append(b)
            if len(bits) >= 16 and bits_to_bytes(bits[:16])[1] == PID_PRE and T == FS_T:
                kind = "pre"
                break
            if n == 8 and kind != "pre":
                kind = "abort"
                break
            j += 1
        byts = bits_to_bytes(bits)
        t1 = durs[j][2] if j < len(durs) else t_end
        eop = durs[j][1] if (j < len(durs) and durs[j][0] == "0") else 0
        pkts.append({"kind": kind, "sync": byts[0] if byts else None, "bytes": byts[1:], "rate": T, "t0": t0,
                     "t1": t1, "jitter": jit[1:-1] if kind == "pkt" else jit, "dev": dev, "eop": eop,
                     "nbits": len(bits), "stuffed": stuffed, "edges": edges,
                     "complete": kind == "pre" or (j + 1 < len(durs) and durs[j][0] == "0")})
        if kind == "pre":
            i = j + 1
            continue
        i = j + 1
    return pkts


def bits_to_bytes(bits):
    return [sum(bits[k + i] << i for i in range(8)) for k in range(0, len(bits) - 7, 8)]


def check_crc(p):
    b = p["bytes"]
    if not b:
        return False
    pid = b[0]
    if (pid & 0xf) != ((~pid >> 4) & 0xf):
        return False
    if pid in (PID_OUT, PID_IN, PID_SOF, PID_SETUP):
        v = b[1] | (b[2] << 8)
        return len(b) == 3 and crc5(v & 0x7ff) == (v >> 11)
    if pid in (PID_DATA0, PID_DATA1):
        return crc16(b[1:-2]) == (b[-2] | (b[-1] << 8))
    return len(b) == 1


# Test bench ----------------------------------------------------------------------------------------------------

class TB:
    def __init__(self, dut):
        self.dut = dut
        self.trans = []
        self.eop_ev = Event()
        self.ls_pol = False
        self.handler = None
        self.dev_busy = False
        self.log = dut._log
        self.processed = set()     # t0 of the packets already handled
        self.skew_ps = 0           # device driver impairments (t10): D- transitions late by skew_ps,
        self.dcd_ps = 0            # D+ rising edges late by dcd_ps (single-ended threshold / duty-cycle distortion)
        self.csr = json.load(open(os.environ["CSR_MAP"])) if KIND == "mig" else None

    async def start(self):
        d = self.dut
        d.dev_oe.value = 0
        d.dev_dp.value = 0
        d.dev_dn.value = 0
        d.dev_pull.value = 0
        if KIND == "ref":
            self.clk = d.clk
            cocotb.start_soon(Clock(d.clk, even_ps(48e6), unit="ps").start())
            d.m_sel.value = 0; d.m_rd.value = 0; d.m_wr.value = 0; d.m_addr.value = 0; d.m_data_i.value = 0
            d.rst.value = 1
        else:
            self.clk = d.sys_clk
            cocotb.start_soon(Clock(d.sys_clk, even_ps(SYS_FREQ), unit="ps").start())
            cocotb.start_soon(Clock(d.usb_clk, even_ps(USB_FREQ), unit="ps").start())
            d.csr_we.value = 0; d.csr_re.value = 0; d.csr_adr.value = 0; d.csr_dat_w.value = 0
            d.sys_rst.value = 1; d.usb_rst.value = 1
        await Timer(1, unit="us")
        if KIND == "ref":
            d.rst.value = 0
        else:
            d.sys_rst.value = 0; d.usb_rst.value = 0
        cocotb.start_soon(self.monitor())
        cocotb.start_soon(self.device())
        await Timer(1, unit="us")

    # Register access ------------------------------------------------------------------------------------------
    REF_ADDR = {"ctrl": 0, "stat": 1, "irq_ack": 2, "irq_sts": 3, "irq_mask": 4, "tx_len": 5, "token": 6,
                "rx_stat": 7, "data": 8}

    async def wr(self, reg, val):
        d = self.dut
        await FallingEdge(self.clk)
        if KIND == "ref":
            d.m_sel.value = 1; d.m_addr.value = self.REF_ADDR[reg]; d.m_data_i.value = val; d.m_wr.value = 1
            await FallingEdge(self.clk)
            d.m_sel.value = 0; d.m_wr.value = 0
        else:
            d.csr_adr.value = self.csr[reg]; d.csr_dat_w.value = val; d.csr_we.value = 1
            await FallingEdge(self.clk)
            d.csr_we.value = 0
        await FallingEdge(self.clk)

    async def rd(self, reg):
        d = self.dut
        await FallingEdge(self.clk)
        if KIND == "ref":
            if reg == "rx_data":        # FIFO: pop loads the output register, then read it
                d.m_sel.value = 1; d.m_addr.value = 8; d.m_rd.value = 1
                await FallingEdge(self.clk)
                d.m_rd.value = 0
                await FallingEdge(self.clk)
                v = int(d.m_data_o.value)
                d.m_sel.value = 0
                return v & 0xff
            d.m_sel.value = 1; d.m_addr.value = self.REF_ADDR[reg]
            await FallingEdge(self.clk)
            v = int(d.m_data_o.value)
            d.m_sel.value = 0
            return v
        d.csr_adr.value = self.csr[reg]; d.csr_re.value = 1
        await FallingEdge(self.clk)
        d.csr_re.value = 0
        v = int(d.csr_dat_r.value)
        await FallingEdge(self.clk)
        return v

    async def push_tx(self, data):
        for b in data:
            if KIND == "ref":
                await self.wr("data", b)
            else:
                await self.wr("tx_data", b)

    async def root_config(self, speed, sof=False):
        v = (XCVR[speed] << 3) | CTL_TERMSEL | CTL_DP_PULLD | CTL_DN_PULLD | CTL_TX_FLSH | (CTL_SOF_EN if sof else 0)
        await self.wr("ctrl", v)

    async def transaction(self, pid, addr, ep, data=b"", hs=True, data1=False, timeout_us=400):
        """Runs one transaction as ucmem/req.c does; returns (rx_stat, rx bytes)."""
        if pid != PID_IN:
            await self.push_tx(data)
        await self.wr("tx_len", len(data) if pid != PID_IN else 0)
        tok = (pid << 16) | (addr << 9) | (ep << 5) | TKN_START
        tok |= (TKN_HS if hs else 0) | (TKN_DATA1 if data1 else 0) | (TKN_IN if pid == PID_IN else 0)
        await self.wr("token", tok)
        t0 = get_sim_time("us")
        while True:
            s = await self.rd("rx_stat")
            if not (s & RX_QUEUED) and (s & SIE_IDLE):
                break
            if get_sim_time("us") - t0 > timeout_us:
                raise AssertionError("transaction did not finish, rx_stat=%08x" % s)
        rx = []
        if pid == PID_IN and not (s & (RX_TIMEOUT | RX_CRCERR)) and ((s >> 16) & 0xff) in (PID_DATA0, PID_DATA1):
            for _ in range(s & 0xffff):
                rx.append(await self.rd("rx_data"))
        return s, rx

    # USB line monitor and device model -----------------------------------------------------------------------
    async def monitor(self):
        d = self.dut
        prev = None
        se0 = False
        while True:
            dp, dn = d.line_dp.value, d.line_dn.value
            dp = int(dp) if dp.is_resolvable else 0
            dn = int(dn) if dn.is_resolvable else 0
            if (dp, dn) != prev:
                t = get_sim_time("ps")
                self.trans.append((t, dp, dn, int(d.dev_oe.value)))
                if dp == 0 and dn == 0:
                    se0 = True
                elif se0:
                    se0 = False
                    self.eop_ev.set()
                prev = (dp, dn)
            await First(d.line_dp.value_change, d.line_dn.value_change)

    def packets(self, host_only=False):
        p = decode(self.trans, self.ls_pol, get_sim_time("ps"))
        return [x for x in p if not (host_only and x["dev"])]

    async def device(self):
        """Calls self.handler(pkt) for every new host packet after its EOP; drives the returned response."""
        while True:
            await self.eop_ev.wait()
            self.eop_ev.clear()
            if self.dev_busy:
                continue
            T = LS_T if (self.ls_pol or getattr(self, "pre_mode", False)) else FS_T
            await Timer(round(2*T), unit="ps")
            for p in self.packets():
                if p["kind"] != "pkt" or not p["complete"] or p["t0"] in self.processed:
                    continue
                self.processed.add(p["t0"])
                if p["dev"] or self.handler is None:
                    continue
                resp = self.handler(p)
                if resp:
                    await self.drive(resp["bytes"], resp.get("rate", FS_T), resp.get("ls_pol", self.ls_pol),
                                     resp.get("bad_crc", False))

    async def drive(self, byts, T, ls_pol, bad_crc=False):
        d = self.dut
        self.dev_busy = True
        if bad_crc:
            byts = list(byts)
            byts[-1] ^= 0x01
        bits = [0, 0, 0, 0, 0, 0, 0, 1]
        for b in byts:
            bits += [(b >> i) & 1 for i in range(8)]
        st, ones = [], 0
        for b in bits:
            st.append(b)
            ones = ones + 1 if b else 0
            if ones == 6:
                st.append(0)
                ones = 0
        J = (0, 1) if ls_pol else (1, 0)
        K = (J[1], J[0])
        lv = J
        seq = []
        for b in st:
            if b == 0:
                lv = K if lv == J else J
            seq.append(lv)
        seq += [(0, 0), (0, 0), J]
        t0 = get_sim_time("ps")
        d.dev_dp.value, d.dev_dn.value = J
        d.dev_oe.value = 1
        ev, cp, cn = [], J[0], J[1]
        for k, (p, n) in enumerate(seq):
            tk = t0 + k*T
            if p != cp:
                ev.append((tk + (self.dcd_ps if p else 0), 0, p))
            if n != cn:
                ev.append((tk + self.skew_ps, 1, n))
            cp, cn = p, n
        for t, which, v in sorted(ev):
            if round(t) > get_sim_time("ps"):
                await Timer(round(t) - get_sim_time("ps"), unit="ps")
            if which == 0:
                d.dev_dp.value = v
            else:
                d.dev_dn.value = v
        t_end = round(t0 + len(seq)*T + max(self.skew_ps, self.dcd_ps))
        if t_end > get_sim_time("ps"):
            await Timer(t_end - get_sim_time("ps"), unit="ps")
        d.dev_oe.value = 0
        self.dev_busy = False


def record(name, value):
    if not RESULTS:
        return
    r = json.load(open(RESULTS)) if os.path.exists(RESULTS) else {}
    r[name] = value
    json.dump(r, open(RESULTS, "w"), indent=1)


def jitter_stats(pkts):
    js = [j for p in pkts for j in p["jitter"]]
    if not js:
        return None
    rate = [p for p in pkts]
    return {"max_abs_ns": max(abs(x) for x in js)/1e3, "n_intervals": len(js)}


def rate_error(p):
    """Mean bit rate of a host packet (from SYNC start to EOP start) vs nominal, relative."""
    nb = p["nbits"] + p["stuffed"]
    return ((p["t1"] - p["t0"])/nb)/p["rate"] - 1


def edge_fit(p):
    """Least-squares line through the edge times of one packet (time vs bit position): mean bit period error
    (ppm) and the largest edge deviation from the line (ns) - the source jitter of USB 2.0 table 7-9 (TDJ)."""
    e = p["edges"]
    n = len(e)
    mx = sum(b for _, b in e)/n
    my = sum(t for t, _ in e)/n
    sxx = sum((b - mx)**2 for _, b in e)
    slope = sum((b - mx)*(t - my) for t, b in e)/sxx
    res = [t - (my + slope*(b - mx)) for t, b in e]
    return {"period_ppm": (slope/p["rate"] - 1)*1e6, "tdj_max_ns": max(abs(r) for r in res)/1e3, "edges": n}


# Tests ---------------------------------------------------------------------------------------------------------

SETUP_GET_DEV = bytes([0x80, 0x06, 0x00, 0x01, 0x00, 0x00, 0x12, 0x00])


@cocotb.test()
async def t01_crc_reference(dut):
    """Reference CRC functions against known USB packets (SETUP addr 0 ep 0 = 2D 00 10; GET_DESCRIPTOR)."""
    assert token_bytes(PID_SETUP, 0, 0) == [0x2d, 0x00, 0x10]
    assert crc16(SETUP_GET_DEV) == 0xf4e0, hex(crc16(SETUP_GET_DEV))
    # a token with its CRC5 leaves the USB residual 01100 (MSB first) = 0b00110 in this LSB-first register
    v = 0x15 | (0xe << 7)
    v |= crc5(v) << 11
    c = 0x1f
    for i in range(16):
        c = (c >> 1) ^ 0x14 if ((c ^ (v >> i)) & 1) else c >> 1
    assert c == 0b00110, bin(c)


@cocotb.test()
async def t02_fs_setup_out(dut):
    """FS: SETUP token + DATA0 (8 bytes) -> device ACK. Token CRC5 and data CRC16 checked on the wire."""
    tb = TB(dut)
    await tb.start()
    dut.dev_pull.value = 1
    got = []

    def h(p):
        got.append(p)
        if p["bytes"] and p["bytes"][0] in (PID_DATA0, PID_DATA1):
            return {"bytes": [PID_ACK]}
    tb.handler = h
    await tb.root_config("fs")
    s, _ = await tb.transaction(PID_SETUP, 0, 0, SETUP_GET_DEV)
    await Timer(20, unit="us")
    hp = [p for p in tb.packets(host_only=True) if p["kind"] == "pkt"]
    assert len(hp) >= 2, hp
    assert hp[0]["bytes"] == token_bytes(PID_SETUP, 0, 0), hp[0]["bytes"]
    assert hp[1]["bytes"] == data_packet(PID_DATA0, SETUP_GET_DEV), [hex(x) for x in hp[1]["bytes"]]
    assert all(check_crc(p) for p in hp[:2])
    assert hp[0]["sync"] == 0x80
    assert (s >> 16) & 0xff == PID_ACK and not (s & (RX_TIMEOUT | RX_CRCERR)), hex(s)
    j = jitter_stats(hp)
    record("fs_tx_interval_dev_max_ns", j["max_abs_ns"])
    record("fs_tx_edgefit_data0", edge_fit(hp[1]))
    record("fs_eop_ns", hp[0]["eop"]/1e3)


@cocotb.test()
async def t03_fs_in_data1(dut):
    """FS: IN token -> device DATA1 (8 bytes) -> host ACK; CPU reads the 8 bytes."""
    tb = TB(dut)
    await tb.start()
    dut.dev_pull.value = 1
    payload = [0x02, 0x00, 0x04, 0x05, 0x00, 0x00, 0x00, 0x00]
    tb.handler = lambda p: {"bytes": data_packet(PID_DATA1, payload)} if p["bytes"][:1] == [PID_IN] else None
    await tb.root_config("fs")
    s, rx = await tb.transaction(PID_IN, 5, 1, data1=True)
    await Timer(20, unit="us")
    assert (s >> 16) & 0xff == PID_DATA1, hex(s)
    assert not (s & (RX_TIMEOUT | RX_CRCERR)), hex(s)
    assert s & 0xffff == 8, hex(s)
    assert rx == payload, rx
    hp = [p for p in tb.packets(host_only=True) if p["kind"] == "pkt"]
    assert hp[0]["bytes"] == token_bytes(PID_IN, 5, 1)
    assert hp[1]["bytes"] == [PID_ACK], hp[1]["bytes"]


@cocotb.test()
async def t04_fs_in_bad_crc(dut):
    """FS: DATA0 with a corrupted CRC16 -> crc_err, no ACK."""
    tb = TB(dut)
    await tb.start()
    dut.dev_pull.value = 1
    tb.handler = lambda p: ({"bytes": data_packet(PID_DATA0, [1, 2, 3, 4]), "bad_crc": True}
                            if p["bytes"][:1] == [PID_IN] else None)
    await tb.root_config("fs")
    s, rx = await tb.transaction(PID_IN, 1, 1)
    await Timer(20, unit="us")
    assert s & RX_CRCERR, hex(s)
    hp = [p for p in tb.packets(host_only=True) if p["kind"] == "pkt"]
    assert len(hp) == 1, [p["bytes"] for p in hp]


@cocotb.test()
async def t05_fs_in_timeout_and_nak(dut):
    """FS: no response -> timeout; NAK -> resp = NAK."""
    tb = TB(dut)
    await tb.start()
    dut.dev_pull.value = 1
    await tb.root_config("fs")
    s, _ = await tb.transaction(PID_IN, 3, 2)
    assert s & RX_TIMEOUT, hex(s)
    tb.handler = lambda p: {"bytes": [PID_NAK]} if p["bytes"][:1] == [PID_IN] else None
    await tb.root_config("fs")
    s, _ = await tb.transaction(PID_IN, 3, 2)
    assert (s >> 16) & 0xff == PID_NAK and not (s & RX_TIMEOUT), hex(s)


@cocotb.test()
async def t06_fs_sof(dut):
    """FS: SOF every 1 ms, frame number +1, CRC5 valid."""
    tb = TB(dut)
    await tb.start()
    dut.dev_pull.value = 1
    await tb.root_config("fs", sof=True)
    await Timer(3500, unit="us")
    sofs = [p for p in tb.packets(host_only=True) if p["kind"] == "pkt" and p["bytes"][:1] == [PID_SOF]]
    assert len(sofs) >= 3, len(sofs)
    frames = [(p["bytes"][1] | (p["bytes"][2] << 8)) & 0x7ff for p in sofs]
    assert all(check_crc(p) for p in sofs), [p["bytes"] for p in sofs]
    assert all(frames[i + 1] == frames[i] + 1 for i in range(len(frames) - 1)), frames
    per = [(sofs[i + 1]["t0"] - sofs[i]["t0"])/1e6 for i in range(len(sofs) - 1)]   # us
    assert all(abs(x - 1000) < 1 for x in per), per
    record("sof_period_us", per)


@cocotb.test()
async def t07_ls_direct(dut):
    """LS device directly on the port: IN -> DATA0 (8 bytes) at 1.5 Mb/s with LS polarity; keep-alive EOPs."""
    tb = TB(dut)
    await tb.start()
    tb.ls_pol = True
    dut.dev_pull.value = 2
    payload = [0x00, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x00, 0x00]
    tb.handler = lambda p: ({"bytes": data_packet(PID_DATA0, payload), "rate": LS_T, "ls_pol": True}
                            if p["bytes"][:1] == [PID_IN] else None)
    await tb.root_config("ls")
    s, rx = await tb.transaction(PID_IN, 2, 1, timeout_us=1500)
    await Timer(50, unit="us")
    assert (s >> 16) & 0xff == PID_DATA0 and not (s & (RX_TIMEOUT | RX_CRCERR)), hex(s)
    assert rx == payload, rx
    hp = [p for p in tb.packets(host_only=True) if p["kind"] == "pkt"]
    assert hp[0]["rate"] == LS_T and hp[0]["bytes"] == token_bytes(PID_IN, 2, 1), hp[0]
    assert hp[1]["bytes"] == [PID_ACK]
    record("ls_tx_interval_dev_max_ns", jitter_stats(hp)["max_abs_ns"])
    record("ls_tx_edgefit_token", edge_fit(hp[0]))
    # keep-alive: SOF enabled in LS mode sends only an EOP (SE0 2 LS bits) every ms
    n0 = len(tb.trans)
    await tb.root_config("ls", sof=True)
    await Timer(2500, unit="us")
    ka = [p for p in decode(tb.trans[n0 - 1:], True, get_sim_time("ps")) if p["kind"] == "se0" and not p["dev"]]
    assert len(ka) >= 2, ka
    assert all(abs(p["dur"] - 2*LS_T) < 0.2*LS_T for p in ka), [p["dur"] for p in ka]
    record("ls_keepalive_se0_ns", [p["dur"]/1e3 for p in ka])


@cocotb.test()
async def t08_pre_ls_behind_hub(dut):
    """LS device behind a FS hub (xcvrsel 3): FS SYNC+PRE, then the LS token at 1.5 Mb/s in FS polarity; LS DATA
    response; the host ACK is preceded by PRE as well."""
    tb = TB(dut)
    await tb.start()
    tb.pre_mode = True
    dut.dev_pull.value = 1      # the hub's FS pull-up
    payload = [0x01, 0x02, 0x03]
    tb.handler = lambda p: ({"bytes": data_packet(PID_DATA1, payload), "rate": LS_T, "ls_pol": False}
                            if p["bytes"][:1] == [PID_IN] else None)
    await tb.root_config("pre")
    s, rx = await tb.transaction(PID_IN, 4, 1, data1=True, timeout_us=1500)
    await Timer(50, unit="us")
    assert (s >> 16) & 0xff == PID_DATA1 and not (s & (RX_TIMEOUT | RX_CRCERR)), hex(s)
    assert rx == payload, rx
    hp = [p for p in tb.packets(host_only=True) if p["kind"] in ("pkt", "pre")]
    kinds = [(p["kind"], p["rate"] == LS_T, p["bytes"][:1]) for p in hp]
    assert kinds[0] == ("pre", False, [PID_PRE]), kinds
    assert kinds[1] == ("pkt", True, [PID_IN]) and hp[1]["bytes"] == token_bytes(PID_IN, 4, 1), kinds
    assert kinds[2] == ("pre", False, [PID_PRE]), kinds
    assert kinds[3] == ("pkt", True, [PID_ACK]), kinds
    # FS bit times between the end of the PRE PID and the LS SYNC: 4 (PRE_WAIT) + up to one LS bit (8 FS bits)
    # until the first LS bit tick; the hub needs >= 4.
    gap = (hp[1]["t0"] - hp[0]["t0"])/FS_T - 16
    record("pre_gap_fs_bits", gap)
    assert 3.5 <= gap <= 13, gap


@cocotb.test()
async def t09_bus_reset_and_detect(dut):
    """Bus reset drives SE0 while selected; connect detect sets STAT.detect after the debounce."""
    tb = TB(dut)
    await tb.start()
    dut.dev_pull.value = 1
    await Timer(40, unit="us")
    st = await tb.rd("stat")
    assert (st & STAT_DETECT or SMALL) and st & 1, hex(st)
    await tb.wr("ctrl", (2 << 1) | CTL_DP_PULLD | CTL_DN_PULLD)     # opmode 2, xcvrsel 0, termsel 0
    await Timer(20, unit="us")
    assert int(dut.host_oe.value) == 1 and int(dut.line_dp.value) == 0 and int(dut.line_dn.value) == 0
    await tb.root_config("fs")
    await Timer(2, unit="us")
    assert int(dut.host_oe.value) == 0 and int(dut.line_dp.value) == 1
    dut.dev_pull.value = 0
    await Timer(60, unit="us")
    st = await tb.rd("stat")
    assert not (st & STAT_DETECT) and not (st & 3), hex(st)


@cocotb.test()
async def t10_fs_rx_impairments(dut):
    """FS IN with a skewed D- (SE0/SE1 transients at every edge) and a late D+ rising edge (duty-cycle distortion
    of the single-ended D+ input): records which impairments still give an intact packet. Board finding (TASK-5051):
    at 48 MHz (4 samples per bit, PNRU's clock) 8 ns of D+ distortion already inserts bits (PID 4b -> 9b); from
    60 MHz (5 samples) every case passes, so the SoC runs the engine at 60 MHz (--usb-pnru-freq 60e6)."""
    if KIND != "mig":
        return
    tb = TB(dut)
    await tb.start()
    dut.dev_pull.value = 1
    payload = [0x12, 0x01, 0x00, 0x02, 0x00, 0x00, 0x00, 0x08]
    tb.handler = lambda p: {"bytes": data_packet(PID_DATA1, payload)} if p["bytes"][:1] == [PID_IN] else None
    modes = ["pnru"]
    cases = {"none": (0, 0), "skew10": (10000, 0), "skew20": (20000, 0), "skew30": (30000, 0),
             "dcd8": (0, 8000), "dcd16": (0, 16000), "skew20_dcd8": (20000, 8000)}
    table = {}
    for mn in modes:
        for cn, (sk, dc) in cases.items():
            tb.skew_ps, tb.dcd_ps = sk, dc
            await tb.root_config("fs")
            await Timer(2, unit="us")
            s, rx = await tb.transaction(PID_IN, 5, 1, data1=True)
            await Timer(20, unit="us")
            ok = ((s >> 16) & 0xff) == PID_DATA1 and not (s & (RX_TIMEOUT | RX_CRCERR)) and rx == payload
            table["%s/%s" % (mn, cn)] = ok
            if not ok:
                dut._log.info("%s/%s: rx_stat %08x rx %s" % (mn, cn, s, " ".join("%02x" % b for b in rx)))
    tb.skew_ps = tb.dcd_ps = 0
    record("rx_impairments", table)
    for k, v in table.items():
        dut._log.info("%-24s %s" % (k, "ok" if v else "FAIL"))
    assert table["pnru/none"] and table["pnru/skew20"], table
    if USB_FREQ >= 59e6:
        assert all(table.values()), table
