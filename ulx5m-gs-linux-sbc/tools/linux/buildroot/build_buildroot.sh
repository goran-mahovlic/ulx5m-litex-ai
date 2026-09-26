#!/usr/bin/env bash
# TASK-5051: Buildroot + Linux 6.12 for the ULX5M-GS SBC (VexRiscv-SMP, rv32ima, ilp32), recipe of
# linux-on-litex-vexriscv plus linux_sbc.fragment and a rootfs overlay with usbhostd (tools/usbhostd).
#   tools/linux/buildroot/build_buildroot.sh [WORKDIR]      (default ~/app/raid/t5051; ~1-2 h, ~15 GB)
# Out: WORKDIR/buildroot/output/images/{Image,rootfs.cpio,opensbi.bin}; boot with the DTB from tools/linux/mkdts.py.
# Build host without root (the pai container): put file/rsync/bc/cpio wrappers in BR_HOSTTOOLS (they were unpacked
# from Debian packages with dpkg -x); Buildroot's check for exactly /usr/bin/file is then relaxed to `file`.
set -e
[ -n "$BR_HOSTTOOLS" ] && export PATH="$BR_HOSTTOOLS:$PATH"
HERE=$(cd "$(dirname "$0")" && pwd)
W=${1:-$HOME/app/raid/t5051}
BR_TAG=2026.05.3
LOLV_COMMIT=05fc5e4           # litex-hub/linux-on-litex-vexriscv, 2026-09-14
mkdir -p "$W" && cd "$W"
[ -d buildroot ] || git clone -q --depth 1 --branch $BR_TAG https://gitlab.com/buildroot.org/buildroot.git
[ -d linux-on-litex-vexriscv ] || git clone -q https://github.com/litex-hub/linux-on-litex-vexriscv
git -C linux-on-litex-vexriscv checkout -q $LOLV_COMMIT
[ -x /usr/bin/file ] || sed -i 's|^check_prog_host "/usr/bin/file"|check_prog_host "file"|' buildroot/support/dependencies/dependencies.sh
EXT=$W/linux-on-litex-vexriscv/buildroot

# rootfs overlay: upstream overlay + usbhostd
OVL=$W/overlay_sbc
rm -rf "$OVL" && mkdir -p "$OVL/usr/bin" "$OVL/etc/init.d"
make -s -C "$HERE/../../doom_linux" usbhostd
cp "$HERE/../../doom_linux/usbhostd" "$OVL/usr/bin/"
make -s -C "$HERE/../../doom_linux" csrpeek
cp "$HERE/../../doom_linux/csrpeek" "$OVL/usr/bin/"
cp "$HERE/../../usbhostd/S90usbhostd" "$OVL/etc/init.d/"
cp -a "$HERE/rootfs/." "$OVL/"             # S20console (no cursor blink), S89fbperf + S92sbcdiag (with sbcdiag=)

DEF=$W/sbc_defconfig
cp "$EXT/configs/litex_vexriscv_defconfig" "$DEF"
cat >> "$DEF" <<EOT
BR2_LINUX_KERNEL_CONFIG_FRAGMENT_FILES="$HERE/linux_sbc.fragment"
BR2_ROOTFS_OVERLAY="\$(BR2_EXTERNAL_LITEX_VEXRISCV_PATH)/board/litex_vexriscv/rootfs_overlay $OVL"
BR2_TARGET_ROOTFS_EXT2=n
BR2_ROOTFS_POST_IMAGE_SCRIPT=""
EOT
# (upstream post-image.sh builds an SD image and needs boot.json/rv32.dtb from its make.py; we boot by TFTP/serial
#  with the DTB of tools/linux/mkdts.py)
cd buildroot
make BR2_EXTERNAL="$EXT" BR2_DEFCONFIG="$DEF" defconfig
make -j"$(nproc)"
ls -la output/images
