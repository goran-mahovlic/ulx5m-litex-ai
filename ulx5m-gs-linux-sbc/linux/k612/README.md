# Linux 6.12 images for the ULX5M-GS SBC

Ready-made boot files for the recommended bitstream
`bitstreams/ETH_GateMateA1_2609_1646_Linux_GbE_DVI_USBPNRU_pll60s1.bit`. These are the exact files that were
booted and measured on the board on 26–27 September 2026 (`docs/USB_HUB_PNRU.md` §7.3, §7.3.1).

They are compressed with `gzip -9`. Unpack them into the TFTP folder with `gunzip -k *.gz`.

| File | What it is | sha256 (unpacked) |
|---|---|---|
| `Image612.gz` | Linux 6.12.0 kernel (Buildroot `output/images/Image`) | `79a1e9d2768cd7ae761c2c4de3f8552f0c14337928cb9c0803117d36c75fc3f0` |
| `opensbi612.bin.gz` | OpenSBI 1.3.1 (Buildroot `output/images/fw_jump.bin`) | `f2603c09e584a38bdcd663e98eb26bd46f2c61abc4816e7b98e6eba1216f628d` |
| `rootfs612.cpio.gz` | Buildroot root file system (initramfs), zero-padded to 12 MiB | `75b8eab5aa7110ea276459a8302e061fe4e1186c2a8a66433588c0022ba92f15` |
| `rv32_k612.dtb.gz` | Device tree for build `s_usb5_pll60_s1` | `5d8d4ee267282073fb8a770e3835753564b6386c314ef8f405dd64eb499b19bc` |

`SHA256SUMS` lists the `.gz` files: `sha256sum -c SHA256SUMS`.

## How they were built

- **Kernel, OpenSBI, root file system:** `tools/linux/buildroot/build_buildroot.sh`. It uses Buildroot 2026.05.3
  and the `litex_vexriscv` recipe of [linux-on-litex-vexriscv](https://github.com/litex-hub/linux-on-litex-vexriscv)
  at commit `05fc5e4` (Linux 6.12), plus our kernel config fragment `tools/linux/buildroot/linux_sbc.fragment`
  (fbcon on the DVI framebuffer, small fonts, uinput/evdev, `ip=` on the command line, `/dev/mem`, SPI-SD).
- **Root file system overlay:** the upstream overlay, plus `usbhostd` (USB host driver, `tools/usbhostd/`),
  `csrpeek`, and the init scripts in `tools/linux/buildroot/rootfs/` and `tools/usbhostd/S90usbhostd`.
  After the Buildroot run, the `usbhostd` binary with autorepeat (`EV_REP`, TASK-5075) was put in with
  `tools/linux/cpio_append.py`. A new Buildroot run includes it anyway.
- **Device tree:** `tools/linux/rv32_usb5_pll60_s1_k612.dts`, made with

      python3 tools/linux/mkdts.py build/s_usb5_pll60_s1 --font 6x8 \
          --append "consoleblank=0 usbhostd=-v,-s,60 sbcdiag=0xf0002800" > rv32_k612.dts
      dtc -O dtb -o rv32_k612.dtb rv32_k612.dts

## Network addresses

The kernel command line in the DTB sets `ip=192.168.10.213` (board) with `192.168.10.14` as the server. The BIOS
addresses are in the bitstream. For other addresses, run `mkdts.py` again and edit `ip=` in the `.dts`.

## Login

The root file system has the Buildroot default: user `root`, **no password**. Only use it on a trusted network.
It contains no SSH server and no keys.

## License

The kernel is GPL-2.0. OpenSBI is BSD-2-Clause. The root file system holds BusyBox and other Buildroot packages
under their own licenses (mostly GPL). The source code is upstream: Buildroot 2026.05.3, linux-on-litex-vexriscv
`05fc5e4`, and the Linux 6.12 and OpenSBI sources that Buildroot downloads for that recipe. Our changes are only the
scripts, the config fragment and the overlay files in this repository (`tools/linux/`, `tools/usbhostd/`,
`tools/doom_linux/`).
