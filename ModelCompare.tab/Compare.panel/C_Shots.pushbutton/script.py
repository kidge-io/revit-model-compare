# -*- coding: utf-8 -*-
"""
Issue screenshots. Reads shots.csv and, for each entry, creates an MC_ 3D view with a section box,
colors the issue elements, greys out other MEP elements and exports a PNG.
Run once in the reference model and once in the model under test: both use the same section box,
so the images can be compared side by side. Only adds views; elements are not modified.
"""
import codecs
import os

from Autodesk.Revit.DB import (
    BoundingBoxXYZ, BuiltInCategory, CategoryType, Color, DisplayStyle, ElementId,
    ElementMulticategoryFilter, ExportRange, FillPatternElement, FilteredElementCollector,
    ImageExportOptions, ImageFileType, ImageResolution, OverrideGraphicSettings, Transaction,
    View3D, ViewDetailLevel, ViewFamily, ViewFamilyType, XYZ, ZoomFitType,
)
from Autodesk.Revit.UI import TaskDialog
from System import Int64
from System.Collections.Generic import List
from pyrevit import forms, revit

from mc_categories import MEP_CATEGORIES
from mc_i18n import TR, m

doc = revit.doc
FT = 304.8
PIXELS = 2400

CATS = [getattr(BuiltInCategory, n) for n in MEP_CATEGORIES if hasattr(BuiltInCategory, n)]
COLORS = {
    u'缺漏元件': (220, 30, 30), u'缺漏管段': (220, 30, 30),
    u'元件尺寸不符': (240, 180, 0), u'管段尺寸不符': (240, 180, 0), u'元件類型不符': (240, 180, 0),
    u'多出元件': (255, 120, 0), u'多出管段': (255, 120, 0),
    u'非標準族群': (170, 60, 200),
    u'管段斷點差異': (30, 120, 220), u'元件位置不同': (30, 120, 220),
    u'管段位置偏差': (30, 170, 160),
}
COLORS.update(dict((TR[k], v) for k, v in list(COLORS.items()) if k in TR))  # English shots.csv


def eid(v):
    try:
        return ElementId(Int64(int(v)))
    except Exception:
        return ElementId(int(v))


def int_id(e):
    try:
        return e.Value
    except AttributeError:
        return e.IntegerValue


def crop_to_box(v, box, pad=1.0):
    """Shrink the view crop to the projected section box so the export zooms to the issue."""
    cb = v.CropBox
    T = cb.Transform
    inv = T.Inverse
    xs, ys = [], []
    for x in (box.Min.X, box.Max.X):
        for y in (box.Min.Y, box.Max.Y):
            for z in (box.Min.Z, box.Max.Z):
                q = inv.OfPoint(XYZ(x, y, z))
                xs.append(q.X)
                ys.append(q.Y)
    nb = BoundingBoxXYZ()
    nb.Transform = T
    nb.Min = XYZ(min(xs) - pad, min(ys) - pad, cb.Min.Z)
    nb.Max = XYZ(max(xs) + pad, max(ys) + pad, cb.Max.Z)
    v.CropBox = nb
    v.CropBoxActive = True
    v.CropBoxVisible = False


def read_shots(path):
    import csv
    f = codecs.open(path, 'r', 'utf-8-sig')
    lines = [l for l in f.read().splitlines() if l.strip()]
    f.close()
    rows = list(csv.reader(lines))
    return [dict(zip(rows[0], r)) for r in rows[1:]]


csv_path = forms.pick_file(file_ext='csv', title=m('pick_shots'))
if not csv_path:
    raise SystemExit
which = forms.CommandSwitchWindow.show([m('owner'), m('ai')], message=m('which_model'))
if not which:
    raise SystemExit
id_col, tag = ('owner_ids', 'ref') if which == m('owner') else ('ai_ids', 'test')
out_dir = forms.pick_folder(title=m('pick_img'))
if not out_dir:
    raise SystemExit

shots = read_shots(csv_path)
vft = [x for x in FilteredElementCollector(doc).OfClass(ViewFamilyType)
       if x.ViewFamily == ViewFamily.ThreeDimensional][0]
solid = [fp for fp in FilteredElementCollector(doc).OfClass(FillPatternElement)
         if fp.GetFillPattern().IsSolidFill][0]
mep_cat_ids = set()
for c in CATS:
    cat = doc.Settings.Categories.get_Item(c)
    if cat is not None:
        mep_cat_ids.add(int_id(cat.Id))
mep_filter = ElementMulticategoryFilter(List[BuiltInCategory](CATS))

