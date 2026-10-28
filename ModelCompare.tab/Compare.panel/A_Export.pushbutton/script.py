# -*- coding: utf-8 -*-
"""
Export MEP elements of the open model to CSV (read-only).
Run once in each model you want to compare.

Columns: ElementId, UniqueId, CatKey (BuiltInCategory), Category, Family, Type, Level,
SystemClassification, SystemType, SystemName, Size, Diameter/Width/Height/MiddleElev/Length (mm),
GeomKind (Curve / Point / BBox), internal coordinates X1..Z2, shared coordinates SX1..SZ2,
bounding box BBMin/BBMax (internal, mm).
"""
import codecs
import os

from Autodesk.Revit.DB import (
    BuiltInCategory, BuiltInParameter, Element, ElementId, ElementMulticategoryFilter,
    FilteredElementCollector, LocationCurve, LocationPoint, StorageType,
)
from Autodesk.Revit.UI import TaskDialog
from System import Enum, Environment
from System.Collections.Generic import List
from pyrevit import forms, revit

from mc_categories import MEP_CATEGORIES
from mc_i18n import m

doc = revit.doc
FT_TO_MM = 304.8


def txt(v):
    if v is None:
        return u""
    try:
        return unicode(v)  # noqa: F821  IronPython
    except NameError:
        return str(v)


def int_id(eid):
    try:
        return eid.Value          # Revit 2024+
    except AttributeError:
        return eid.IntegerValue   # older versions


def bip(name):
    return getattr(BuiltInParameter, name, None)


def param_text(el, bip_name):
    b = bip(bip_name)
    if b is None:
        return u""
    try:
        p = el.get_Parameter(b)
    except Exception:
        return u""
    if p is None or not p.HasValue:
        return u""
    if p.StorageType == StorageType.String:
        return txt(p.AsString())
    s = p.AsValueString()
    return txt(s) if s else u""


def param_mm(el, bip_names):
    for name in bip_names:
        b = bip(name)
        if b is None:
            continue
        try:
            p = el.get_Parameter(b)
        except Exception:
            continue
        if p is not None and p.HasValue and p.StorageType == StorageType.Double:
            return round(p.AsDouble() * FT_TO_MM, 1)
    return u""


def level_name(el):
    try:
        rl = getattr(el, "ReferenceLevel", None)  # MEPCurve
        if rl is not None:
            return txt(rl.Name)
    except Exception:
        pass
    try:
        lid = el.LevelId
    except Exception:
        lid = None
    if lid is not None and lid != ElementId.InvalidElementId:
        lv = doc.GetElement(lid)
        if lv is not None:
            return txt(lv.Name)
    for name in ("FAMILY_LEVEL_PARAM", "RBS_START_LEVEL_PARAM", "SCHEDULE_LEVEL_PARAM"):
        v = param_text(el, name)
        if v:
            return v
    return u""


def family_type(el):
    fam, typ = u"", u""
    try:
        t = doc.GetElement(el.GetTypeId())
        if t is not None:
            try:
                typ = txt(Element.Name.GetValue(t))  # IronPython cannot read ElementType.Name directly
            except Exception:
                typ = txt(getattr(t, "Name", u""))
            fam = txt(getattr(t, "FamilyName", u""))
    except Exception:
        pass
    return fam, typ


def cat_key(el):
    try:
        return txt(el.Category.BuiltInCategory)  # Revit 2023+
    except Exception:
        pass
    try:
        import clr
        return txt(Enum.ToObject(clr.GetClrType(BuiltInCategory), int(int_id(el.Category.Id))))
    except Exception:
        return u""


def system_type(el):
    # ducts/pipes use the system type; cable trays/conduits use the service type
    return (param_text(el, "RBS_PIPING_SYSTEM_TYPE_PARAM") or param_text(el, "RBS_DUCT_SYSTEM_TYPE_PARAM")
            or param_text(el, "RBS_CTC_SERVICE_TYPE"))


try:
    to_shared = doc.ActiveProjectLocation.GetTotalTransform().Inverse
except Exception:
    to_shared = None


def mm(pt):
    return [round(pt.X * FT_TO_MM, 1), round(pt.Y * FT_TO_MM, 1), round(pt.Z * FT_TO_MM, 1)]


def shared_mm(pt):
    if to_shared is None:
        return [u"", u"", u""]
    return mm(to_shared.OfPoint(pt))


def csv_cell(v):
    s = txt(v)
    if any(c in s for c in [u",", u'"', u"\n", u"\r"]):
        s = u'"' + s.replace(u'"', u'""') + u'"'
    return s


