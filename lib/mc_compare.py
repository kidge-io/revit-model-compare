# -*- coding: utf-8 -*-
"""
ModelCompare core: geometric comparison of two MEP model exports.

Pure Python, runs on IronPython 2.7 (pyRevit default engine) and CPython 3.
Input : two CSVs produced by the "Export MEP" button (reference model, model under test)
Output: comparison tables, issue list, shots.csv for the "Issue Shots" button, summary

Elements are matched by geometry, never by ElementId, so two independently built
models can be compared. Both models must share the same internal origin.

Internal status / group names are Traditional Chinese; mc_i18n.TR translates them.
"""
from __future__ import division

import codecs
import csv
import math
import os
import re

try:
    text_type = unicode  # noqa: F821  (IronPython / Py2)
except NameError:
    text_type = str

__version__ = '1.0.0'

TOL = 50.0          # position tolerance, mm
EXACT = 5.0         # "match" threshold, mm
FIT_NEAR = 1000.0   # second pass: same-type component within 1 m counts as "moved"
SAMPLE = 200.0      # centerline coverage sampling step, mm
NO_SYSTEM = u'(無系統)'


# ---------------------------------------------------------------- I/O
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def read_export(path):
    f = codecs.open(path, 'r', 'utf-8-sig')
    try:
        lines = [l for l in f.read().splitlines() if l.strip()]
    finally:
        f.close()
    rows = list(csv.reader(lines))
    head = rows[0]
    out = []
    for r in rows[1:]:
        d = dict(zip(head, r))
        for k in ('X1', 'Y1', 'Z1', 'X2', 'Y2', 'Z2', 'BBMinX', 'BBMinY', 'BBMinZ', 'BBMaxX', 'BBMaxY', 'BBMaxZ',
                  'Length_mm'):
            d[k] = _num(d.get(k))
        d['ElementId'] = int(float(d['ElementId']))
        out.append(d)
    return out


def write_csv(path, header, rows):
    f = codecs.open(path, 'w', 'utf-8-sig')
    try:
        def cell(v):
            if v is None:
                return u''
            if isinstance(v, float):
                v = round(v, 1)
            s = text_type(v)
            if any(c in s for c in u',"\n\r'):
                s = u'"' + s.replace(u'"', u'""') + u'"'
            return s
        f.write(u','.join(cell(h) for h in header) + u'\r\n')
        for r in rows:
            f.write(u','.join(cell(r.get(h)) for h in header) + u'\r\n')
    finally:
        f.close()


# ---------------------------------------------------------------- geometry
def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a):
    return math.sqrt(dot(a, a))


def dist(a, b):
    return norm(sub(a, b))


def mid(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0)


class Grid(object):
    """Minimal uniform-grid spatial index."""

    def __init__(self, cell):
        self.cell = float(cell)
        self.d = {}

    def key(self, p):
        c = self.cell
        return (int(math.floor(p[0] / c)), int(math.floor(p[1] / c)), int(math.floor(p[2] / c)))

    def add_point(self, p, item):
        self.d.setdefault(self.key(p), []).append(item)

    def add_box(self, lo, hi, item):
        a, b = self.key(lo), self.key(hi)
        for i in range(a[0], b[0] + 1):
            for j in range(a[1], b[1] + 1):
                for k in range(a[2], b[2] + 1):
                    self.d.setdefault((i, j, k), []).append(item)

    def near(self, p, r):
        a = self.key((p[0] - r, p[1] - r, p[2] - r))
        b = self.key((p[0] + r, p[1] + r, p[2] + r))
        seen = set()
        for i in range(a[0], b[0] + 1):
            for j in range(a[1], b[1] + 1):
                for k in range(a[2], b[2] + 1):
                    for it in self.d.get((i, j, k), ()):
                        if it not in seen:
                            seen.add(it)
                            yield it


