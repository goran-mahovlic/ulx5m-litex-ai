#!/usr/bin/env python3
"""TASK-5033 (instruction #33/#34): Ethernet speed test against the ULX5M-GS speedtest.bin (netboot SoC, CPU port).

    eth_speedtest.py [ip] [--count N] [--sizes 64,512,1472]

For every payload size:
  RTT   : N echo requests to UDP 5002, one at a time -> loss, RTT min/avg/max
  Pi->FPGA : "RX" on 5000, N datagrams to 5001 as fast as possible, "RXEND" -> the board reports
             packets/bytes/ticks it counted -> Mb/s measured by the board and loss
  FPGA->Pi : "TX <size> <N>" on 5000 -> the board blasts N datagrams back -> Mb/s measured by this host
             (first..last arrival) and by the board (its send loop), loss
The board clock (ticks) is CONFIG_CLOCK_FREQUENCY = 20 MHz. All measurement is done here; the board only
counts and answers.
"""
import argparse, socket, struct, time

CTRL, SINK, ECHO, CLK = 5000, 5001, 5002, 20e6


def mbps(nbytes, seconds):
    return nbytes * 8 / seconds / 1e6 if seconds > 0 else 0.0


def ctrl(sock, ip, msg, want, timeout=3.0, tries=5):
    """Send a control message, return the first reply that starts with `want` (drains data packets)."""
    for _ in range(tries):
        sock.sendto(msg.encode(), (ip, CTRL))
        end = time.time() + timeout
        while time.time() < end:
            sock.settimeout(max(0.01, end - time.time()))
            try:
                d, a = sock.recvfrom(2048)
            except socket.timeout:
                break
            if a[1] == CTRL and d.decode(errors="ignore").startswith(want):
                return d.decode().split()
    return None


def rtt_test(ip, size, n):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(0.5)
    rtts, lost = [], 0
    for i in range(n):
        p = struct.pack(">I", i) + bytes(size - 4)
        t0 = time.perf_counter(); s.sendto(p, (ip, ECHO))
        while True:
            try:
                d, _ = s.recvfrom(2048)
            except socket.timeout:
                lost += 1; break
            if d[:4] == p[:4]:
                rtts.append((time.perf_counter() - t0) * 1e3); break
    s.close()
    return lost, rtts


def rx_test(ip, size, n):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if not ctrl(s, ip, "RXEND", "RXSTAT"):          # flush any old sink state; board replies RXSTAT
        return None
    s.sendto(b"RX", (ip, CTRL)); time.sleep(0.05)
    payload = bytes(size)
    t0 = time.perf_counter()
    for _ in range(n):
        s.sendto(payload, (ip, SINK))
    t1 = time.perf_counter()
    time.sleep(0.2)
    r = ctrl(s, ip, "RXEND", "RXSTAT")
    s.close()
    if not r:
        return None
    pkts, nbytes, ticks = int(r[1]), int(r[2]), int(r[3])
    return {"sent_mbps": mbps(n * size, t1 - t0), "pkts": pkts, "lost": n - pkts,
            "board_mbps": mbps(nbytes, ticks / CLK) if pkts > 1 else 0.0}


def tx_test(ip, size, n):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
    s.sendto(("TX %d %d" % (size, n)).encode(), (ip, CTRL))
    got, first, last, done = 0, None, None, None
    end = time.time() + 30
    while time.time() < end:
        s.settimeout(2.0)
        try:
            d, a = s.recvfrom(2048)
        except socket.timeout:
            break
        if a[1] == SINK:
            t = time.perf_counter(); first = first or t; last = t; got += 1
        elif a[1] == CTRL and d.startswith(b"TXDONE"):
            done = d.decode().split(); break
    s.close()
    if not done:
        return {"got": got, "lost": n - got, "pi_mbps": 0.0, "board_mbps": 0.0, "done": False}
    return {"got": got, "lost": n - got, "done": True,
            "pi_mbps": mbps((got - 1) * size, last - first) if got > 1 else 0.0,
            "board_mbps": mbps(int(done[2]), int(done[3]) / CLK)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ip", nargs="?", default="192.168.10.213")
    ap.add_argument("--count", type=int, default=2000, help="datagrams per throughput test (default 2000)")
    ap.add_argument("--rtt-count", type=int, default=100)
    ap.add_argument("--sizes", default="64,512,1472")
    a = ap.parse_args()
    print("ULX5M-GS speed test -> %s (speedtest.bin, VexRiscv @ 20 MHz); count %d" % (a.ip, a.count))
    print("%6s | %-24s | %-34s | %-38s" % ("size", "RTT ms min/avg/max (loss)", "Pi->FPGA Mb/s: board (sent) loss",
                                            "FPGA->Pi Mb/s: Pi (board) loss"))
    for size in [int(x) for x in a.sizes.split(",")]:
        lost, r = rtt_test(a.ip, size, a.rtt_count)
        rtt = ("%.2f/%.2f/%.2f (%d/%d)" % (min(r), sum(r) / len(r), max(r), lost, a.rtt_count)) if r else "no reply"
        rx = rx_test(a.ip, size, a.count)
        rxs = ("%.2f (%.1f) %d/%d" % (rx["board_mbps"], rx["sent_mbps"], rx["lost"], a.count)) if rx else "no reply"
        tx = tx_test(a.ip, size, a.count)
        txs = "%.2f (%.2f) %d/%d%s" % (tx["pi_mbps"], tx["board_mbps"], tx["lost"], a.count,
                                       "" if tx["done"] else " no TXDONE")
        print("%6d | %-24s | %-34s | %-38s" % (size, rtt, rxs, txs), flush=True)


if __name__ == "__main__":
    main()
