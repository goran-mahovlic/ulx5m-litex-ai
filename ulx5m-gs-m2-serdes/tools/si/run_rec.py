from run_matrix import ms
from fd2d import pair
cases=[("3313 w0.127 s0.18",ms(0.127,0.18,0.0994,4.1,0.02)),("3313 w0.127 s0.10",ms(0.127,0.10,0.0994,4.1,0.02)),
("3313 w0.15 s0.13",ms(0.15,0.13,0.0994,4.1,0.02)),("1080-6L w0.10 s0.15",ms(0.10,0.15,0.0764,3.91,0.02)),
("1080-6L w0.11 s0.13 ",ms(0.11,0.13,0.0764,3.91,0.02)),("M2 1080 w0.147 s0.20",ms(0.147,0.20,0.0764,3.91,0.02)),
("M2 0201 pad, In1 voided -> ref In2 (h=0.642)",ms(0.46,0.30,0.6416,4.3,0.02)),
("GS 0402 pad, In1 voided -> GND patch on In2 (h=0.664)",ms(0.56,0.40,0.6646,4.25,0.02))]
for lab,g in cases:
    r=pair(g,dx=0.0025 if 'voided' not in lab else 0.005); print(lab,'Zdiff=%.1f'%r['Zdiff'],flush=True)
