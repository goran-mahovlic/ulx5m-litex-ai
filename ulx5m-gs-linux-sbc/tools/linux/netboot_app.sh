#!/bin/bash
# TASK-5033: choose what the netboot SoC loads from TFTP (/srv/tftp on this Pi) on the next -r / reboot.
#   netboot_app.sh speedtest   -> boot.json loads speedtest.bin (the BIOS tries boot.json before boot.bin)
#   netboot_app.sh demo        -> no boot.json: the BIOS loads boot.bin (LiteX demo)
#   netboot_app.sh linux       -> DEFAULT (Goran 28.09.2026): Linux 6.12 with the console on DVI + USB keyboard
#                                 (Image612 + rv32_k612.dtb + rootfs612.cpio + opensbi612.bin; bitstream …USBPNRU_pll60s1.bit)
#   netboot_app.sh linux514    -> old Linux 5.14 (Image + rv32.dtb + rootfs.cpio + opensbi.bin), no DVI console
#   netboot_app.sh linuxsd     -> same, with rv32sd.dtb (Linux SoC + SPI-SD, TASK-5039)
#   netboot_app.sh linuxdvi    -> same, with rv32dvi.dtb (Linux SoC + 1G + DVI simple-framebuffer, TASK-5040)
rm -f /srv/tftp/boot.json 2>/dev/null   # may belong to another user (group-writable dir)
case "$1" in
  speedtest) printf '{\n  "speedtest.bin": "0x40000000",\n  "bootargs": {"addr": "0x40000000"}\n}\n' > /srv/tftp/boot.json ;;
  demo)      rm -f /srv/tftp/boot.json ;;
  linux)     # Buildroot Linux 6.12 (linux/k612): fbcon on DVI + USB keyboard; OpenSBI is listed last = jump address
             printf '{\n  "Image612":       "0x40000000",\n  "rv32_k612.dtb":  "0x40ef0000",\n  "rootfs612.cpio": "0x41000000",\n  "opensbi612.bin": "0x40f00000"\n}\n' > /srv/tftp/boot.json ;;
  linux514)  # linux-on-litex-vexriscv 5.14 images (VexRiscv-SMP SoC only)
             printf '{\n  "Image":       "0x40000000",\n  "rv32.dtb":    "0x40ef0000",\n  "rootfs.cpio": "0x41000000",\n  "opensbi.bin": "0x40f00000"\n}\n' > /srv/tftp/boot.json ;;
  linuxsd)   printf '{\n  "Image":       "0x40000000",\n  "rv32sd.dtb":  "0x40ef0000",\n  "rootfs.cpio": "0x41000000",\n  "opensbi.bin": "0x40f00000"\n}\n' > /srv/tftp/boot.json ;;
  linuxdvi)  printf '{\n  "Image":       "0x40000000",\n  "rv32dvi.dtb": "0x40ef0000",\n  "rootfs_dvi.cpio": "0x41000000",\n  "opensbi.bin": "0x40f00000"\n}\n' > /srv/tftp/boot.json ;;
  *) echo "usage: $0 speedtest|demo|linux|linux514|linuxsd|linuxdvi"; exit 1 ;;
esac
ls -la /srv/tftp
