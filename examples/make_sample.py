# -*- coding: utf-8 -*-
"""
Generate a synthetic sample pair (reference.csv / under_test.csv) with known, seeded differences.
No real project data. Used by the tests and for trying "Compare Models" without Revit models.

    python examples/make_sample.py            # writes examples/sample/*.csv
"""
import csv
import io
import os

HEADER = ["ElementId", "UniqueId", "CatKey", "Category", "Family", "Type", "Level", "SystemClassification",
          "SystemType", "SystemName", "Size", "Diameter_mm", "Width_mm", "Height_mm", "MiddleElev_mm", "Length_mm",
          "GeomKind", "X1", "Y1", "Z1", "X2", "Y2", "Z2", "SX1", "SY1", "SZ1", "SX2", "SY2", "SZ2",
          "BBMinX", "BBMinY", "BBMinZ", "BBMaxX", "BBMaxY", "BBMaxZ"]
LEVELS = [("1F", 0.0), ("2F", 4000.0), ("3F", 8000.0)]


class Model(object):
    def __init__(self, start_id):
        self.rows = []
        self.next = start_id

    def _id(self):
        self.next += 1
        return self.next

    def seg(self, catkey, cat, fam, level, system, size, w, h, a, b):
        i = self._id()
        L = sum((a[k] - b[k]) ** 2 for k in range(3)) ** 0.5
        hw, hh = w / 2.0, h / 2.0
        self.rows.append(dict(
            ElementId=i, UniqueId="u-%d" % i, CatKey=catkey, Category=cat, Family=fam, Type="Standard",
            Level=level, SystemType=system, Size=size, Width_mm=w, Height_mm=h, Length_mm=round(L, 1),
            GeomKind="Curve", X1=a[0], Y1=a[1], Z1=a[2], X2=b[0], Y2=b[1], Z2=b[2],
            BBMinX=min(a[0], b[0]) - hw, BBMinY=min(a[1], b[1]) - hw, BBMinZ=min(a[2], b[2]) - hh,
            BBMaxX=max(a[0], b[0]) + hw, BBMaxY=max(a[1], b[1]) + hw, BBMaxZ=max(a[2], b[2]) + hh))
        return i

    def comp(self, catkey, cat, fam, level, system, size, p, r=300.0):
        i = self._id()
        self.rows.append(dict(
            ElementId=i, UniqueId="u-%d" % i, CatKey=catkey, Category=cat, Family=fam, Type="Standard",
            Level=level, SystemType=system, Size=size, GeomKind="Point", X1=p[0], Y1=p[1], Z1=p[2],
            BBMinX=p[0] - r, BBMinY=p[1] - r, BBMinZ=p[2] - r, BBMaxX=p[0] + r, BBMaxY=p[1] + r, BBMaxZ=p[2] + r))
        return i


def build(m, variant):
    """variant='ref' or 'test'. The test model carries the seeded differences listed in EXPECTED."""
    t = variant == 'test'
    for lv, z0 in LEVELS:
        z = z0 + 3000.0
        # --- duct main along X with two branches ---
        xs = [0, 6000, 12000, 18000]
        for k in range(3):
            a, b = (xs[k] + 300, 0, z), (xs[k + 1] - 300, 0, z)
            if t and lv == "2F" and k == 1:
                b = (b[0] + 55, 0, z)                 # break offset: segment end differs by 55 mm
            if t and lv == "3F" and k == 0:
                a, b = (a[0], 15, z), (b[0], 15, z)   # minor offset: 15 mm
            m.seg("OST_DuctCurves", "Ducts", "Rectangular Duct", lv, "Exhaust Air", "800x400", 800, 400, a, b)
        for k, x in enumerate(xs[1:3]):
            fam = "Rectangular Tee"
            p = (x, 0, z)
            if t and lv == "1F" and k == 0:
                p = (x + 350, 0, z)                   # moved: tee placed 350 mm away
            m.comp("OST_DuctFitting", "Duct Fittings", fam, lv, "Exhaust Air", "800x400-800x400-400x300", p)
            m.seg("OST_DuctCurves", "Ducts", "Rectangular Duct", lv, "Exhaust Air", "400x300", 400, 300,
                  (x, 300, z), (x, 4000, z))
        if not (t and lv == "2F"):                    # missing: reducer at the end of the 2F main
            m.comp("OST_DuctFitting", "Duct Fittings", "Rectangular Transition", lv, "Exhaust Air",
                   "800x400-600x400", (18000, 0, z))
        size = "600x400-400ø" if not (t and lv == "3F") else "600x400-300ø"   # size mismatch on 3F
        m.comp("OST_DuctFitting", "Duct Fittings", "Rectangular to Round Transition", lv, "Exhaust Air", size,
               (18500, 0, z))
        # --- pipe run ---
        zp = z - 600
        for k in range(4):
            m.seg("OST_PipeCurves", "Pipes", "Pipe Types", lv, "Domestic Cold Water", "50", 60, 60,
                  (k * 5000 + 100, 2000, zp), (k * 5000 + 4900, 2000, zp))
            if k < 3:
                fam = "Elbow - Generic" if not (t and lv == "1F" and k == 2) else "PLUGIN_elbow_7f3a"  # non-reference family
                m.comp("OST_PipeFitting", "Pipe Fittings", fam, lv, "Domestic Cold Water", "50-50",
                       ((k + 1) * 5000, 2000, zp), r=60)
        # --- cable tray ---
        zt = z + 500
        for k in range(2):
            m.seg("OST_CableTray", "Cable Trays", "Ladder Tray", lv, "Power", "300x100", 300, 100,
                  (k * 6000, -1500, zt), ((k + 1) * 6000, -1500, zt))
    if t:                                             # extra: one duct the reference does not have
        m.seg("OST_DuctCurves", "Ducts", "Rectangular Duct", "1F", "Exhaust Air", "400x300", 400, 300,
              (24000, 0, 3000), (28000, 0, 3000))


EXPECTED = {
    'seg_status': {u'斷點差異': 1, u'位置偏差': 1, u'多出': 1},
    'comp_status': {u'位置不同': 1, u'缺漏': 1, u'尺寸不符': 1},
    'test_custom': 1,
}


def write(path, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=HEADER, lineterminator="\r\n")
    w.writeheader()
    for r in rows:
        w.writerow(dict((k, r.get(k, "")) for k in HEADER))
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(buf.getvalue())


def main(out_dir=None):
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    ref, test = Model(100000), Model(500000)
    build(ref, 'ref')
    build(test, 'test')
    write(os.path.join(out_dir, "reference.csv"), ref.rows)
    write(os.path.join(out_dir, "under_test.csv"), test.rows)
    return out_dir


if __name__ == "__main__":
    print("written to", main())