# ---------------------------------------------------------------- classification
DISC_BY_CAT = {
    'OST_DuctCurves': 'Duct', 'OST_DuctFitting': 'Duct', 'OST_DuctAccessory': 'Duct',
    'OST_FlexDuctCurves': 'Duct', 'OST_DuctTerminal': 'Duct',
    'OST_PipeCurves': 'Pipe', 'OST_PipeFitting': 'Pipe', 'OST_PipeAccessory': 'Pipe',
    'OST_FlexPipeCurves': 'Pipe', 'OST_Sprinklers': 'Pipe', 'OST_PlumbingFixtures': 'Pipe',
    'OST_CableTray': 'CableTray', 'OST_CableTrayFitting': 'CableTray',
    'OST_Conduit': 'Conduit', 'OST_ConduitFitting': 'Conduit',
    'OST_MechanicalEquipment': 'Equipment', 'OST_ElectricalEquipment': 'Equipment',
    'OST_LightingFixtures': 'Equipment',
}
_DISC_GUESS = [  # older exports without CatKey: guess from the (localized) category name
    (u'電纜架|cable tray', 'CableTray'), (u'導線管|線管|conduit', 'Conduit'),
    (u'風管|風口|duct|air terminal', 'Duct'),
    (u'管|撒水|灑水|衛浴|pipe|sprinkler|plumbing', 'Pipe'),
    (u'設備|燈具|equipment|lighting', 'Equipment'),
]


def discipline(r):
    k = r.get('CatKey')
    if k in DISC_BY_CAT:
        return DISC_BY_CAT[k]
    c = text_type(r.get('Category') or u'')
    for pat, d in _DISC_GUESS:
        if re.search(pat, c, re.I):
            return d
    return 'Other'


def kind(fam, catkey=None):
    f = text_type(fam or u'')
    if re.search(u'三通|tee|wye', f, re.I):
        return u'三通'
    if re.search(u'四通|cross', f, re.I):
        return u'四通'
    if re.search(u'彎頭|elbow|bend', f, re.I):
        return u'彎頭'
    if re.search(u'大小頭|轉接頭|異徑|transition|reducer', f, re.I):
        return u'大小頭/轉接頭'
    if re.search(u'管帽|端蓋|cap', f, re.I):
        return u'管帽'
    if re.search(u'接頭|套管|coupling|union', f, re.I):
        return u'接頭'
    if re.search(u'風門|閥|damper|valve', f, re.I):
        return u'風門/閥'
    if catkey in ('OST_DuctTerminal',):
        return u'風口'
    if catkey in ('OST_Sprinklers',):
        return u'撒水頭'
    if catkey in ('OST_MechanicalEquipment', 'OST_ElectricalEquipment', 'OST_PlumbingFixtures',
                  'OST_LightingFixtures'):
        return u'設備'
    if re.search(u'風管|管|duct|pipe|tray|conduit', f, re.I):
        return u'管段'
    return u'其他'


def is_linear(r):
    return r.get('GeomKind') == u'Curve' and r.get('X2') is not None


def p1(r):
    return (r['X1'], r['Y1'], r['Z1'])


def p2(r):
    return (r['X2'], r['Y2'], r['Z2'])


def floor_of(z, levels, fallback):
    """Floor by actual elevation; levels = [(name, elevation_mm)], low to high."""
    if not levels or z is None:
        return fallback
    name = levels[0][0]
    for n, e in levels:
        if z + 100 >= e:
            name = n
    return name


def short_level(lv):
    return text_type(lv or u'').split(u'、')[0]


def system_of(r):
    return r.get('SystemType') or NO_SYSTEM


