import sys,json,math,re
src=open('si_extract.py').read(); src=src[:src.index("path=sys.argv[1]")]
exec(src)
path=sys.argv[1]; refs=sys.argv[2].split(','); planes=sys.argv[3].split(',')
root=parse(open(path).read())
NETS={c[1]:c[2] for c in kids(root,'net') if len(c)>2}
globals()['NETS']=NETS
fills=collections.defaultdict(list)
for z in kids(root,'zone'):
    zn=netof(z) or '?'
    for fpoly in kids(z,'filled_polygon'):
        L=kid(fpoly,'layer')[1]; pts=[(float(p[1]),float(p[2])) for p in kid(fpoly,'pts')[1:] if p[0]=='xy']
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]; fills[L].append((zn,pts,(min(xs),min(ys),max(xs),max(ys))))
def inpoly(x,y,pts):
    c=False; j=len(pts)-1
    for i in range(len(pts)):
        xi,yi=pts[i]; xj,yj=pts[j]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi+1e-18)+xi: c=not c
        j=i
    return c
def cover(L,x,y): return sorted({zn for zn,pts,bb in fills.get(L,[]) if bb[0]<=x<=bb[2] and bb[1]<=y<=bb[3] and inpoly(x,y,pts)}) or ['NONE']
# zone clearance settings
for z in kids(root,'zone'):
    n=netof(z); L=kid(z,'layer') or kid(z,'layers')
    if n in ('GND',): 
        cl=kid(kid(z,'connect_pads') or [],'clearance') if kid(z,'connect_pads') else None
        print('zone',n,L[1:],'clearance',cl[1] if cl else '?','min_thickness',(kid(z,'min_thickness') or ['',''])[1])
for fp in kids(root,'footprint'):
    ref=[p[2] for p in kids(fp,'property') if p[1]=='Reference']; ref=ref[0] if ref else '?'
    if ref not in refs: continue
    at=kid(fp,'at'); fx,fy=float(at[1]),float(at[2]); rot=float(at[3]) if len(at)>3 else 0
    for p in kids(fp,'pad'):
        pa=kid(p,'at'); r=math.radians(-rot); px,py=float(pa[1]),float(pa[2])
        x=fx+px*math.cos(r)-py*math.sin(r); y=fy+px*math.sin(r)+py*math.cos(r)
        n=netof(p)
        print(ref,p[1],n,kid(fp,'layer')[1],'size',kid(p,'size')[1:],{L:cover(L,x,y) for L in planes})
