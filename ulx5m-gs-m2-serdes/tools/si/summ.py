import json,sys
d=json.load(open(sys.argv[1]))
for lab,r in d.items():
    print(f"## {lab}  skew={r['skew_mm']} mm  pn_gap={r['pn_gap']}")
    for n,x in r['nets'].items():
        print(f"  {n}: {x['total']} mm {x['by_layer']} w={x['widths']}")
        print(f"    vias: {[(v['size'],v['drill'],v['at']) for v in x['vias']]}")
        print(f"    pads: {[(p['ref'],p['pad'],p['lib'].split(':')[-1],p['side'],p['size']) for p in x['pads']]}")
        print(f"    ref: {x['ref_plane_mm']}  gaps={x['n_ref_gap']} {x['ref_gap_samples'][:3]}")
