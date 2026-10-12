#!/bin/bash
# TASK-5487 uputa #308: after lab18_5g -> lab19 scatter (10 x 240 s) -> eye H2 quick test (m2).
H=/home/pi/ulx5m-serdes/t5483
until grep -q "LAB18_5G ALL DONE" $H/lab18_5g.out; do sleep 20; done
bash $H/lab19.sh 10 > $H/lab19.out 2>&1
echo "CHAIN19 DONE $(date +%T)"
