#!/usr/bin/env python3
"""TASK-5033: Linux DTS for the ULX5M-GS VexRiscv-SMP SoC. mkdts.py <build dir> > rv32.dts

litex_json2dts_linux only emits the LiteEth node when an `ethphy` CSR block exists; our GbePHY has none (the
KSZ9031 is configured by the hardware mdio_core), so the `litex,liteeth` node is added here with the "mac" and
"buffer" regions only (the Linux liteeth driver maps them by name and never touches "mdio").
TASK-5040: with --with-video (constant VIDEO_FB_BASE) a simple-framebuffer node (320x240 r5g6b5, shown 2x on DVI)
is added, its memory is reserved (no-map) and kernel messages go to tty0 (fbcon) as well as liteuart.
Compile on the Pi (no dtc in the container): dtc -O dtb -o rv32.dtb rv32.dts
TASK-5051: mkdts.py <build dir> [--font NAME] [--append "ARGS"] - fbcon font (default VGA8x8, the only small font of
the prebuilt 5.14; the Buildroot 6.12 kernel also has 6x8, 6x10, MINI4x6) and extra kernel arguments, e.g.
--font 6x8 --append "consoleblank=0 usbhostd=-v sbcdiag=0xf0002800".
"""
import argparse, json, os, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("build")
ap.add_argument("--font", default="VGA8x8")
ap.add_argument("--append", default="")
args = ap.parse_args()
build = args.build
csr = os.path.join(build, "csr.json")
dts = subprocess.run([sys.executable, "-m", "litex.tools.litex_json2dts_linux", "--root-device", "ram0", csr],
                     check=True, capture_output=True, text=True).stdout
d = json.load(open(csr))
if "ethmac" in d["csr_bases"] and "litex,liteeth" not in dts:
    c, m = d["constants"], d["memories"]["ethmac"]
    irq = ""
    if "ethmac_interrupt" in c:
        irq = "interrupts = <%d>;" % int(c["ethmac_interrupt"])
    node = """
            mac0: mac@%x {
                compatible = "litex,liteeth";
                reg = <0x%x 0x7c>, <0x%x 0x%x>;
                reg-names = "mac", "buffer";
                litex,rx-slots = <%d>;
                litex,tx-slots = <%d>;
                litex,slot-size = <%d>;
                %s
                local-mac-address = [10 e2 d5 00 00 01];
                status = "okay";
            };
""" % (d["csr_bases"]["ethmac"], d["csr_bases"]["ethmac"], m["base"], m["size"],
       c["ethmac_rx_slots"], c["ethmac_tx_slots"], c["ethmac_slot_size"], irq)
    anchor = "            liteuart0: serial@"
    assert anchor in dts, "liteuart node not found"
    dts = dts.replace(anchor, node.lstrip("\n") + "\n" + anchor, 1)
c = d["constants"]
if "video_fb_base" in c:
    base, w, h = int(c["video_fb_base"]), int(c["video_fb_width"]), int(c["video_fb_height"])
    size = (w*h*2 + 0xfff) & ~0xfff
    rsv = "            opensbi@"
    assert rsv in dts, "reserved-memory node not found"
    dts = dts.replace(rsv, "            framebuffer@%x {\n                reg = <0x%x 0x%x>;\n                no-map;\n"
                      "            };\n\n" % (base, base, size) + rsv, 1)
    fb = """        framebuffer0: framebuffer@%x {
            compatible = "simple-framebuffer";
            reg = <0x%x 0x%x>;
            width = <%d>;
            height = <%d>;
            stride = <%d>;
            format = "r5g6b5";
            status = "okay";
        };

""" % (base, base, size, w, h, w*2)
    anchor = "        soc {"
    assert anchor in dts
    dts = dts.replace(anchor, fb + anchor, 1)
    # VGA8x8 (in the prebuilt kernel): 40x30 characters on 320x240. Kernel messages on both; the last console= (liteuart) stays /dev/console, because without a USB host the
    # DVI console has no keyboard - a shell on the screen is started from the UART (getty/sh on tty1).
    # rootfs_dvi.cpio (tools/doom_linux/mkrootfs_dvi.py: + doom, doom1.wad) is 8,4 MB > the 8 MB initrd window
    dts = dts.replace("linux,initrd-end   = <0x41800000>;", "linux,initrd-end   = <0x41c00000>;", 1)
    dts = dts.replace('bootargs = "console=liteuart ', 'bootargs = "fbcon=font:%s logo.nologo console=tty0 console=liteuart '
                      % args.font, 1)
if "usb_hid" in d["csr_bases"]:
    # TASK-5047: USB HID host CSRs; S90usbhidd starts usbhidd only if this node exists (the address differs per build,
    # and a fixed address would hit another peripheral - on glr0_1 0xf0003810 is video_fb2x_dma_loop).
    ub = d["csr_bases"]["usb_hid"]
    node = """        usbhid@%x {
            compatible = "regoc,usbhid-csr";
            reg = <0x%x 0x100>;
            status = "okay";
        };

""" % (ub, ub)
    anchor = "        soc {"
    dts = dts.replace(anchor, node + anchor, 1)
if "usb_pnru" in d["csr_bases"]:
    # TASK-5051: USB 1.1 LS/FS host (PNRU port); S90usbhostd starts usbhostd only if this node exists.
    ub = d["csr_bases"]["usb_pnru"]
    node = """        usbhost@%x {
            compatible = "regoc,usb-pnru-csr";
            reg = <0x%x 0x100>;
            status = "okay";
        };

""" % (ub, ub)
    anchor = "        soc {"
    dts = dts.replace(anchor, node + anchor, 1)
if args.append:
    i = dts.index('bootargs = "') + len('bootargs = "')
    dts = dts[:i] + args.append + " " + dts[i:]
sys.stdout.write(dts)
