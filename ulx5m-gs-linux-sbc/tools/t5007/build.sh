#!/usr/bin/env bash
# usage: t5007_build.sh <name> <args...>
cd /home/klaudio/app/litex-eth-ulx5m-gs/litex-eth-ulx5m-gs
export OSS_CAD_SUITE=/home/klaudio/app/raid/tools/oss-cad-suite-20260923 LXROOT=/home/klaudio/app/litex-rgmii-ulx5m
source ./env.sh >/dev/null 2>&1
export PATH="/home/klaudio/app/litex-rgmii-ulx5m/.venv/bin:$PATH"
n=$1; shift
mkdir -p ~/.tmp/t5007
python3 gateware/target_eth.py --build --ip 192.168.10.212 --output-dir build/t5007_$n "$@" > ~/.tmp/t5007/$n.log 2>&1
echo "$n exit=$?" >> ~/.tmp/t5007/done.txt