def model_dir(d):
    """Folder of the model file; Desktop for cloud or unsaved models."""
    try:
        p = d.PathName
        if p and os.path.isabs(p) and os.path.isdir(os.path.dirname(p)):
            return os.path.dirname(p)
    except Exception:
        pass
    return Environment.GetFolderPath(Environment.SpecialFolder.Desktop)  # handles OneDrive desktops


HEADER = [
    "ElementId", "UniqueId", "CatKey", "Category", "Family", "Type", "Level",
    "SystemClassification", "SystemType", "SystemName", "Size",
    "Diameter_mm", "Width_mm", "Height_mm", "MiddleElev_mm", "Length_mm",
    "GeomKind",
    "X1", "Y1", "Z1", "X2", "Y2", "Z2",
    "SX1", "SY1", "SZ1", "SX2", "SY2", "SZ2",
    "BBMinX", "BBMinY", "BBMinZ", "BBMaxX", "BBMaxY", "BBMaxZ",
]

default_name = (doc.Title or u"model") + u"_mep_elements.csv"
path = forms.save_file(file_ext="csv", init_dir=model_dir(doc), default_name=default_name,
                       restore_dir=True, title=m('save_export'))
if not path:
    raise SystemExit
if not path.lower().endswith(".csv"):
    path += ".csv"

cats = List[BuiltInCategory]()
for n in MEP_CATEGORIES:
    c = getattr(BuiltInCategory, n, None)
    if c is not None:
        cats.Add(c)
elems = (FilteredElementCollector(doc)
         .WherePasses(ElementMulticategoryFilter(cats))
         .WhereElementIsNotElementType()
         .ToElements())

LOG_PATH = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "ModelCompare_export_log.txt")
log = codecs.open(LOG_PATH, "w", "utf-8")
log.write(u"START doc={0} count={1}\r\n".format(doc.Title, len(elems)))

rows, failed = [], 0
for i, el in enumerate(elems):
    try:
        fam, typ = family_type(el)
        row = [
            int_id(el.Id), el.UniqueId, cat_key(el),
            el.Category.Name if el.Category else u"",
            fam, typ, level_name(el),
            param_text(el, "RBS_SYSTEM_CLASSIFICATION_PARAM"),
            system_type(el),
            param_text(el, "RBS_SYSTEM_NAME_PARAM"),
            param_text(el, "RBS_CALCULATED_SIZE"),
            param_mm(el, ["RBS_PIPE_DIAMETER_PARAM", "RBS_CURVE_DIAMETER_PARAM", "RBS_CONDUIT_DIAMETER_PARAM"]),
            param_mm(el, ["RBS_CURVE_WIDTH_PARAM", "RBS_CABLETRAY_WIDTH_PARAM"]),
            param_mm(el, ["RBS_CURVE_HEIGHT_PARAM", "RBS_CABLETRAY_HEIGHT_PARAM"]),
            param_mm(el, ["RBS_OFFSET_PARAM"]),
            param_mm(el, ["CURVE_ELEM_LENGTH"]),
        ]
        loc = el.Location
        a = b = None
        if isinstance(loc, LocationCurve) and loc.Curve is not None:
            kind = u"Curve"
            a, b = loc.Curve.GetEndPoint(0), loc.Curve.GetEndPoint(1)
        elif isinstance(loc, LocationPoint):
            kind = u"Point"
            a = loc.Point
        else:
            kind = u"BBox"
        row.append(kind)
        row += mm(a) if a else [u""] * 3
        row += mm(b) if b else [u""] * 3
        row += shared_mm(a) if a else [u""] * 3
        row += shared_mm(b) if b else [u""] * 3
        bb = el.get_BoundingBox(None)
        row += (mm(bb.Min) + mm(bb.Max)) if bb else [u""] * 6
        rows.append(row)
    except Exception as ex:
        failed += 1
        log.write(u"skip id={0}: {1}\r\n".format(el.Id, ex))
    if i % 500 == 0:
        log.write(u"progress {0}\r\n".format(i))
        log.flush()

f = codecs.open(path, "w", "utf-8-sig")  # BOM so Excel opens CJK text correctly
try:
    f.write(u",".join(HEADER) + u"\r\n")
    for r in rows:
        f.write(u",".join(csv_cell(v) for v in r) + u"\r\n")
finally:
    f.close()
log.write(u"DONE rows={0} failed={1} -> {2}\r\n".format(len(rows), failed, path))
log.close()
TaskDialog.Show(u"ModelCompare", m('export_done', len(rows), path))
