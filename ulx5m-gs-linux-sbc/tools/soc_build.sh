#!/usr/bin/env bash
# TASK-5032: tools/soc_build.sh <name> <target_soc.py args...>  -> build/s_<name>/, log ~/.tmp/t5032/soc_<name>.log
# LiteX tree: ~/app/litex-1g-deps (LiteX b6ae9e0b2 >= 7fca6dba + CC_IOBUF T fix; migen/liteeth/boards shared)
cd "$(dirname "$0")/.."
export OSS_CAD_SUITE=/home/klaudio/app/raid/tools/oss-cad-suite-20260923 LXROOT=${LXROOT:-/home/klaudio/app/litex-1g-deps}
source ./env.sh >/dev/null 2>&1
export PATH="/home/klaudio/app/litex-rgmii-ulx5m/.venv/bin:/home/klaudio/app/raid/tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin:$PATH" TMPDIR=/home/klaudio/.tmp
n=$1; shift
mkdir -p ~/.tmp/t5032
python3 gateware/target_soc.py --build --output-dir build/s_$n "$@" > ~/.tmp/t5032/soc_$n.log 2>&1
rc=$?
echo "$n exit=$rc $(date +%T)" >> ~/.tmp/t5032/soc_done.txt
exit $rc