# remove views left by a previous run
old = [v.Id for v in FilteredElementCollector(doc).OfClass(View3D)
       if not v.IsTemplate and v.Name.startswith(u'MC_') and v.Name.endswith(u'_' + tag)]
if old:
    t = Transaction(doc, m('tx_clean'))
    t.Start()
    for i in old:
        doc.Delete(i)
    t.Commit()

done, missing_ids, log = 0, 0, []
for s in shots:
    name = u'MC_%s_%s' % (s['shot_id'], tag)
    ids = [x for x in s.get(id_col, u'').split(u';') if x.strip()]
    hl = [i for i in (eid(x) for x in ids) if doc.GetElement(i) is not None]
    missing_ids += len(ids) - len(hl)

    t = Transaction(doc, u'ModelCompare ' + name)
    t.Start()
    try:
        v = View3D.CreateIsometric(doc, vft.Id)
        v.Name = name
        try:
            v.ViewTemplateId = ElementId.InvalidElementId  # a default template would override crop/graphics
        except Exception:
            pass
        v.DisplayStyle = DisplayStyle.ShadingWithEdges
        v.DetailLevel = ViewDetailLevel.Fine
        box = BoundingBoxXYZ()
        box.Min = XYZ(float(s['minx']) / FT, float(s['miny']) / FT, float(s['minz']) / FT)
        box.Max = XYZ(float(s['maxx']) / FT, float(s['maxy']) / FT, float(s['maxz']) / FT)
        v.SetSectionBox(box)
        for cat in doc.Settings.Categories:
            if cat.CategoryType == CategoryType.Model and int_id(cat.Id) not in mep_cat_ids:
                try:
                    if v.CanCategoryBeHidden(cat.Id):
                        v.SetCategoryHidden(cat.Id, True)
                except Exception:
                    pass
        try:
            v.SetCategoryHidden(ElementId(BuiltInCategory.OST_SectionBox), True)
        except Exception:
            pass
        doc.Regenerate()
        crop_to_box(v, box)
        doc.Regenerate()
        # everything else: solid grey (system colors would otherwise show through halftone)
        grey = OverrideGraphicSettings()
        grey.SetHalftone(True)
        grey.SetSurfaceForegroundPatternId(solid.Id)
        grey.SetSurfaceForegroundPatternColor(Color(190, 190, 190))
        grey.SetProjectionLineColor(Color(150, 150, 150))
        hl_set = set(int_id(i) for i in hl)
        for el in FilteredElementCollector(doc, v.Id).WherePasses(mep_filter).WhereElementIsNotElementType():
            if int_id(el.Id) not in hl_set:
                v.SetElementOverrides(el.Id, grey)
        rgb = COLORS.get(s['group'], (220, 30, 30))
        c = Color(rgb[0], rgb[1], rgb[2])
        ogs = OverrideGraphicSettings()
        ogs.SetSurfaceForegroundPatternId(solid.Id)
        ogs.SetSurfaceForegroundPatternColor(c)
        ogs.SetProjectionLineColor(c)
        ogs.SetProjectionLineWeight(6)
        for i in hl:
            v.SetElementOverrides(i, ogs)
        t.Commit()
    except Exception as ex:
        t.RollBack()
        log.append(m('view_fail', s['shot_id'], ex))
        continue

    try:
        opts = ImageExportOptions()
        opts.ExportRange = ExportRange.SetOfViews
        opts.SetViewsAndSheets(List[ElementId]([v.Id]))
        prefix = os.path.join(out_dir, u'%s_%s' % (s['shot_id'], tag))
        opts.FilePath = prefix
        opts.ZoomType = ZoomFitType.FitToPage
        opts.PixelSize = PIXELS
        opts.ImageResolution = ImageResolution.DPI_150
        opts.HLRandWFViewsFileType = ImageFileType.PNG
        opts.ShadowViewsFileType = ImageFileType.PNG
        before = set(os.listdir(out_dir))
        doc.ExportImage(opts)
        new = [n for n in os.listdir(out_dir) if n not in before and n.lower().endswith('.png')]
        target = prefix + u'.png'
        if new:
            if os.path.exists(target):
                os.remove(target)
            os.rename(os.path.join(out_dir, new[0]), target)
        done += 1
    except Exception as ex:
        log.append(m('export_fail', s['shot_id'], ex))

logf = codecs.open(os.path.join(out_dir, u'ModelCompare_shots_log_%s.txt' % tag), 'w', 'utf-8')
logf.write(u'\r\n'.join(log) if log else u'OK')
logf.close()
TaskDialog.Show(u'ModelCompare', m('shots_done', which, done, len(shots), missing_ids, len(log), out_dir))
