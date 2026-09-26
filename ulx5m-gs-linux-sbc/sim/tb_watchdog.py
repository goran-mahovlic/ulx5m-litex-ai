#!/usr/bin/env python3
# TASK-5047: ResyncWatchdog (gateware/video_sbc.py) - wd rises after N resyncs without a good frame in between,
# a good frame clears the count, wd stays until reset.
# Run: source tools/sbc_env.sh && python3 sim/tb_watchdog.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))
from migen import *
from video_sbc import ResyncWatchdog

def run():
    dut = ResyncWatchdog(n=4)
    fails = []
    def ev(kind):
        yield (dut.resync if kind == "r" else dut.frame_ok).eq(1)
        yield
        yield dut.resync.eq(0); yield dut.frame_ok.eq(0)
        yield
    def check(name, want):
        got = yield dut.wd
        print(("ok  " if got == want else "FAIL") + " %-38s wd=%d (want %d)" % (name, got, want))
        if got != want: fails.append(name)
    def gen():
        for _ in range(3): yield from ev("r")
        yield from check("3 resyncs", 0)
        yield from ev("g")
        for _ in range(3): yield from ev("r")
        yield from check("good frame clears, 3 more resyncs", 0)
        yield from ev("r")
        yield from check("4th consecutive resync", 1)
        yield from ev("g")
        yield from check("wd sticky until reset", 1)
    run_simulation(dut, gen())
    print("PASS" if not fails else "FAIL %d" % len(fails))
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(run())
