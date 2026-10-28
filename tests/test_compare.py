# -*- coding: utf-8 -*-
"""Tests for the comparison core (CPython). Run: python -m unittest discover -s tests"""
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lib'))
sys.path.insert(0, os.path.join(ROOT, 'examples'))

import make_sample  # noqa: E402
import mc_compare as M  # noqa: E402


def row(i, catkey, cat, fam, size, a, b=None):
    r = dict(ElementId=i, CatKey=catkey, Category=cat, Family=fam, Size=size, Level=u'1F', SystemType=u'S',
             GeomKind=u'Curve' if b else u'Point', X1=a[0], Y1=a[1], Z1=a[2],
             BBMinX=a[0] - 100, BBMinY=a[1] - 100, BBMinZ=a[2] - 100,
             BBMaxX=a[0] + 100, BBMaxY=a[1] + 100, BBMaxZ=a[2] + 100, Length_mm=None)
    if b:
        r.update(X2=b[0], Y2=b[1], Z2=b[2])
    else:
        r.update(X2=None, Y2=None, Z2=None)
    return r


class SampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        make_sample.main(cls.tmp)
        cls.ref = os.path.join(cls.tmp, 'reference.csv')
        cls.test = os.path.join(cls.tmp, 'under_test.csv')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def run_cmp(self, L):
        out = tempfile.mkdtemp(dir=self.tmp)
        S, n, s, text = M.run(self.ref, self.test, out, L=L)
        return S, n, s, text, out

    def test_seeded_differences_are_found(self):
        S = self.run_cmp('zh')[0]
        for k, v in make_sample.EXPECTED['seg_status'].items():
            self.assertEqual(S['seg_status'].get(k), v, k)
        for k, v in make_sample.EXPECTED['comp_status'].items():
            self.assertEqual(S['comp_status'].get(k), v, k)
        self.assertEqual(S['ai_custom'], make_sample.EXPECTED['ai_custom'])
        self.assertAlmostEqual(S['cov_owner_same_pct'], 100.0, places=3)

    def test_unchanged_disciplines_match_fully(self):
        S = self.run_cmp('en')[0]
        for d in ('Pipe', 'CableTray'):
            P = S['per_disc'][d]
            self.assertEqual(P['seg_status'], {u'一致': P['owner_segs']})

    def test_outputs_in_both_languages(self):
        for L in ('zh', 'en'):
            S, n, s, text, out = self.run_cmp(L)
            files = set(os.listdir(out))
            for f in M.FILES[L].values():
                if not f.endswith('_'):
                    self.assertIn(f, files)
            self.assertIn('shots.csv', files)
            self.assertGreater(s, 0)
            if L == 'en':
                self.assertIsNone(re.search(u'[一-鿿]', text.split('\r\n', 3)[3].replace(u'、', u'')),
                                  'English summary contains CJK text')


class RulesTest(unittest.TestCase):
    def test_disciplines_never_match_each_other(self):
        owner = [row(1, 'OST_DuctCurves', 'Ducts', 'Rect Duct', '400x300', (0, 0, 0), (3000, 0, 0))]
        ai = [row(2, 'OST_PipeCurves', 'Pipes', 'Pipe', '400x300', (0, 0, 0), (3000, 0, 0))]
        seg, comp, S = M.compare(owner, ai)
        self.assertEqual(sorted(x['status'] for x in seg), [u'多出', u'缺漏'])

    def test_reversed_segment_is_a_match(self):
        owner = [row(1, 'OST_DuctCurves', 'Ducts', 'Rect Duct', '400x300', (0, 0, 0), (3000, 0, 0))]
        ai = [row(2, 'OST_DuctCurves', 'Ducts', 'Rect Duct', '400x300', (3000, 0, 0), (0, 0, 0))]
        seg, comp, S = M.compare(owner, ai)
        self.assertEqual([x['status'] for x in seg], [u'一致'])
        self.assertEqual(S['seg_reversed'], 1)

    def test_legacy_export_without_catkey(self):
        r = dict(Category=u'風管配件')
        self.assertEqual(M.discipline(r), 'Duct')
        self.assertEqual(M.discipline(dict(Category=u'Cable Tray Fittings')), 'CableTray')
        self.assertEqual(M.discipline(dict(Category=u'管配件')), 'Pipe')

    def test_kinds(self):
        self.assertEqual(M.kind(u'風管-矩形-三通(短型)'), u'三通')
        self.assertEqual(M.kind(u'Elbow - Generic'), u'彎頭')
        self.assertEqual(M.kind(u'Rectangular to Round Transition'), u'大小頭/轉接頭')
        self.assertEqual(M.kind(u'Sprinkler - Pendent', 'OST_Sprinklers'), u'撒水頭')


if __name__ == '__main__':
    unittest.main()
