#!/usr/bin/env python3
"""Render a SerDes path from a .kicad_pcb to PNG (PIL only, no kicad-cli) - TASK-5524.

Background copper of the window is drawn dimmed (F.Cu red, B.Cu blue, pads grey); the chosen nets are drawn bright
(F.Cu: P red / N orange, B.Cu: P blue / N cyan), vias yellow, chosen footprints outlined with a label.
Used as a library by render_m2_gs_path.py (one call per picture):
    render(pcb, nets={'P': net, 'N': net, ...}, refs=[...], window=(x0,y0,x1,y1), out='x.png', ...)
"""
import math, re, collections
from PIL import Image, ImageDraw, ImageFont

TOK = re.compile(r'\s+|\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONTB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def parse(s):
    st = [[]]
    for m in TOK.finditer(s):
        t = m.group(0)
        if t[0].isspace():
            continue
        if t == '(':
            st.append([])
        elif t == ')':
            x = st.pop(); st[-1].append(x)
        else:
            st[-1].append(t[1:-1] if t[0] == '"' else t)
    return st[0][0]


def kids(n, k): return [c for c in n if isinstance(c, list) and c and c[0] == k]


def kid(n, k):
    r = kids(n, k); return r[0] if r else None


def arc_points(a, m, b, n=16):
    (ax, ay), (bx, by), (cx, cy) = a, m, b
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [a, b]
    ux = ((ax*ax+ay*ay)*(by-cy)+(bx*bx+by*by)*(cy-ay)+(cx*cx+cy*cy)*(ay-by))/d
    uy = ((ax*ax+ay*ay)*(cx-bx)+(bx*bx+by*by)*(ax-cx)+(cx*cx+cy*cy)*(bx-ax))/d
    r = math.dist((ux, uy), a)
    a1, am, a2 = (math.atan2(p[1]-uy, p[0]-ux) for p in (a, m, b))
    tw = lambda x: x % (2*math.pi)
    sw = tw(a2 - a1)
    if tw(am - a1) > sw:
        sw -= 2*math.pi
    return [(ux + r*math.cos(a1 + sw*i/n), uy + r*math.sin(a1 + sw*i/n)) for i in range(n+1)]


class Board:
    def __init__(self, path):
        self.root = parse(open(path).read())
        r = self.root
        self.netnames = {c[1]: c[2] for c in kids(r, 'net') if len(c) > 2}
        self.tracks = []   # (net, layer, width, [pts])
        for s in kids(r, 'segment') + kids(r, 'arc'):
            a = tuple(map(float, kid(s, 'start')[1:3])); b = tuple(map(float, kid(s, 'end')[1:3]))
            pts = arc_points(a, tuple(map(float, kid(s, 'mid')[1:3])), b) if s[0] == 'arc' else [a, b]
            self.tracks.append((self._net(s), kid(s, 'layer')[1], float(kid(s, 'width')[1]), pts))
        self.vias = [(self._net(v), tuple(map(float, kid(v, 'at')[1:3])), float(kid(v, 'size')[1]),
                      float(kid(v, 'drill')[1])) for v in kids(r, 'via')]
        self.fps = {}      # ref -> dict(at, rot, layer, value, lib, pads=[(name, net, layer-side, poly)])
        for fp in kids(r, 'footprint'):
            props = {p[1]: p[2] for p in kids(fp, 'property')}
            ref = props.get('Reference', '?')
            at = kid(fp, 'at'); fx, fy = float(at[1]), float(at[2]); rot = float(at[3]) if len(at) > 3 else 0.0
            side = kid(fp, 'layer')[1]
            pads = []
            for p in kids(fp, 'pad'):
                pa = kid(p, 'at'); px, py = float(pa[1]), float(pa[2]); prot = float(pa[3]) if len(pa) > 3 else rot
                rr = math.radians(-rot)
                cx, cy = fx + px*math.cos(rr) - py*math.sin(rr), fy + px*math.sin(rr) + py*math.cos(rr)
                sz = kid(p, 'size'); w, h = float(sz[1]), float(sz[2])
                lay = kid(p, 'layers'); lays = lay[1:] if lay else []
                pads.append(dict(name=p[1], net=self._net(p), shape=p[3], c=(cx, cy), w=w, h=h, rot=prot,
                                 layers=lays))
            attr = kid(fp, 'attr') or []
            self.fps[ref] = dict(at=(fx, fy), rot=rot, side=side, value=props.get('Value', ''), lib=fp[1],
                                 dnp='dnp' in attr, pads=pads, props=props)
        self.edges = []
        for g in r:
            if isinstance(g, list) and g and g[0] in ('gr_line', 'gr_arc') and kid(g, 'layer') and kid(g, 'layer')[1] == 'Edge.Cuts':
                a = tuple(map(float, kid(g, 'start')[1:3])); b = tuple(map(float, kid(g, 'end')[1:3]))
                self.edges.append(arc_points(a, tuple(map(float, kid(g, 'mid')[1:3])), b) if g[0] == 'gr_arc' else [a, b])

    def _net(self, n):
        k = kid(n, 'net')
        if not k:
            return None
        return k[2] if len(k) > 2 else self.netnames.get(k[1], k[1])


def pad_poly(p):
    w, h = p['w'], p['h']; a = math.radians(-p['rot']); cx, cy = p['c']
    return [(cx + x*math.cos(a) - y*math.sin(a), cy + x*math.sin(a) + y*math.cos(a))
            for x, y in ((-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2))]


COL = dict(bg=(18, 20, 24), Fdim=(95, 45, 45), Bdim=(40, 55, 90), pad=(110, 110, 100), edge=(230, 230, 230),
           FP=(255, 50, 50), FN=(255, 165, 0), BP=(60, 160, 255), BN=(60, 230, 210), via=(255, 230, 0),
           hl=(120, 255, 120), txt=(240, 240, 240), box=(0, 0, 0))


def wrap(lines, font, width):
    out = []
    for ln in lines:
        words = ln.split(' '); cur = ''
        for w in words:
            t = (cur + ' ' + w).strip()
            if font.getlength(t) <= width or not cur:
                cur = t
            else:
                out.append(cur); cur = '   ' + w
        out.append(cur)
    return out


def render(board, nets, refs, window, out, ppm=30, title='', notes=(), labels=(), panel_w=0, legend=True,
           notes_font=22):
    """nets: {'P': [net names], 'N': [net names]}; labels: [(x_mm, y_mm, text, dx_px, dy_px, colour)]"""
    x0, y0, x1, y1 = window
    W, H = int((x1-x0)*ppm), int((y1-y0)*ppm)
    fN = ImageFont.truetype(FONT, 20); fT = ImageFont.truetype(FONTB, 26); fNotes = ImageFont.truetype(FONT, notes_font)
    lh = notes_font + 8
    CW = max(W, panel_w)
    notes = wrap(list(notes), fNotes, CW - 20)
    head = 44
    foot = lh * len(notes) + 16
    img = Image.new('RGB', (max(W, panel_w), head + H + foot), COL['bg'])
    d = ImageDraw.Draw(img)
    T = lambda p: ((p[0]-x0)*ppm, head + (p[1]-y0)*ppm)
    role = {}
    for r_, ns in nets.items():
        for n in ns:
            role[n] = r_
    inwin = lambda p: x0-2 <= p[0] <= x1+2 and y0-2 <= p[1] <= y1+2
    # background copper, B first so F lies on top
    for lay, c in (('B.Cu', COL['Bdim']), ('F.Cu', COL['Fdim'])):
        for net, L, w, pts in board.tracks:
            if L == lay and net not in role and any(inwin(p) for p in pts):
                d.line([T(p) for p in pts], fill=c, width=max(1, int(w*ppm)))
    for ref, fp in board.fps.items():
        for p in fp['pads']:
            if inwin(p['c']) and p['net'] not in role:
                if p['shape'] == 'circle':
                    cx, cy = T(p['c']); r = p['w']*ppm/2; d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=COL['pad'])
                else:
                    d.polygon([T(q) for q in pad_poly(p)], fill=COL['pad'])
    for net, at, sz, dr in board.vias:
        if inwin(at) and net not in role:
            cx, cy = T(at); r = sz*ppm/2; d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(90, 90, 60))
    for e in board.edges:
        if any(inwin(p) for p in e):
            d.line([T(p) for p in e], fill=COL['edge'], width=2)
    # highlighted nets: B.Cu, then F.Cu
    for lay in ('B.Cu', 'F.Cu'):
        for net, L, w, pts in board.tracks:
            if L == lay and net in role:
                c = COL[lay[0] + role[net]]
                d.line([T(p) for p in pts], fill=c, width=max(3, int(w*ppm)))
                for p in pts:  # round joints
                    cx, cy = T(p); r = max(3, int(w*ppm))/2; d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=c)
    for ref, fp in board.fps.items():
        for p in fp['pads']:
            if p['net'] in role:
                c = COL['F' + role[p['net']]] if ref not in refs else COL['hl']
                if p['shape'] == 'circle':
                    cx, cy = T(p['c']); r = p['w']*ppm/2; d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=c)
                else:
                    d.polygon([T(q) for q in pad_poly(p)], fill=c)
    for ref in refs:
        fp = board.fps[ref]
        pts = [q for p in fp['pads'] for q in pad_poly(p)]
        xs = [T(q)[0] for q in pts]; ys = [T(q)[1] for q in pts]
        d.rectangle([min(xs)-4, min(ys)-4, max(xs)+4, max(ys)+4], outline=COL['hl'], width=2)
    for net, at, sz, dr in board.vias:
        if net in role:
            cx, cy = T(at); r = max(6, sz*ppm/2); rd = max(2, dr*ppm/2)
            d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=COL['via'], outline=(0, 0, 0))
            d.ellipse([cx-rd, cy-rd, cx+rd, cy+rd], fill=(0, 0, 0))
    for (lx, ly, text, dx, dy, colr) in labels:
        px, py = T((lx, ly)); tx, ty = px + dx, py + dy
        bb = d.multiline_textbbox((0, 0), text, font=fN)
        tx = min(max(tx, 6), CW - bb[2] - 8); ty = min(max(ty, head + 4), head + H - bb[3] - 6)
        d.line([(px, py), (tx, ty)], fill=colr, width=2)
        bb = d.multiline_textbbox((tx, ty), text, font=fN)
        d.rectangle([bb[0]-4, bb[1]-3, bb[2]+4, bb[3]+3], fill=COL['box'], outline=colr, width=2)
        d.multiline_text((tx, ty), text, fill=COL['txt'], font=fN)
    # scale bar 5 mm
    sb = 5*ppm; d.line([(14, head+H-18), (14+sb, head+H-18)], fill=COL['txt'], width=4)
    d.text((14, head+H-46), '5 mm', fill=COL['txt'], font=fN)
    if legend:
        lg = [('F.Cu P', COL['FP']), ('F.Cu N', COL['FN']), ('B.Cu P', COL['BP']), ('B.Cu N', COL['BN']),
              ('via', COL['via']), ('istaknuti dio', COL['hl'])]
        lx = W - 190; ly = head + 10
        d.rectangle([lx-8, ly-6, W-6, ly + 26*len(lg)], fill=COL['box'])
        for i, (t, c) in enumerate(lg):
            d.rectangle([lx, ly+i*26+4, lx+26, ly+i*26+18], fill=c); d.text((lx+34, ly+i*26), t, fill=COL['txt'], font=fN)
    d.text((10, 8), title, fill=COL['txt'], font=fT)
    for i, t in enumerate(notes):
        d.text((10, head + H + 8 + i*lh), t, fill=COL['txt'], font=fNotes)
    img.save(out)
    return out
