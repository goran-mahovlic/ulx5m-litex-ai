#!/usr/bin/env python3
"""2D quasi-TEM finite-difference field solver for edge-coupled diff pairs (microstrip w/ soldermask, asym. stripline).
Returns Z0(single), Zodd, Zeven, Zdiff, eps_eff(odd), and per-length loss at given freqs:
  conductor loss from surface-charge distribution of the vacuum problem (J_s = c*rho_s0), Hammerstad roughness,
  dielectric loss from electric-energy fraction per material.  Uniform grid, Neumann sides, Dirichlet planes."""
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spl, math, json, sys
C0=299792458.0; EPS0=8.854187817e-12; MU0=4e-7*math.pi; SIGMA_CU=5.8e7
def build(geom, dx):
    # geom: layers list bottom->top in mm: dict(kind='diel', t, er, tand) ; planes: 'bot' at y=0, 'top' at y=H (stripline) or None
    # traces: list of (x0,x1,y0,y1) conductor rectangles ids 1,2 ; mask: (t_mask, er_mask)
    Wd=geom['W']; H=geom['H']; nx=int(round(Wd/dx))+1; ny=int(round(H/dx))+1
    er=np.ones((ny-1,nx-1)); td=np.zeros((ny-1,nx-1)); mat=np.zeros((ny-1,nx-1),int)
    yc=(np.arange(ny-1)+0.5)*dx; xc=(np.arange(nx-1)+0.5)*dx
    for k,(y0,y1,e,t) in enumerate(geom['diel']):
        m=(yc>=y0)&(yc<y1); er[m,:]=e; td[m,:]=t; mat[m,:]=k+1
    cond=np.zeros((ny,nx),int)  # 0 free, -1 ground, 1/2 traces
    cond[0,:]=-1
    if geom.get('top_plane'): cond[-1,:]=-1
    X,Y=np.meshgrid(np.arange(nx)*dx,np.arange(ny)*dx)
    for i,(x0,x1,y0,y1) in enumerate(geom['traces']):
        cond[(X>=x0-1e-9)&(X<=x1+1e-9)&(Y>=y0-1e-9)&(Y<=y1+1e-9)]=i+1
    # conformal mask: cells within t_mask of dielectric top surface (outside traces) or of trace surfaces, below mask top
    if geom.get('mask'):
        tm,em,ysurf=geom['mask']
        XC,YC=np.meshgrid(xc,yc); inmask=(YC>=ysurf)&(YC<ysurf+tm)
        for (x0,x1,y0,y1) in geom['traces']:
            inmask|=(XC>=x0-tm)&(XC<=x1+tm)&(YC>=y0)&(YC<=y1+tm)
        tr=np.zeros_like(inmask)
        for (x0,x1,y0,y1) in geom['traces']: tr|=(XC>x0)&(XC<x1)&(YC>y0)&(YC<y1)
        m=inmask&~tr&(er==1.0); er[m]=em; td[m]=0.0; mat[m]=99
    return nx,ny,er,td,mat,cond
def solve(nx,ny,epsc,cond,dx,volts):
    # epsc: cell permittivity (ny-1,nx-1). edge coefficient avg of adjacent cells
    idx=-np.ones((ny,nx),int); free=cond==0; idx[free]=np.arange(free.sum())
    V=np.zeros((ny,nx))
    for c,v in volts.items(): V[cond==c]=v
    ep=np.pad(epsc,1,mode='edge')  # (ny+1,nx+1), cell (j,i) -> ep[j+1,i+1]
    # horizontal edge between node (j,i)-(j,i+1): cells (j-1,i),(j,i)
    eh=0.5*(ep[0:ny,1:nx]+ep[1:ny+1,1:nx])   # (ny, nx-1)
    ev=0.5*(ep[1:ny,0:nx]+ep[1:ny,1:nx+1])   # (ny-1, nx) vertical edge (j,i)-(j+1,i)
    # Neumann on left/right: no edge beyond; top boundary if no plane: Dirichlet 0 handled by cond? use Neumann-free with far top -> set top row Dirichlet 0
    fi=idx.ravel(); Vf=V.ravel(); n=int(free.sum())
    N=np.arange(ny*nx).reshape(ny,nx)
    pa=np.concatenate([N[:,:-1].ravel(),N[:-1,:].ravel()]); pb=np.concatenate([N[:,1:].ravel(),N[1:,:].ravel()])
    w=np.concatenate([eh.ravel(),ev.ravel()])
    ia=fi[pa]; ib=fi[pb]
    diag=np.bincount(ia[ia>=0],weights=w[ia>=0],minlength=n)+np.bincount(ib[ib>=0],weights=w[ib>=0],minlength=n)
    both=(ia>=0)&(ib>=0)
    rows=np.concatenate([ia[both],ib[both]]); cols=np.concatenate([ib[both],ia[both]]); vals=-np.concatenate([w[both],w[both]])
    b=np.bincount(ia[(ia>=0)&(ib<0)],weights=(w*Vf[pb])[(ia>=0)&(ib<0)],minlength=n)+np.bincount(ib[(ib>=0)&(ia<0)],weights=(w*Vf[pa])[(ib>=0)&(ia<0)],minlength=n)
    A=sp.coo_matrix((vals,(rows,cols)),shape=(n,n)).tocsr()+sp.diags(diag)
    V[free]=spl.spsolve(A.tocsc(),b)
    # charges per conductor node: sum of fluxes to free neighbours
    q=np.zeros((ny,nx))
    fh=eh*(V[:,:-1]-V[:,1:]); fv=ev*(V[:-1,:]-V[1:,:])
    q[:,:-1]+=fh; q[:,1:]-=fh; q[:-1,:]+=fv; q[1:,:]-=fv
    q*=EPS0   # per unit length (dx cancels in 2D uniform grid)
    return V,q,eh,ev
