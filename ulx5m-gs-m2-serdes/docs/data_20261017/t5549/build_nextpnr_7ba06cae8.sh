#!/bin/bash
set -euo pipefail
export PATH=~/app/raid/tools/nextpnr-pr1810/venv/bin:$PATH TMPDIR=~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/tmp
git -C ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/src submodule update --init --recursive
cmake -S ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/src -B ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/src/build -G Ninja -DARCH=himbaechel -DHIMBAECHEL_UARCH=gatemate -DEXTERNAL_CHIPDB=ON -DEXTERNAL_CHIPDB_ROOT=~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/share/nextpnr -DHIMBAECHEL_GATEMATE_DEVICES= -DHIMBAECHEL_PEPPERCORN_PATH=/nonexistent -DBUILD_GUI=OFF -DBUILD_PYTHON=OFF -DCMAKE_BUILD_TYPE=Release -DBoost_USE_STATIC_LIBS=ON -DBOOST_ROOT=~/app/raid/tools/nextpnr-pr1810/deps/boost -DEigen3_DIR=~/app/raid/tools/nextpnr-pr1810/deps/eigen/share/eigen3/cmake
ninja -C ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/src/build -j 16 nextpnr-himbaechel
mkdir -p ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/bin ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/share/nextpnr/himbaechel
install -m755 ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/src/build/nextpnr-himbaechel ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/bin/
ln -sfn ~/app/raid/tools/oss-cad-suite-20261016/share/nextpnr/himbaechel/gatemate ~/app/tmp/zadaci/TASK-5549_preuzeti-najnoviji-open-source/np7ba06/share/nextpnr/himbaechel/gatemate
echo BUILD_OK
