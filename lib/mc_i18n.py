# -*- coding: utf-8 -*-
"""
UI language for ModelCompare. Follows pyRevit's language setting
(pyRevit > Settings > language): Chinese -> Traditional Chinese UI, anything else -> English.
"""

_LANG = None


def lang():
    global _LANG
    if _LANG is None:
        code = u'en_us'
        try:
            from pyrevit.coreutils import applocales
            code = applocales.get_current_applocale().locale_code or u'en_us'
        except Exception:
            pass
        _LANG = 'zh' if code in ('chinese_t', 'chinese_s', 'chinese') else 'en'
    return _LANG


# English for data values (statuses, issue groups, component kinds)
TR = {
    u'一致': u'Match', u'位置偏差': u'Minor offset', u'斷點差異': u'Break offset', u'位置不同': u'Moved',
    u'尺寸不符': u'Size mismatch', u'類型不符': u'Type mismatch', u'缺漏': u'Missing', u'多出': u'Extra',
    u'多出管段': u'Extra segment', u'缺漏管段': u'Missing segment', u'管段斷點差異': u'Segment break offset',
    u'管段位置偏差': u'Segment minor offset', u'管段尺寸不符': u'Segment size mismatch',
    u'缺漏元件': u'Missing component', u'多出元件': u'Extra component', u'元件尺寸不符': u'Component size mismatch',
    u'元件位置不同': u'Component moved', u'元件類型不符': u'Component type mismatch',
    u'非標準族群': u'Non-reference family',
    u'三通': u'Tee', u'四通': u'Cross', u'彎頭': u'Elbow', u'大小頭/轉接頭': u'Transition', u'管帽': u'Cap',
    u'接頭': u'Coupling', u'風門/閥': u'Damper/valve', u'風口': u'Air terminal', u'撒水頭': u'Sprinkler',
    u'設備': u'Equipment', u'管段': u'Segment', u'其他': u'Other', u'(無系統)': u'(no system)',
}


def tr(v, L=None):
    if (L or lang()) == 'zh' or v is None:
        return v
    return TR.get(v, v)


DISCIPLINES = {'Duct': (u'風管', u'Ducts'), 'Pipe': (u'水管', u'Pipes'), 'CableTray': (u'電纜架', u'Cable trays'),
               'Conduit': (u'導線管', u'Conduits'), 'Equipment': (u'設備', u'Equipment'), 'Other': (u'其他', u'Other')}


def disc_name(key):
    zh, en = DISCIPLINES.get(key, (key, key))
    return zh if lang() == 'zh' else en


MSG = {
    # Export
    'save_export': (u'匯出 MEP 元件 CSV 存放位置', u'Save exported MEP CSV'),
    'export_done': (u'已匯出 {0} 個元件\n{1}', u'Exported {0} elements\n{1}'),
    # Compare
    'pick_owner': (u'1/2 選擇「參考模型」的 CSV（例如業主模型）',
                   u'1/2 Select the CSV of the REFERENCE model (e.g. the owner model)'),
    'pick_ai': (u'2/2 選擇「受測模型」的 CSV（例如 AI 或外掛產生的模型）',
                u'2/2 Select the CSV of the model UNDER TEST (e.g. AI- or plugin-generated)'),
    'pick_out': (u'選擇比對結果要存放的資料夾', u'Select a folder for the comparison results'),
    'read_fail': (u'讀取 CSV 失敗，請確認是「匯出 MEP」產生的檔案。\n\n{0}',
                  u'Could not read the CSV. Make sure it was created by "Export MEP".\n\n{0}'),
    'pick_disc': (u'要比對哪些專業？', u'Which disciplines should be compared?'),
    'pick_btn': (u'確定', u'OK'),
    'all_sys': (u'所選專業共有 {0} 種系統類型。要全部比對嗎？\n選「否」可以挑選系統。',
                u'The selected disciplines contain {0} system types. Compare all of them?\nChoose "No" to pick systems.'),
    'pick_sys': (u'要比對哪些系統類型？', u'Which system types should be compared?'),
    'lvl_doc': (u'樓層依目前開啟模型的樓層高程判定', u'Floors assigned from level elevations of the open model'),
    'lvl_ref': (u'樓層依元件的參考樓層（目前模型的樓層高程與 CSV 對不上，或未開啟對應模型）',
                u'Floors taken from each element\'s reference level (open model levels did not match the CSV)'),
    'err': (u'比對時發生錯誤，詳見：\n{0}', u'An error occurred during comparison. See:\n{0}'),
    'done_title': (u'比對完成：{0} 筆差異，{1} 組截圖', u'Comparison done: {0} issues, {1} screenshot sets'),
    'done_body': (
        u'中心線（相同尺寸）覆蓋率：{0:.1f}%\n管段一致：{1} / {2}\n元件一致：{3} / {4}\n'
        u'缺漏元件 {5}、多出元件 {6}、尺寸不符 {7}\n受測模型使用參考模型沒有的族群：{8} 個\n\n結果存在：\n{9}\n\n{10}',
        u'Centerline coverage (same size): {0:.1f}%\nSegments matched: {1} / {2}\nComponents matched: {3} / {4}\n'
        u'Missing components {5}, extra components {6}, size mismatches {7}\n'
        u'Test-model components using non-reference families: {8}\n\nResults saved to:\n{9}\n\n{10}'),
    'done_footer': (u'下一步：在兩個模型各按一次「差異截圖」，選這次產生的 shots.csv',
                    u'Next: run "Issue Shots" in both models and select this shots.csv'),
    'open_folder': (u'開啟結果資料夾', u'Open results folder'),
    'filters': (u'比對範圍：', u'Scope: '),
    # Shots
    'pick_shots': (u'選擇 shots.csv', u'Select shots.csv'),
    'which_model': (u'目前開啟的是哪一個模型？', u'Which model is open?'),
    'owner': (u'參考模型', u'Reference model'),
    'ai': (u'受測模型', u'Model under test'),
    'pick_img': (u'選擇截圖存放資料夾', u'Select a folder for the screenshots'),
    'shots_done': (u'{0}：完成 {1} / {2} 張截圖\n找不到的元件 ID：{3} 個\n錯誤：{4} 筆（詳見資料夾內 log）\n輸出：{5}',
                   u'{0}: {1} / {2} screenshots exported\nElement IDs not found: {3}\nErrors: {4} (see log in folder)\n'
                   u'Output: {5}'),
    'view_fail': (u'{0} 建立視圖失敗: {1}', u'{0} view creation failed: {1}'),
    'export_fail': (u'{0} 匯出失敗: {1}', u'{0} export failed: {1}'),
    'tx_clean': (u'ModelCompare 清除舊視圖', u'ModelCompare remove old views'),
}


def m(key, *args):
    zh, en = MSG[key]
    s = zh if lang() == 'zh' else en
    return s.format(*args) if args else s
