#!/bin/bash
# TASK-5033: choose what the netboot SoC loads from TFTP (/srv/tftp on this Pi) on the next -r / reboot.
#   netboot_app.sh speedtest   -> boot.json loads speedtest.bin (the BIOS tries boot.json before boot.bin)
#   netboot_app.sh demo        -> no boot.json: the BIOS loads boot.bin (LiteX demo)
#   netboot_app.sh linux       -> boot.json loads Image + rv32.dtb + rootfs.cpio + opensbi.bin (Linux SoC)
#   netboot_app.sh linuxsd     -> same, with rv32sd.dtb (Linux SoC + SPI-SD, TASK-5039)
rm -f /srv/tftp/boot.json 2>/dev/null   # may belong to another user (group-writable dir)
case "$1" in
  speedtest) printf '{\n  "speedtest.bin": "0x40000000",\n  "bootargs": {"addr": "0x40000000"}\n}\n' > /srv/tftp/boot.json ;;
  demo)      rm -f /srv/tftp/boot.json ;;
  linux)     # linux-on-litex-vexriscv images (VexRiscv-SMP SoC only): OpenSBI is listed last = jump address
             printf '{\n  "Image":       "0x40000000",\n  "rv32.dtb":    "0x40ef0000",\n  "rootfs.cpio": "0x41000000",\n  "opensbi.bin": "0x40f00000"\n}\n' > /srv/tftp/boot.json ;;
  linuxsd)   printf '{\n  "Image":       "0x40000000",\n  "rv32sd.dtb":  "0x40ef0000",\n  "rootfs.cpio": "0x41000000",\n  "opensbi.bin": "0x40f00000"\n}\n' > /srv/tftp/boot.json ;;
  *) echo "usage: $0 speedtest|demo|linux|linuxsd"; exit 1 ;;
esac
ls -la /srv/tftp
