# Build/sim environment for this machine (tools/soc_build.sh sources it). source tools/sbc_env.sh
# Local paths: oss-cad-suite, the LiteX tree (~/app/litex-1g-deps) and the RISC-V GCC for the BIOS.
export OSS_CAD_SUITE=/home/klaudio/app/raid/tools/oss-cad-suite-20260923 LXROOT=${LXROOT:-/home/klaudio/app/litex-1g-deps}
source "$(dirname "${BASH_SOURCE[0]}")/../env.sh" >/dev/null 2>&1
export PATH="/home/klaudio/app/litex-rgmii-ulx5m/.venv/bin:/home/klaudio/app/raid/tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin:$PATH" TMPDIR=/home/klaudio/.tmp
