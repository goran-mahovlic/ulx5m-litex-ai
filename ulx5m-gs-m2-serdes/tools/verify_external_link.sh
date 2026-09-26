#!/bin/bash
# verify_external_link.sh — ponovljiv dokaz da GS<->M2 SerDes podaci idu VANJSKIM kabelom (TASK-5055).
# Preduvjet: na obje ploče je ber_top (vidi README_verify_external_link.md). Pokretanje na Piju:
#     tools/verify_external_link.sh            (interaktivno, s koracima kabela)
#     tools/verify_external_link.sh --no-cable (samo automatski koraci)
#     ... --load    (prvo učita ber_top na m2 pa na gs, 300 Mb/s)
# Izlaz: PASS/FAIL po koraku, na kraju ukupno; exit 0 samo ako su svi koraci PASS.
cd "$(dirname "$(readlink -f "$0")")" || exit 2
T=$PWD; BIT=${SERDES_BIT_DIR:-$T/../bitstreams}
CABLE=1; LOAD=0
for a in "$@"; do case $a in --no-cable) CABLE=0;; --load) LOAD=1;; esac; done
PASSN=0; FAILN=0; RES=()
step() { # step "<ime>" <0|1>
    if [ "$2" = 0 ]; then echo "  -> PASS"; PASSN=$((PASSN+1)); RES+=("PASS  $1"); else echo "  -> FAIL"; FAILN=$((FAILN+1)); RES+=("FAIL  $1"); fi; }
jt()    { fpga-jtag "$1" run python3 "$T/ber_jtag_check.py" --samples 10 --expect "$2" 2>&1 | tail -1; }
jtok()  { local o; o=$(jt "$1" "$2"); echo "  $o"; echo "$o" | grep -q -- '-> PASS'; }
state() { python3 "$T/ber_mon.py" state --secs 3 2>&1 | tail -1; }
want()  { # want "<regex>" [pokušaja]  — čeka dok stanje ne odgovara
    local n=${2:-5} s; for i in $(seq "$n"); do s=$(state); echo "  $s"; echo "$s" | grep -Eq "$1" && return 0; sleep 1; done; return 1; }
txctl() { fpga-jtag "$1" run python3 "$T/serdes_tx_ctl.py" "${@:2}" 2>&1 | tail -1; }

echo "=== verify_external_link  $(date '+%F %T')"
if [ $LOAD = 1 ]; then
    fpga-jtag m2 $BIT/ber_m2_0g3_CFGRST.bit -r 2>&1 | tail -1; fpga-jtag gs $BIT/ber_gs_0g3_CFGRST.bit -r 2>&1 | tail -1; sleep 3
fi

echo "[1] Početno stanje: obje ploče primaju podatke DRUGE ploče, LOOPBACK_SEL=0, bez grešaka"
python3 "$T/ber_mon.py" cmd Z >/dev/null; sleep 2
{ jtok gs peer && jtok m2 peer && want 'GS=UP M2=UP'; }; step "1 početno stanje (gs i m2 primaju PEER, LOOPBACK_SEL=0)" $?

echo "[2] Utišaj TX na m2 (električni idle) -> gs MORA izgubiti podatke, m2 i dalje prima od gs"
txctl m2 idle on
{ want 'GS=DOWN' && jtok m2 peer; }; step "2 m2 TX utišan -> gs pao, m2 i dalje prima" $?
txctl m2 idle off; python3 "$T/ber_mon.py" cmd Z >/dev/null; sleep 2
want 'GS=UP M2=UP' 8; step "2b m2 TX vraćen -> oporavak obje strane" $?

echo "[3] Utišaj TX na gs -> m2 MORA izgubiti podatke, gs i dalje prima od m2"
txctl gs idle on
{ want 'GS=UP M2=DOWN' && jtok m2 down; }; step "3 gs TX utišan -> m2 pao, gs i dalje prima" $?
txctl gs idle off; python3 "$T/ber_mon.py" cmd Z >/dev/null; sleep 2
want 'GS=UP M2=UP' 8; step "3b gs TX vraćen -> oporavak obje strane" $?

echo "[4] Promjena uzorka: ubaci točno 3 greške na svaki TX -> druga strana mora izbrojiti točno 3"
python3 "$T/ber_mon.py" inject e --n 3; step "4a gs TX 3 greške -> m2 checker broji 3" $?
python3 "$T/ber_mon.py" inject E --n 3; step "4b m2 TX 3 greške -> gs checker broji 3" $?
echo "    zamijeni podatke na m2 TX fiksnim uzorkom (TX_DATA_OVR) -> gs ne smije vidjeti m2 podatke"
txctl m2 pattern 00FF00FF
{ want 'GS=DOWN' && ! jtok gs peer; }; step "4c m2 šalje drugi uzorak -> gs odbija" $?
txctl m2 pattern off; python3 "$T/ber_mon.py" cmd Z >/dev/null; sleep 2
want 'GS=UP M2=UP' 8; step "4d uzorak vraćen -> oporavak" $?

if [ $CABLE = 1 ]; then
    echo
    echo "############################################################"
    echo "###  SAD IZVUCI SerDes KABEL (između GS i M2), pa ENTER  ###"
    echo "############################################################"
    read -r _
    { want 'GS=DOWN' && jtok m2 down; }; step "5 kabel izvučen -> OBJE strane pale" $?
    echo
    echo "############################################################"
    echo "###  VRATI SerDes KABEL, pa ENTER                        ###"
    echo "############################################################"
    read -r _
    sleep 2; python3 "$T/ber_mon.py" cmd Z >/dev/null; sleep 2
    { want 'GS=UP M2=UP' 15 && jtok gs peer && jtok m2 peer; }; step "6 kabel vraćen -> oporavak obje strane" $?
fi

echo; echo "=== SAŽETAK  $(date '+%T')"; printf '  %s\n' "${RES[@]}"
echo "=== UKUPNO: $PASSN PASS, $FAILN FAIL -> $([ $FAILN = 0 ] && echo PASS || echo FAIL)"
[ $FAILN = 0 ]
