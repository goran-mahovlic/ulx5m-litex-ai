# source sim/lastbe_env.sh <LXROOT> : toolchain + python path of the LiteX tree under test (TASK-5032)
export OSS_CAD_SUITE=/home/klaudio/app/raid/tools/oss-cad-suite-20260923 LXROOT="$1"
source "$(dirname "${BASH_SOURCE[0]}")/../env.sh" >/dev/null 2>&1
export PATH="/home/klaudio/app/litex-rgmii-ulx5m/.venv/bin:$PATH" TMPDIR=/home/klaudio/.tmp
