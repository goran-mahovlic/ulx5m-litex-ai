#!/usr/bin/env bash
# TASK-5032: tools/gbe_build.sh <name> <target_gbe.py args...>
# LiteX tree: ~/app/litex-1g-deps (LiteX b6ae9e0b2 >= 7fca6dba + CC_IOBUF T fix; migen/liteeth/boards shared)  -> build/g_<name>/, log ~/.tmp/t5032/<name>.log
cd "$(dirname "$0")/.."
export OSS_CAD_SUITE=/home/klaudio/app/raid/tools/oss-cad-suite-20260923 LXROOT=${LXROOT:-/home/klaudio/app/litex-1g-deps}
source ./env.sh >/dev/null 2>&1
export PATH="/home/klaudio/app/litex-rgmii-ulx5m/.venv/bin:$PATH" TMPDIR=/home/klaudio/.tmp
n=$1; shift
mkdir -p ~/.tmp/t5032
python3 gateware/target_gbe.py --build --output-dir build/g_$n "$@" > ~/.tmp/t5032/$n.log 2>&1
rc=$?
echo "$n exit=$rc $(date +%T)" >> ~/.tmp/t5032/done.txt
exit $rc
