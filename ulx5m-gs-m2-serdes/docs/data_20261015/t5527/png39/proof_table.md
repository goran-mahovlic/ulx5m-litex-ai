## (B) Repeatability — 21 fresh loads

| Load | t_link s | PEER 200/200 both | offset gs / m2 | M2→GS A | GS→M2 A | M2→GS G2 | GS→M2 G2 | result |
|---|---|---|---|---|---|---|---|---|
| t1_l1 | 41.9 | yes | 2 / 7 | 4.2e-08 | 1.3e-11 | 3.2e-08 | 0 (<4.0e-11) | rejected |
| t1_l2 | 45.7 | yes | 3 / 7 | 3.2e-08 | 2.6e-10 | 2.3e-08 | 1.3e-09 | rejected |
| t1_l3 | 49.1 | yes | 1 / 7 | 1.5e-08 | 1.6e-08 | 2.6e-08 | 2.5e-09 | rejected |
| t2_l1 | 47.6 | yes | 2 / 7 | 6.2e-11 | 4.9e-10 | — | — | first |
| t3_l1 | 43.7 | yes | 1 / 7 | 9.3e-09 | 7.6e-09 | 1.8e-08 | 5.4e-09 | rejected |
| t3_l2 | 40.8 | yes | 2 / 7 | 6.7e-10 | 9.3e-11 | — | — | first |
| t4_l1 | 43.7 | yes | 1 / 7 | 2.6e-09 | 2.9e-09 | 9.9e-09 | 1.3e-11 | rejected |
| t4_l2 | 42.2 | yes | 1 / 7 | 9.4e-08 | 2.3e-08 | 1.1e-07 | 4.6e-09 | rejected |
| t4_l3 | 43.9 | yes | 1 / 7 | 6.1e-10 | 5.5e-10 | — | — | first |
| t5_l1 | 44.0 | yes | 2 / 7 | 2.2e-08 | 1.6e-10 | 1.1e-08 | 7.4e-10 | rejected |
| t5_l2 | 46.8 | yes | 2 / 7 | 9.6e-10 | 1.2e-11 | — | — | first |
| t6_l1 | 43.8 | yes | 2 / 7 | 1.0e-09 | 0 (<3.6e-11) | 7.9e-09 | 1.8e-09 | rejected |
| t6_l2 | 48.8 | yes | 2 / 7 | 1.6e-08 | 0 (<3.5e-11) | 7.2e-10 | 8.1e-11 | G2 |
| t7_l1 | 42.8 | yes | 2 / 7 | 1.3e-10 | 0 (<3.9e-11) | — | — | first |
| t8_l1 | 48.0 | yes | 2 / 7 | 3.0e-08 | 2.0e-08 | 3.5e-10 | 6.6e-11 | G2 |
| t9_l1 | 44.4 | yes | 1 / 7 | 9.7e-11 | 0 (<3.6e-11) | — | — | first |
| t10_l1 | 43.6 | yes | 2 / 7 | 2.7e-07 | 9.2e-09 | 3.8e-09 | 8.8e-11 | rejected |
| t10_l2 | 51.3 | yes | 2 / 7 | 9.9e-08 | 1.4e-08 | 2.7e-07 | 7.0e-09 | rejected |
| t10_l3 | 43.4 | yes | 2 / 7 | 1.1e-09 | 0 (<3.9e-11) | 0 (<4.4e-11) | 0 (<3.9e-11) | G2 |
| soak_l1 | 46.5 | yes | 2 / 7 | 1.5e-08 | 4.4e-09 | 7.2e-08 | 1.7e-09 | rejected |
| soak_l2 (soak) | 48.1 | yes | 2 / 7 | 3.1e-10 | 4.8e-11 | — | — | first |

Link up (PEER 200/200 both): **21/21** loads, t_link 40.8–51.3 s. Accepted (< 1e-9 both, 60 s): first try **7/21**, after the G2 rule +3 → **10/21**.

## (A) Soak on load soak_l2 — 4.79 h

| Direction | bits | bit errors | BER | 95 % interval | 60 s intervals with 0 errors | restarts |
|---|---|---|---|---|---|---|
| M2→GS | 2.16e+13 | 17844 | 8.27e-10 | 8.15e-10 – 8.39e-10 | 0 / 278 | 0 |
| GS→M2 | 2.16e+13 | 8953 | 4.15e-10 | 4.06e-10 – 4.24e-10 | 19 / 278 | 0 |

| Hour | M2→GS | GS→M2 |
|---|---|---|
| 1 | 6.4e-10 | 4.9e-10 |
| 2 | 5.9e-10 | 1.6e-10 |
| 3 | 1.0e-09 | 1.5e-10 |
| 4 | 7.3e-10 | 5.3e-10 |
| 5 | 1.3e-09 | 8.4e-10 |
