# DVI "black screen" on the 8090 grabber - check with a known-good bitstream (TASK-5072, 27.09.2026 03:48 CEST)

**Verdict: the fault is in the grabber / HDMI cable chain, not in the run9 build and not in Linux 6.12.**

| Step | Result |
|------|--------|
| Known-good `ETH_GateMateA1_2509_1651_Linux_DVI_s1.bit` (Goran confirmed picture 25.09 17:16), `fpga-jtag gs ... -r`, BIOS + `tools/dvi/testimg_cmds.sh` (8 colour bands) | BIOS `litex>` OK, all 9 `mem_write` accepted |
| 3 snapshots `http://192.168.10.14:8090/snap.jpg` after the test image | 640x480, **one colour (7,7,7)** = MS2109 "no HDMI signal" fill, not a black picture with signal |
| Grabber USB (`534d:2109`, uvcvideo, 1-1.1.2.1.4) | enumerated since boot (+58 s), no disconnect since; ffmpeg reading `/dev/video0`, frames arrive |
| `hdmi-stream` restart | not possible (fpga-klaudio has no NOPASSWD systemctl) |

Timeline from saved snapshots: the grabber showed the Linux 6.12 fbcon login at **26.09 17:30** (`last_ok_…jpg`),
and from **17:37** onwards every snapshot is (7,7,7) (`first_nosignal_…jpg`, run9 at 21:49, now). No USB event on the
Pi in that window, so the HDMI input lost its source - most likely the HDMI cable was moved (Goran typed at the
board ~20:00 and reported "the screen kept turning off" from his own monitor at 22:46).

Pi side note: 532 `Under-voltage detected` events in 16 h (dmesg) - unrelated to DVI, but it is a real supply problem.

Physical check (Goran): 1) HDMI cable from the ULX5M-GS DVI connector into the MS2109 grabber (not the monitor);
2) if it is plugged in: re-seat both ends, then unplug/replug the grabber USB (MS2109 can stick in no-signal).
After that, one snapshot of `:8090/snap.jpg` decides; run9 does not need to be re-tested unless that is still black.
