#!/usr/bin/env python3
# timed.py <bit> <secs>: load, mem_test at t=8 s, UART events and 1472-byte ping replies timestamped from the load
import subprocess, sys, time, os, threading, re
bit, T = sys.argv[1], int(sys.argv[2]); U = "/dev/ttyACM0"; IP = "192.168.10.212"
subprocess.run(["stty", "-F", U, "115200", "raw", "-echo"])
subprocess.run("timeout 2 cat %s >/dev/null" % U, shell=True)
subprocess.run(["ip", "neigh", "del", IP, "dev", "eth0"], stderr=subprocess.DEVNULL)
subprocess.run(["sudo", "-n", "/usr/local/bin/openFPGALoader", "-c", "dirtyJtag", bit, "-r"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t0 = time.time(); ev = []; stop = False
fd = os.open(U, os.O_RDONLY | os.O_NONBLOCK); buf = b""
def rd():
    global buf
    while not stop:
        try: d = os.read(fd, 4096)
        except BlockingIOError: d = b""
        if d:
            buf += d
            for k in (b"Memtest OK", b"Memtest at", b"litex>"):
                while k in buf:
                    ev.append((round(time.time() - t0, 1), k.decode())); buf = buf.split(k, 1)[1]
        time.sleep(0.05)
th = threading.Thread(target=rd); th.start()
p = subprocess.Popen(["ping", "-D", "-i", "0.5", "-W", "1", "-c", str(2*T), "-s", "1472", IP], stdout=subprocess.PIPE, text=True)
time.sleep(8)
wf = os.open(U, os.O_WRONLY)
for c in "mem_test 0x40000000 0x4000000": os.write(wf, c.encode()); time.sleep(0.02)
os.write(wf, b"\r"); t_cmd = round(time.time() - t0, 1)
out = p.communicate()[0]; stop = True; th.join()
bins = [0] * (T // 10 + 1)
for l in out.splitlines():
    m = re.match(r"\[([0-9.]+)\].*bytes from", l)
    if m: bins[min(len(bins)-1, int((float(m.group(1)) - t0) // 10))] += 1
print("mem_test sent at", t_cmd, "s; UART events:", ev)
print("1472 replies per 10 s (max 20):", bins)
