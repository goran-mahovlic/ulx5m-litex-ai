import socket, struct, time, sys
s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0806)); s.bind(("eth0", 0)); s.settimeout(0.3)
mymac = s.getsockname()[4]
def mk(total):
    arp = struct.pack("!HHBBH6s4s6s4s", 1, 0x800, 6, 4, 1, mymac, socket.inet_aton("192.168.10.14"), b"\0"*6, socket.inet_aton("192.168.10.212"))
    f = b"\xff"*6 + mymac + b"\x08\x06" + arp
    return f + bytes((i*37+11) & 0xff for i in range(total - len(f)))
for total in [int(x) for x in sys.argv[1:]]:
    ok = 0
    for k in range(6):
        s.send(mk(total)); t0 = time.time(); got = False
        while time.time() - t0 < 0.3:
            try: d = s.recv(2048)
            except socket.timeout: break
            if d[6:9] == b"\x10\xe2\xd5" and d[20:22] == b"\x00\x02": got = True; break
        ok += got; time.sleep(0.05)
    print(f"ARP req frame {total} B (+4 FCS): {ok}/6 replies", flush=True)