def pair(geom,dx=0.005,freqs=(1.25e9,2.5e9,3.125e9),rq_um=1.0,single=False):
    nx,ny,er,td,mat,cond=build(geom,dx)
    if geom.get('top_open'): cond[-1,:]=-1  # far lid
    ones=np.ones_like(er); out={}
    modes={'odd':{1:1.0,2:-1.0,-1:0.0},'even':{1:1.0,2:1.0,-1:0.0}} if not single else {'se':{1:1.0,-1:0.0}}
    for mname,vv in modes.items():
        V,q,eh,ev=solve(nx,ny,er,cond,dx,vv); Q=q[cond==1].sum()
        V0,q0,_,_=solve(nx,ny,ones,cond,dx,vv); Q0=q0[cond==1].sum()
        Z=1/(C0*math.sqrt(Q*Q0)); eeff=Q/Q0
        # dielectric energy fractions: cell field
        Vc=V; Ex=(Vc[:-1,1:]+Vc[1:,1:]-Vc[:-1,:-1]-Vc[1:,:-1])/(2*dx*1e-3); Ey=(Vc[1:,:-1]+Vc[1:,1:]-Vc[:-1,:-1]-Vc[:-1,1:])/(2*dx*1e-3)
        W=er*(Ex**2+Ey**2); tand_eff=float((W*td).sum()/W.sum())
        # conductor: rho_s ~ q0/(dx) on boundary nodes (vacuum problem), per conductor; integral rho^2 dl = sum q0^2/dx
        dl=dx*1e-3; s2=float((q0[cond!=0]**2).sum()/dl)
        res={'Z':Z,'eeff':eeff,'tand_eff':tand_eff,'loss_dB_per_mm':{}}
        for f in freqs:
            Rs=math.sqrt(math.pi*f*MU0/SIGMA_CU); delta=1/math.sqrt(math.pi*f*MU0*SIGMA_CU)
            Kr=1+2/math.pi*math.atan(1.4*(rq_um*1e-6/delta)**2)
            nlines=len([c for c in vv if c>0 and vv[c]!=0])
            # P_loss=1/2 Rs sum|Js|^2 ; Js=c*rho0 ; P_tx=nlines*1/2*V*I, I=c*Q0 per line (V=1)
            # R per line = Rs*Kr*sum(rho0^2)/(nlines*Q0^2) (current follows vacuum charge distribution); alpha=R/(2*Z_mode)
            Rline=Rs*Kr*s2/(nlines*Q0**2); ac=Rline/(2*Z)  # Np/m
            ad=math.pi*f/C0*math.sqrt(eeff)*tand_eff
            res['loss_dB_per_mm'][f"{f/1e9:g}"]=round(8.686*(ac+ad)/1000,5)
            res.setdefault('split',{})[f"{f/1e9:g}"]=dict(cond=round(8.686*ac/1000,5),diel=round(8.686*ad/1000,5),Kr=round(Kr,2))
        out[mname]=res
    if single: return dict(Z0=out['se']['Z'],eeff=out['se']['eeff'])
    return dict(Zdiff=2*out['odd']['Z'],Zodd=out['odd']['Z'],Zeven=out['even']['Z'],Zcm=out['even']['Z']/2,eeff_odd=out['odd']['eeff'],tand_eff=out['odd']['tand_eff'],
                loss_diff_dB_per_mm=out['odd']['loss_dB_per_mm'],split=out['odd']['split'])
def microstrip(w,s,h,er,tand,t=0.035,mask=(0.015,3.8),margin=1.2,air=1.2,single=False):
    W=2*margin+(w if single else 2*w+s); H=h+t+air
    x0=margin; tr=[(x0,x0+w,h,h+t)] + ([] if single else [(x0+w+s,x0+2*w+s,h,h+t)])
    g=dict(W=W,H=H,diel=[(0,h,er,tand)],traces=tr,mask=(mask[0],mask[1],h) if mask else None,top_open=True)
    return g
def stripline(w,s,h_below,h_above,er,tand,t=0.0152,margin=1.2,er_above=None,tand_above=None,single=False):
    W=2*margin+(w if single else 2*w+s); H=h_below+t+h_above
    x0=margin; tr=[(x0,x0+w,h_below,h_below+t)] + ([] if single else [(x0+w+s,x0+2*w+s,h_below,h_below+t)])
    ea=er_above or er; ta=tand_above if tand_above is not None else tand
    g=dict(W=W,H=H,diel=[(0,h_below,er,tand),(h_below,H,ea,ta)],traces=tr,top_plane=True)
    return g
if __name__=='__main__':
    # validation: microstrip w/h=1.9, er=4.4, t~0, no mask -> Hammerstad-Jensen ~50 ohm
    g=microstrip(0.304,0,0.16,4.4,0.0,t=0.005,mask=None,margin=1.5,air=2.0,single=True)
    print('microstrip w=0.304 h=0.16 er4.4 t=5um:',pair(g,dx=0.005,single=True))
    # symmetric stripline b=0.5 w=0.15 er=4 t~0 : Cohn Z0 = 30pi/sqrt(er) * K(k')/K(k) ~
    g=stripline(0.15,0,0.25,0.25,4.0,0.0,t=0.005,margin=1.5,single=True)
    print('stripline w=0.15 b=0.5 er4:',pair(g,dx=0.005,single=True))
