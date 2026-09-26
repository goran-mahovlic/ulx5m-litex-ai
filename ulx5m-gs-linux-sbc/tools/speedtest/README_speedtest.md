# ULX5M-GS Ethernet speed test (TASK-5033)

Two commands, on the Pi (192.168.10.14):

1. Load the netboot SoC and boot `speedtest.bin` over TFTP, then measure (all in one):

       ssh pi@192.168.10.14 ~/FPGA/eth_speedtest.sh

   (`netboot_app.sh speedtest` writes /srv/tftp/boot.json -> the BIOS loads speedtest.bin instead of boot.bin;
   `~/FPGA/netboot_app.sh demo` switches back to the LiteX demo.)

2. Measure again without reloading (any Linux host on 192.168.10.0/24 works too):

       python3 ~/FPGA/eth_speedtest.py 192.168.10.213 [--count 2000] [--sizes 64,512,1472]

What it measures (the board only counts/answers; the numbers come from the Linux side, board ticks = 20 MHz):
- RTT: UDP echo on port 5002, one at a time -> loss, min/avg/max ms
- Pi->FPGA: datagrams to port 5001 as fast as the host can send; the board counts packets/bytes/ticks -> Mb/s, loss
- FPGA->Pi: "TX <size> <n>" on port 5000; the board sends n datagrams -> Mb/s at the host, loss

Addresses: 192.168.10.212 = hardware ping/Etherbone (MAC 10:e2:d5:00:00:00, no CPU);
192.168.10.213 = CPU port (MAC 10:e2:d5:00:00:01): BIOS TFTP and this application.
The Pi eth0 links at 100 Mb/s, so every Pi measurement is capped at ~95 Mb/s.
Hardware path: `sudo ping -f -c 2000 -s 1472 192.168.10.212`.

NAT / other hosts: the board answers every request to the sender's source IP:port (echo -> source port,
TX data / RXSTAT / TXDONE -> the port the control datagram came from), so the script also works behind
Docker NAT. A host on the LAN without NAT (e.g. node-A 192.168.10.20) measures beyond the Pi's 100 Mb/s.

| Host | link | Pi->FPGA 1472 B | FPGA->Pi 1472 B | RTT 1472 B |
|---|---|---|---|---|
| Pi 192.168.10.14 | 100 Mb/s (lan78xx/USB) | 95.7 Mb/s, 0 lost (host-limited) | 6.33 Mb/s (CPU-limited) | 4.86 ms |
| node-A 192.168.10.20 | 1 Gb/s bridge | measured by REGOČ | | |
| dell-home (Goran, `ulx_blast`, 8 threads sendmmsg) | 1 Gb/s | host sent 110.2 Mb/s, board received 43995/50000 (12 % lost), **board measured 95.67 Mb/s** | | |

Open question (REGOČ, uputa #39): the board caps at ~96 Mb/s of 1472 B datagrams = ~8.1 kpps, the same figure as
from the 100 Mb/s Pi, so the limit is the CPU/MAC (VexRiscv lite at 20 MHz polling 2 RX slots of 2 KiB), not
the link. No PAUSE frames come from the board: LiteEth has no 802.3x flow control and the KSZ9031
advertisement written by mdio_core (REG4 = 0x0001) has the pause bits 10/11 clear. Why the host sends only
~110 Mb/s is not proven (switch/host side).
