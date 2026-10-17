"""TASK-5553: koji JTAG upisi u CC_SERDES regfile se vide u readbacku.
Za svaki 'set F=v' (calib_aba / eeqa / link_gate) usporedi trazenu vrijednost s readbackom iz iste naredbe
(eyescan.py cmd_set ispisuje rd_fields odmah nakon wr_fields). W/C polja (*_RESET, *_CALIB_EN) se preskacu: readback 0 je ocekivan."""
import json, os, re, collections
D = os.path.dirname(os.path.abspath(__file__))
SRC = ['aba2.jsonl', 'eeqa.jsonl',
       '../../data_20261016/t5542/calib/k12a.jsonl', '../t5542_chain4/gate/k3r_2.jsonl']
ADDR = {}
for l in open(os.path.join(D, '../../../tools/serdestool.py')):
    m = re.match(r"\s+'([A-Z0-9_\[\]]+)':\s+\{'addr': (0x[0-9A-F]+), 'mode': '([^']+)', 'hbit':\s+(\d+), 'lbit':\s+(\d+)", l)
    if m: ADDR[m[1]] = (int(m[2], 16), m[3], int(m[4]), int(m[5]))
import ast
_src = open(os.path.join(D, '../../../tools/lab/calib_aba.py')).read()
_plan = ast.literal_eval(_src[_src.index('PLAN = [') + 7:_src.index(']', _src.index('PLAN = [')) + 1])
PLAN = {name: cmd for _, name, _, cmd in _plan}   # calib_aba 'act' zapis nema 'cmd', samo 'name'
WC = {k for k, v in ADDR.items() if v[1] == 'W/C'}
stat = collections.defaultdict(lambda: [0, 0, set()])   # field -> [ok, fail, examples]
EQARST = ['RX_EQA_RESET_OVR=1 RX_EQA_RESET=1', 'RX_EQA_RESET_OVR=0 RX_EQA_RESET=0']
def expand(cmd):
    out = []
    for part in cmd.split(';'):
        part = part.strip()
        if part == 'eqarst': out += EQARST
        elif part and part.split()[0] not in ('freeze', 'restore', 'recal', '-'): out.append(part)
    return out
for s in SRC:
    p = os.path.join(D, s)
    if not os.path.exists(p): continue
    for line in open(p):
        d = json.loads(line)
        cmds, acts = [], []
        cmd = d.get('cmd') or (PLAN.get(d.get('name')) if d.get('kind') == 'act' else None)
        if d.get('kind') in ('act', 'step') and cmd and cmd != '-':
            cmds = expand(cmd)
            for b in ('gs', 'm2'):
                a = [x.split(':', 1)[1] for x in d.get('act', []) if x.startswith(b + ':')]
                acts.append((b, a))
        elif isinstance(d.get('action'), dict) and d['action'].get('level') in ('L1', 'L1b'):
            f = 'RX_EQA_RESET' if d['action']['level'] == 'L1' else 'RX_RESET'
            cmds = ['%s_OVR=1 %s=1' % (f, f), '%s_OVR=0 %s=0' % (f, f)]
            acts = list(d['action']['out'].items())
        for b, a in acts:
            for c, r in zip(cmds, a):
                want = dict(kv.split('=') for kv in c.split())
                got = dict(kv.split('=') for kv in r.split() if '=' in kv and not kv.startswith('board='))
                for k, v in want.items():
                    if k in WC or k not in got: continue
                    ok = int(v, 0) == int(got[k])
                    st = stat[k]; st[0 if ok else 1] += 1
                    if not ok: st[2].add('%s->%s' % (v, got[k]))
print('polje | adresa[bitovi] | readback = upis | readback != upis | primjeri (upis->readback)')
for k in sorted(stat, key=lambda k: ADDR.get(k, (999,))[0]):
    a = ADDR.get(k, (0, '?', 0, 0))
    ok, bad, ex = stat[k]
    print(f'{k} | 0x{a[0]:02X}[{a[2]}:{a[3]}] | {ok} | {bad} | {", ".join(sorted(ex)[:4])}')
