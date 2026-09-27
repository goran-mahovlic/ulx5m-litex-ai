import json
from run_matrix import ms
from fd2d import pair
cases=[("GS 0402 AC-cap pad pair (w0.56 s0.40) on JLC 3313",ms(0.56,0.40,0.0994,4.1,0.02),0.0025),
("GS 0402 pad pair on KiCad-file stackup (h0.274)",ms(0.56,0.40,0.274,4.5,0.02),0.005),
("GS BGA neck w0.127 s0.06 on JLC 3313",ms(0.127,0.06,0.0994,4.1,0.02),0.0025),
("M2 0201 AC-cap pad pair (w0.46 s0.30) on 1080 0.0764",ms(0.46,0.30,0.0764,3.91,0.02),0.0025),
("GS 100ohm target: w0.10 s0.15 on JLC 3313",ms(0.10,0.15,0.0994,4.1,0.02),0.0025),
("GS 90ohm option: w0.127 s0.127 on JLC 3313",ms(0.127,0.127,0.0994,4.1,0.02),0.0025),
("M2 100ohm target: w0.11 s0.20 on 1080 0.0764",ms(0.11,0.20,0.0764,3.91,0.02),0.0025),
]
for lab,g,dx in cases:
    r=pair(g,dx=dx); print(lab,'Zdiff=%.1f eeff=%.2f IL2.5=%.3f dB/cm'%(r['Zdiff'],r['eeff_odd'],r['loss_diff_dB_per_mm']['2.5']*10),flush=True)
