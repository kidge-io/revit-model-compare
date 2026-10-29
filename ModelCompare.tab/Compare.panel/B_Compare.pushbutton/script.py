# -*- coding: utf-8 -*-
"""
Compare two "Export MEP" CSVs: a reference model and a model under test.
Writes a summary, an issue list, segment/component tables and shots.csv for "Issue Shots".
Reads the CSVs and the open model's level elevations only; the model is not modified.
"""
import codecs
import datetime
import os
import traceback

from Autodesk.Revit.DB import FilteredElementCollector, Level
from Autodesk.Revit.UI import TaskDialog, TaskDialogCommonButtons, TaskDialogResult
from pyrevit import forms, revit

import mc_compare as M
from mc_i18n import disc_name, lang, m, tr

L = lang()
FT = 304.8


def doc_levels(doc):
    """(name, elevation_mm) of the open model's levels, low to high; None if unavailable."""
    try:
        lv = [(M.short_level(l.Name), l.Elevation * FT) for l in FilteredElementCollector(doc).OfClass(Level)]
        lv.sort(key=lambda x: x[1])
        return lv or None
    except Exception:
        return None


def levels_trustworthy(levels, rows):
    """Use model levels only if they agree with the CSV's reference levels for most elements."""
    if not levels:
        return False
    names = set(n for n, _ in levels)
    usable = [r for r in rows if M.short_level(r.get('Level')) in names and r.get('BBMinZ') is not None]
    if len(usable) < 20:
        return False
    hit = sum(1 for r in usable if M.floor_of(r['BBMinZ'], levels, None) == M.short_level(r.get('Level')))
    return hit >= 0.5 * len(usable)


owner_csv = forms.pick_file(file_ext='csv', title=m('pick_owner'))
if not owner_csv:
    raise SystemExit
ai_csv = forms.pick_file(file_ext='csv', title=m('pick_ai'))
if not ai_csv:
    raise SystemExit

try:
    owner_rows = M.read_export(owner_csv)
    ai_rows = M.read_export(ai_csv)
except Exception as ex:
    TaskDialog.Show(u'ModelCompare', m('read_fail', ex))
    raise SystemExit

# scope: disciplines, then (optionally) system types
for r in owner_rows + ai_rows:
    r['Disc'] = M.discipline(r)
present = [d for d in ('Duct', 'Pipe', 'CableTray', 'Conduit', 'Equipment', 'Other')
           if any(r['Disc'] == d for r in owner_rows)]
disciplines = None
if len(present) > 1:
    labels = dict((disc_name(d), d) for d in present)
    picked = forms.SelectFromList.show(sorted(labels), title=m('pick_disc'), multiselect=True,
                                       button_name=m('pick_btn'))
    if not picked:
        raise SystemExit
    disciplines = set(labels[p] for p in picked)

scoped = [r for r in owner_rows + ai_rows if not disciplines or r['Disc'] in disciplines]
sys_types = sorted(set(M.system_of(r) for r in scoped))
systems = None
if len(sys_types) > 1 and not forms.alert(m('all_sys', len(sys_types)), yes=True, no=True):
    labels = dict((tr(s, L), s) for s in sys_types)
    picked = forms.SelectFromList.show(sorted(labels), title=m('pick_sys'), multiselect=True,
                                       button_name=m('pick_btn'))
    if not picked:
        raise SystemExit
    systems = set(labels[p] for p in picked)

base_dir = forms.pick_folder(title=m('pick_out'))
if not base_dir:
    raise SystemExit

levels = doc_levels(revit.doc)
level_note = m('lvl_doc')
if not levels_trustworthy(levels, owner_rows):
    levels = None
    level_note = m('lvl_ref')

stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
out_dir = os.path.join(base_dir, M.FILES[L]['folder'] + stamp)
if not os.path.exists(out_dir):
    os.makedirs(out_dir)

try:
    S, n_issues, n_shots, text = M.run(owner_csv, ai_csv, out_dir, levels=levels, systems=systems,
                                       disciplines=disciplines, L=L)
except Exception:
    f = codecs.open(os.path.join(out_dir, u'error_log.txt'), 'w', 'utf-8')
    f.write(traceback.format_exc())
    f.close()
    TaskDialog.Show(u'ModelCompare', m('err', os.path.join(out_dir, u'error_log.txt')))
    raise SystemExit

scope = []
if disciplines:
    scope.append(u', '.join(disc_name(d) for d in sorted(disciplines)))
if systems:
    scope.append(u', '.join(tr(s, L) for s in sorted(systems)))
f = codecs.open(os.path.join(out_dir, M.FILES[L]['summary']), 'a', 'utf-8')
f.write(u'\r\n' + level_note + u'\r\n')
if scope:
    f.write(m('filters') + u' | '.join(scope) + u'\r\n')
f.close()

ss, cs = S['seg_status'], S['comp_status']
td = TaskDialog(u'ModelCompare')
td.MainInstruction = m('done_title', n_issues, n_shots)
td.MainContent = m('done_body', S['cov_ref_same_pct'], ss.get(u'一致', 0), S['ref_segs'],
                   cs.get(u'一致', 0), S['ref_comps'], cs.get(u'缺漏', 0), cs.get(u'多出', 0),
                   cs.get(u'尺寸不符', 0) + ss.get(u'尺寸不符', 0), S['test_custom'], out_dir, level_note)
td.FooterText = m('done_footer')
td.CommonButtons = TaskDialogCommonButtons.Ok | TaskDialogCommonButtons.Close
td.DefaultButton = TaskDialogResult.Ok
td.VerificationText = m('open_folder')
td.Show()
if td.WasVerificationChecked():
    try:
        os.startfile(out_dir)
    except Exception:
        pass