# ---------------------------------------------------------------- comparison
def compare(owner, ai, levels=None, systems=None, disciplines=None, log=None):
    """owner = reference model rows, ai = model-under-test rows."""
    say = log or (lambda m: None)
    for r in owner + ai:
        r['Disc'] = discipline(r)
    if disciplines:
        owner = [r for r in owner if r['Disc'] in disciplines]
        ai = [r for r in ai if r['Disc'] in disciplines]
    if systems:
        owner = [r for r in owner if system_of(r) in systems]
        ai = [r for r in ai if system_of(r) in systems]
    owner_fams = set(r.get('Family') for r in owner)
    for r in owner + ai:
        r['Kind'] = kind(r.get('Family'), r.get('CatKey'))
        r['Floor'] = floor_of(r.get('BBMinZ'), levels, short_level(r.get('Level')))

    od = [r for r in owner if is_linear(r)]
    ad = [r for r in ai if is_linear(r)]
    of = [r for r in owner if not is_linear(r) and r.get('X1') is not None]
    af = [r for r in ai if not is_linear(r) and r.get('X1') is not None]
    say(u'reference: %d segments, %d components; test: %d segments, %d components'
        % (len(od), len(of), len(ad), len(af)))

    # ---------- segments, pass 1: both endpoints, direction-agnostic ----------
    g = Grid(1000.0)
    for j, r in enumerate(ad):
        g.add_point(mid(p1(r), p2(r)), j)
    seg_res, used = [], set()
    R = max(TOL * 4, 200.0)
    for r in od:
        a1, a2 = p1(r), p2(r)
        m = mid(a1, a2)
        best, bestd = None, 1e18
        for j in g.near(m, R):
            if j in used:
                continue
            q = ad[j]
            if q['Disc'] != r['Disc'] or dist(m, mid(p1(q), p2(q))) > R:
                continue
            d1 = max(dist(a1, p1(q)), dist(a2, p2(q)))
            d2 = max(dist(a1, p2(q)), dist(a2, p1(q)))
            dd = min(d1, d2)
            if dd < bestd:
                best, bestd = j, dd
        rec = dict(owner_id=r['ElementId'], owner_size=r.get('Size'), owner_family=r.get('Family'),
                   disc=r['Disc'], category=r.get('Category'), system=system_of(r),
                   floor=r['Floor'], level=r.get('Level'), length=r.get('Length_mm'),
                   x=m[0], y=m[1], z=m[2], kind=u'管段', minz=r.get('BBMinZ'))
        if best is not None and bestd <= TOL:
            used.add(best)
            q = ad[best]
            size_ok = text_type(r.get('Size')) == text_type(q.get('Size'))
            st = u'一致' if (size_ok and bestd <= EXACT) else (u'尺寸不符' if not size_ok else u'位置偏差')
            rev = (dist(a1, p2(q)) + dist(a2, p1(q))) < (dist(a1, p1(q)) + dist(a2, p2(q)))
            rec.update(status=st, ai_id=q['ElementId'], ai_size=q.get('Size'), ai_family=q.get('Family'),
                       dev_mm=bestd, reversed=rev)
        else:
            rec.update(status=u'缺漏')
        seg_res.append(rec)
    for j, q in enumerate(ad):
        if j not in used:
            m = mid(p1(q), p2(q))
            seg_res.append(dict(status=u'多出', ai_id=q['ElementId'], ai_size=q.get('Size'),
                                ai_family=q.get('Family'), disc=q['Disc'], category=q.get('Category'),
                                system=system_of(q), floor=q['Floor'], level=q.get('Level'),
                                length=q.get('Length_mm'), x=m[0], y=m[1], z=m[2], kind=u'管段',
                                minz=q.get('BBMinZ')))

    # ---------- segments, pass 2: same centerline & size, different break points ----------
    o_by = dict((r['ElementId'], r) for r in od)
    a_by = dict((r['ElementId'], r) for r in ad)

    def relation(r, q):
        u = sub(p2(r), p1(r))
        L = norm(u)
        w = sub(p2(q), p1(q))
        Lw = norm(w)
        if L == 0 or Lw == 0:
            return 0, 1e9
        u = mul(u, 1.0 / L)
        if abs(dot(u, mul(w, 1.0 / Lw))) < 0.999:
            return 0, 1e9
        perp = 0.0
        for pt in (p1(q), p2(q)):
            v = sub(pt, p1(r))
            perp = max(perp, norm(sub(v, mul(u, dot(v, u)))))
        t1, t2 = sorted([dot(sub(p1(q), p1(r)), u), dot(sub(p2(q), p1(r)), u)])
        ov = max(0.0, min(L, t2) - max(0.0, t1))
        return ov / max(L, Lw), perp

    miss = [x for x in seg_res if x['status'] == u'缺漏']
    extra = [x for x in seg_res if x['status'] == u'多出']
    taken = set()
    for mrec in miss:
        r = o_by[mrec['owner_id']]
        best = None
        for k, xrec in enumerate(extra):
            if k in taken or xrec.get('ai_size') != mrec.get('owner_size') or xrec['disc'] != mrec['disc']:
                continue
            q = a_by[xrec['ai_id']]
            ratio, perp = relation(r, q)
            if perp <= TOL and ratio >= 0.5 and (best is None or ratio > best[1]):
                best = (k, ratio, q)
        if best:
            k, ratio, q = best
            taken.add(k)
            a1, a2 = p1(r), p2(r)
            dev = min(max(dist(a1, p1(q)), dist(a2, p2(q))), max(dist(a1, p2(q)), dist(a2, p1(q))))
            mrec.update(status=u'斷點差異', ai_id=q['ElementId'], ai_size=q.get('Size'),
                        ai_family=q.get('Family'), dev_mm=dev,
                        len_diff_mm=(q.get('Length_mm') or 0) - (r.get('Length_mm') or 0))
    drop = set(id(extra[k]) for k in taken)
    seg_res = [x for x in seg_res if id(x) not in drop]

    # ---------- centerline coverage (independent of how runs are split) ----------
    def coverage(src, ref):
        gg = Grid(2000.0)
        for j, q in enumerate(ref):
            a, b = p1(q), p2(q)
            lo = (min(a[0], b[0]) - TOL, min(a[1], b[1]) - TOL, min(a[2], b[2]) - TOL)
            hi = (max(a[0], b[0]) + TOL, max(a[1], b[1]) + TOL, max(a[2], b[2]) + TOL)
            gg.add_box(lo, hi, j)
        res = {}
        for r in src:
            t = res.setdefault(r['Disc'], [0.0, 0.0, 0.0])
            a, b = p1(r), p2(r)
            v = sub(b, a)
            L = norm(v)
            n = max(int(L // SAMPLE), 1)
            for i in range(n):
                p = add(a, mul(v, (i + 0.5) / n))
                t[0] += L / n
                hit = hit_same = False
                for j in gg.d.get(gg.key(p), ()):
                    q = ref[j]
                    if q['Disc'] != r['Disc']:
                        continue
                    w = sub(p2(q), p1(q))
                    ll = dot(w, w)
                    if ll == 0:
                        continue
                    s = max(0.0, min(1.0, dot(sub(p, p1(q)), w) / ll))
                    if dist(p, add(p1(q), mul(w, s))) <= TOL:
                        hit = True
                        if q.get('Size') == r.get('Size'):
                            hit_same = True
                            break
                if hit:
                    t[1] += L / n
                if hit_same:
                    t[2] += L / n
        return res

    say(u'centerline coverage...')
    cov_o = coverage(od, ad)
    cov_a = coverage(ad, od)

    # ---------- components (point-based): insertion point ----------
    gf = Grid(500.0)
    for j, q in enumerate(af):
        gf.add_point(p1(q), j)
    pairs = []
    for i, r in enumerate(of):
        for j in gf.near(p1(r), TOL):
            if af[j]['Disc'] != r['Disc']:
                continue
            dd = dist(p1(r), p1(af[j]))
            if dd <= TOL:
                pairs.append((dd, i, j))
    pairs.sort()
    mo, ma, comp_res = set(), set(), []

    def crec(r, q, st, dd):
        base = r if r is not None else q
        p = p1(base)
        rec = dict(status=st, dev_mm=dd, x=p[0], y=p[1], z=p[2], floor=base['Floor'], level=base.get('Level'),
                   category=base.get('Category'), disc=base['Disc'], system=system_of(base),
                   minz=base.get('BBMinZ'))
        if r is not None:
            rec.update(owner_id=r['ElementId'], owner_kind=r['Kind'], owner_family=r.get('Family'),
                       owner_size=r.get('Size'))
        if q is not None:
            rec.update(ai_id=q['ElementId'], ai_kind=q['Kind'], ai_family=q.get('Family'), ai_size=q.get('Size'),
                       ai_custom=q.get('Family') not in owner_fams)
        return rec

    for dd, i, j in pairs:
        if i in mo or j in ma:
            continue
        mo.add(i)
        ma.add(j)
        r, q = of[i], af[j]
        if r['Kind'] != q['Kind']:
            st = u'類型不符'
        elif text_type(r.get('Size')) != text_type(q.get('Size')):
            st = u'尺寸不符'
        elif dd > EXACT:
            st = u'位置偏差'
        else:
            st = u'一致'
        comp_res.append(crec(r, q, st, dd))
    for i, r in enumerate(of):
        if i not in mo:
            comp_res.append(crec(r, None, u'缺漏', None))
    for j, q in enumerate(af):
        if j not in ma:
            comp_res.append(crec(None, q, u'多出', None))

    # ---------- components, pass 2: same type within 1 m ----------
    m_list = [x for x in comp_res if x['status'] == u'缺漏']
    x_list = [x for x in comp_res if x['status'] == u'多出']
    cand = []
    for mi, mrec in enumerate(m_list):
        pm = (mrec['x'], mrec['y'], mrec['z'])
        for xi, xrec in enumerate(x_list):
            if xrec.get('ai_kind') != mrec.get('owner_kind') or xrec['disc'] != mrec['disc']:
                continue
            dd = dist(pm, (xrec['x'], xrec['y'], xrec['z']))
            if dd <= FIT_NEAR:
                cand.append((dd, mi, xi))
    cand.sort()
    um, ux = set(), set()
    for dd, mi, xi in cand:
        if mi in um or xi in ux:
            continue
        um.add(mi)
        ux.add(xi)
        mrec, xrec = m_list[mi], x_list[xi]
        for k in ('ai_id', 'ai_kind', 'ai_family', 'ai_size', 'ai_custom'):
            mrec[k] = xrec.get(k)
        mrec['dev_mm'] = dd
        mrec['status'] = u'位置不同'
    drop = set(id(x_list[xi]) for xi in ux)
    comp_res = [x for x in comp_res if id(x) not in drop]

    def count(lst, disc=None):
        c = {}
        for x in lst:
            if disc is None or x['disc'] == disc:
                c[x['status']] = c.get(x['status'], 0) + 1
        return c

    discs = sorted(set(r['Disc'] for r in owner + ai))
    per_disc = {}
    for d in discs:
        co, ca = cov_o.get(d, [0.0, 0.0, 0.0]), cov_a.get(d, [0.0, 0.0, 0.0])
        per_disc[d] = dict(
            owner_segs=sum(1 for r in od if r['Disc'] == d), ai_segs=sum(1 for r in ad if r['Disc'] == d),
            owner_comps=sum(1 for r in of if r['Disc'] == d), ai_comps=sum(1 for r in af if r['Disc'] == d),
            seg_status=count(seg_res, d), comp_status=count(comp_res, d),
            owner_len_m=co[0] / 1000.0, cov_owner_pct=co[1] / co[0] * 100 if co[0] else 0,
            cov_owner_same_pct=co[2] / co[0] * 100 if co[0] else 0,
            ai_len_m=ca[0] / 1000.0, cov_ai_pct=ca[1] / ca[0] * 100 if ca[0] else 0,
        )
    tot = [sum(v[i] for v in cov_o.values()) for i in range(3)] if cov_o else [0.0, 0.0, 0.0]
    tota = [sum(v[i] for v in cov_a.values()) for i in range(3)] if cov_a else [0.0, 0.0, 0.0]
    summary = dict(
        owner_total=len(owner), ai_total=len(ai), owner_segs=len(od), ai_segs=len(ad),
        owner_comps=len(of), ai_comps=len(af),
        seg_status=count(seg_res), comp_status=count(comp_res),
        seg_reversed=sum(1 for x in seg_res if x.get('reversed')),
        owner_len_m=tot[0] / 1000.0, cov_owner_pct=tot[1] / tot[0] * 100 if tot[0] else 0,
        cov_owner_same_pct=tot[2] / tot[0] * 100 if tot[0] else 0,
        ai_len_m=tota[0] / 1000.0, cov_ai_pct=tota[1] / tota[0] * 100 if tota[0] else 0,
        ai_custom=sum(1 for r in ai if r.get('Family') not in owner_fams and not is_linear(r)),
        fam_owner=len(owner_fams), fam_ai=len(set(r.get('Family') for r in ai)),
        per_disc=per_disc,
    )
    return seg_res, comp_res, summary


# ---------------------------------------------------------------- screenshot list
SEG_GRP = {u'多出': u'多出管段', u'斷點差異': u'管段斷點差異', u'位置偏差': u'管段位置偏差', u'缺漏': u'缺漏管段',
           u'尺寸不符': u'管段尺寸不符'}
COMP_GRP = {u'缺漏': u'缺漏元件', u'多出': u'多出元件', u'尺寸不符': u'元件尺寸不符', u'位置不同': u'元件位置不同',
            u'類型不符': u'元件類型不符'}
QUOTA = [(u'元件尺寸不符', 6), (u'管段尺寸不符', 4), (u'元件類型不符', 4), (u'缺漏管段', 4), (u'多出管段', 4),
         (u'缺漏元件', 4), (u'非標準族群', 3), (u'多出元件', 3), (u'管段斷點差異', 2), (u'元件位置不同', 2),
         (u'管段位置偏差', 2)]


def issues_of(seg_res, comp_res):
    out = []
    for x in seg_res:
        g = SEG_GRP.get(x['status'])
        if g:
            y = dict(x)
            y['grp'] = g
            out.append(y)
    for x in comp_res:
        g = COMP_GRP.get(x['status'])
        if x.get('ai_custom') and x['status'] != u'尺寸不符':
            g = u'非標準族群'
        if g:
            y = dict(x)
            y['grp'] = g
            out.append(y)
    return out


def make_shots(issues, owner, ai, margin_xy=2500.0, margin_z=1200.0, link=6000.0):
    ob = dict((r['ElementId'], r) for r in owner)
    ab = dict((r['ElementId'], r) for r in ai)
    clusters = []
    for grp, quota in QUOTA:
        byfloor = {}
        for x in issues:
            if x['grp'] == grp:
                byfloor.setdefault(x['floor'], []).append(x)
        gc = []
        for floor, lst in byfloor.items():
            parent = list(range(len(lst)))

            def find(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i
            for i in range(len(lst)):
                for j in range(i + 1, len(lst)):
                    if dist((lst[i]['x'], lst[i]['y'], lst[i]['z']), (lst[j]['x'], lst[j]['y'], lst[j]['z'])) <= link:
                        parent[find(i)] = find(j)
            groups = {}
            for i in range(len(lst)):
                groups.setdefault(find(i), []).append(lst[i])
            for cl in groups.values():
                oids = [x['owner_id'] for x in cl if x.get('owner_id') is not None]
                aids = [x['ai_id'] for x in cl if x.get('ai_id') is not None]
                boxes = [ob[i] for i in oids if i in ob] + [ab[i] for i in aids if i in ab]
                boxes = [b for b in boxes if b.get('BBMinX') is not None]
                if not boxes:
                    continue
                lo = [min(b[k] for b in boxes) for k in ('BBMinX', 'BBMinY', 'BBMinZ')]
                hi = [max(b[k] for b in boxes) for k in ('BBMaxX', 'BBMaxY', 'BBMaxZ')]
                gc.append(dict(group=grp, floor=floor, n=len(cl), owner_ids=oids, ai_ids=aids,
                               minx=lo[0] - margin_xy, miny=lo[1] - margin_xy, minz=lo[2] - margin_z,
                               maxx=hi[0] + margin_xy, maxy=hi[1] + margin_xy, maxz=hi[2] + margin_z))
        # most issues first; on ties prefer floors not shot yet
        picked, floors = [], {}
        while gc and len(picked) < quota:
            gc.sort(key=lambda c: (-c['n'], floors.get(c['floor'], 0), c['floor']))
            c = gc.pop(0)
            floors[c['floor']] = floors.get(c['floor'], 0) + 1
            picked.append(c)
        clusters.extend(picked)
    for i, c in enumerate(clusters):
        c['shot_id'] = u'S%02d' % (i + 1)
        c['owner_ids'] = u';'.join(text_type(v) for v in c['owner_ids'])
        c['ai_ids'] = u';'.join(text_type(v) for v in c['ai_ids'])
    return clusters


SHOT_HEADER = ['shot_id', 'title', 'group', 'floor', 'n', 'minx', 'miny', 'minz', 'maxx', 'maxy', 'maxz',
               'owner_ids', 'ai_ids']


# ---------------------------------------------------------------- output
def _tr(v, L):
    if L == 'zh' or v is None:
        return v
    try:
        from mc_i18n import TR
    except ImportError:
        return v
    return TR.get(v, v)


DISC_NAME = {'zh': {'Duct': u'風管', 'Pipe': u'水管', 'CableTray': u'電纜架', 'Conduit': u'導線管',
                    'Equipment': u'設備', 'Other': u'其他'},
             'en': {'Duct': u'Duct', 'Pipe': u'Pipe', 'CableTray': u'Cable tray', 'Conduit': u'Conduit',
                    'Equipment': u'Equipment', 'Other': u'Other'}}


def summary_text(S, owner_name, ai_name, L='zh'):
    zh = L == 'zh'

    def T(v):
        return _tr(v, L)

    def pct(a, b):
        return u'%.1f%%' % (a * 100.0 / b) if b else u'-'

    def block(ss, total, keys, extra_key=u'多出'):
        out = []
        for k in keys:
            if ss.get(k):
                out.append(u'    %s %d%s' % (T(k), ss[k], u'' if k == extra_key else u' (%s)' % pct(ss[k], total)))
        return out

    lines = [
        (u'ModelCompare %s 比對摘要' if zh else u'ModelCompare %s summary') % __version__,
        (u'參考模型：%s' if zh else u'Reference model: %s') % owner_name,
        (u'受測模型：%s' if zh else u'Model under test: %s') % ai_name,
        u'',
        (u'元件數：參考 %d／受測 %d' if zh else u'Elements: reference %d / test %d') % (S['owner_total'], S['ai_total']),
        (u'中心線：參考 %.1f m，被受測模型以相同尺寸覆蓋 %.2f%%（任何尺寸 %.2f%%）' if zh else
         u'Centerline: reference %.1f m, covered by test model at same size %.2f%% (any size %.2f%%)')
        % (S['owner_len_m'], S['cov_owner_same_pct'], S['cov_owner_pct']),
        (u'受測模型管段總長 %.1f m，其中 %.2f%% 與參考模型重疊' if zh else
         u'Test model segment length %.1f m, %.2f%% overlaps the reference')
        % (S['ai_len_m'], S['cov_ai_pct']),
        (u'受測模型使用參考模型沒有的族群：%d 個元件（族群數 參考 %d／受測 %d）' if zh else
         u'Test-model components using families not in the reference: %d (families: reference %d / test %d)')
        % (S['ai_custom'], S['fam_owner'], S['fam_ai']),
    ]
    seg_keys = (u'一致', u'位置偏差', u'斷點差異', u'尺寸不符', u'缺漏', u'多出')
    comp_keys = (u'一致', u'位置偏差', u'位置不同', u'尺寸不符', u'類型不符', u'缺漏', u'多出')
    for d, P in sorted(S['per_disc'].items()):
        lines.append(u'')
        lines.append(u'[%s]' % DISC_NAME[L].get(d, d))
        if P['owner_segs'] or P['ai_segs']:
            lines.append((u'  管段（參考 %d、受測 %d），中心線覆蓋 %.1f%%：' if zh else
                          u'  Segments (reference %d, test %d), centerline coverage %.1f%%:')
                         % (P['owner_segs'], P['ai_segs'], P['cov_owner_same_pct']))
            lines += block(P['seg_status'], P['owner_segs'], seg_keys)
        if P['owner_comps'] or P['ai_comps']:
            lines.append((u'  元件（參考 %d、受測 %d）：' if zh else u'  Components (reference %d, test %d):')
                         % (P['owner_comps'], P['ai_comps']))
            lines += block(P['comp_status'], P['owner_comps'], comp_keys)
    lines.append(u'')
    lines.append((u'起訖方向相反的管段 %d 段（幾何相同，不算差異）' if zh else
                  u'%d segments drawn in reverse direction (same geometry, not counted)') % S['seg_reversed'])
    lines.append((u'判定：一致 ≤ %g mm；位置偏差 ≤ %g mm；位置不同＝同類型 %g m 內' if zh else
                  u'Rules: match <= %g mm; minor offset <= %g mm; moved = same type within %g m')
                 % (EXACT, TOL, FIT_NEAR / 1000.0))
    return u'\r\n'.join(lines)


DETAIL_HEADER = ['grp', 'disc', 'system', 'floor', 'level', 'owner_id', 'ai_id', 'dev_mm', 'owner_size', 'ai_size',
                 'owner_family', 'ai_family', 'x', 'y', 'z']
DETAIL_NAMES = {
    'zh': [u'差異類別', u'專業', u'系統', u'實際樓層', u'參考樓層', u'參考模型ElementId', u'受測模型ElementId',
           u'距離_mm', u'參考尺寸', u'受測尺寸', u'參考族群', u'受測族群', u'X_mm', u'Y_mm', u'Z_mm'],
    'en': [u'Issue', u'Discipline', u'System', u'Floor', u'Ref level', u'Reference ElementId', u'Test ElementId',
           u'Distance_mm', u'Reference size', u'Test size', u'Reference family', u'Test family',
           u'X_mm', u'Y_mm', u'Z_mm'],
}
FILES = {
    'zh': dict(segs=u'管段比對.csv', comps=u'元件比對.csv', detail=u'差異明細.csv', summary=u'比對摘要.txt',
               folder=u'比對結果_'),
    'en': dict(segs=u'Segments.csv', comps=u'Components.csv', detail=u'Issues.csv', summary=u'Summary.txt',
               folder=u'Results_'),
}


def _translated(rows, keys, L):
    out = []
    for r in rows:
        y = dict(r)
        for k in keys:
            y[k] = _tr(y.get(k), L)
        y['disc'] = DISC_NAME[L].get(y.get('disc'), y.get('disc'))
        out.append(y)
    return out


def run(owner_csv, ai_csv, out_dir, levels=None, systems=None, disciplines=None, log=None, L='zh'):
    owner = read_export(owner_csv)
    ai = read_export(ai_csv)
    seg_res, comp_res, S = compare(owner, ai, levels=levels, systems=systems, disciplines=disciplines, log=log)
    issues = issues_of(seg_res, comp_res)
    shots = make_shots(issues, owner, ai)
    F = FILES[L]

    sh = ['status', 'disc', 'system', 'owner_id', 'ai_id', 'dev_mm', 'owner_size', 'ai_size', 'owner_family',
          'ai_family', 'floor', 'level', 'length', 'len_diff_mm', 'reversed', 'x', 'y', 'z']
    write_csv(os.path.join(out_dir, F['segs']), sh, _translated(seg_res, ['status'], L))
    ch = ['status', 'disc', 'system', 'owner_id', 'ai_id', 'dev_mm', 'owner_kind', 'ai_kind', 'owner_family',
          'ai_family', 'owner_size', 'ai_size', 'ai_custom', 'floor', 'level', 'category', 'x', 'y', 'z']
    write_csv(os.path.join(out_dir, F['comps']), ch, _translated(comp_res, ['status', 'owner_kind', 'ai_kind'], L))
    names = DETAIL_NAMES[L]
    detail = []
    for x in _translated(issues, ['grp'], L):
        detail.append(dict(zip(names, [x.get(h) for h in DETAIL_HEADER])))
    write_csv(os.path.join(out_dir, F['detail']), names, detail)
    for c in shots:
        c['group'] = _tr(c['group'], L)
        c['title'] = u'%s %s %s (%d)' % (c['shot_id'], c['floor'], c['group'], c['n'])
    write_csv(os.path.join(out_dir, u'shots.csv'), SHOT_HEADER, shots)
    text = summary_text(S, os.path.basename(owner_csv), os.path.basename(ai_csv), L)
    f = codecs.open(os.path.join(out_dir, F['summary']), 'w', 'utf-8-sig')
    f.write(text)
    f.close()
    return S, len(issues), len(shots), text
