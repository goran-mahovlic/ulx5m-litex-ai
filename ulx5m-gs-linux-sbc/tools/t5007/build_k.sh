#!/usr/bin/env bash
# usage: build.sh <name> <args...>   -> build/k_<name>, log ~/.tmp/t4999k/<name>.log, args in <name>.args
cd /home/klaudio/app/litex-eth-ulx5m-gs/litex-eth-ulx5m-gs
export OSS_CAD_SUITE=/home/klaudio/app/raid/tools/oss-cad-suite-20260923 LXROOT=/home/klaudio/app/litex-rgmii-ulx5m
source ./env.sh >/dev/null 2>&1
export PATH="/home/klaudio/app/litex-rgmii-ulx5m/.venv/bin:$PATH"
n=$1; shift
echo "$@" > ~/.tmp/t4999k/$n.args
python3 gateware/target_eth.py --build --ip 192.168.10.212 --output-dir build/k_$n "$@" > ~/.tmp/t4999k/$n.log 2>&1
echo "$n exit=$? $(date +%T)" >> ~/.tmp/t4999k/done.txt
