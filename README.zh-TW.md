# Revit Model Compare

**量化 AI 或外掛自動產生的 MEP 模型，跟參考模型差多少。**

[English](README.md)

> **開始前請注意**：這是 pyRevit 擴充套件，需要先裝好 **Revit**（本工具在 2024 版開發）和 **[pyRevit](https://github.com/pyrevitlabs/pyRevit/releases)**。pyRevit 免費，到它的 Releases 頁面下載 `pyRevit_x.x.x_signed.exe` 執行即可；公司電腦不能自行安裝的話，請 IT 用 `..._admin_signed.exe` 安裝。接著照[安裝](#安裝)步驟進行。

AI 和自動化工具已經可以從 2D 圖面建出 Revit 模型，難的是確認建得對不對。Revit 現有的比對工具（ACC 版本比對、Navisworks Compare）都靠元件 ID 配對，只能比較**同一個檔案**的前後版本。兩個各自建立的模型 ID 完全不同，這些工具只會回報「全部新增、全部刪除」。

Revit Model Compare 改用**幾何位置**配對。每一段風管、水管、電纜架、導線管和每一個管件，都會判定為：建對了、略有偏差、位置不同、尺寸錯、缺漏，或多出。差異處也會自動產生上色的並排截圖。

這是一個 [pyRevit](https://github.com/pyrevitlabs/pyRevit) 擴充套件，有三個按鈕：

| 按鈕 | 功能 |
|---|---|
| **匯出 MEP** | 把目前模型的 MEP 元件匯出成 CSV，包含 ID、類別、族群、系統、尺寸、座標。只讀取，不修改模型。 |
| **比對模型** | 比對參考模型與受測模型的 CSV，輸出摘要、差異明細、完整比對表和截圖清單。 |
| **差異截圖** | 為每一群差異建立剖面框 3D 視圖，差異元件上色後匯出 PNG。兩個模型各跑一次，就得到同視角的成對截圖。 |

第一次實際應用，是比對外掛自動產生的排煙風管系統和業主模型（每個模型約 1,400 個元件，15 個樓層）。結果顯示，業主風管中心線 100% 以正確尺寸重現。工具也找出了外掛出錯的具體位置：轉接頭圓端口徑退回族群預設值、該用矩形斷面的地方出現橢圓斷面，以及用外掛自產族群取代了業主的標準族群。

## 判定項目

管段（風管、水管、電纜架、導線管）以兩端點配對，不論繪製方向。元件（管件、附件、風口、撒水頭、設備）以插入點配對。只在同一個專業內配對，風管不會跟水管配在一起。

| 結果 | 意義 |
|---|---|
| 一致 | 尺寸相同，位置差 ≤ 5 mm |
| 位置偏差 | 尺寸相同，位置差 ≤ 50 mm |
| 斷點差異（管段） | 同中心線、同尺寸，但分段的位置不同 |
| 位置不同（元件） | 同類型元件在 1 m 內，但差距超過 50 mm |
| 尺寸不符／類型不符 | 位置吻合，但尺寸或元件類型不同 |
| 缺漏／多出 | 找不到對應構件 |
| 非標準族群 | 受測模型用了參考模型沒有的族群 |

另外會計算**中心線覆蓋率**：參考模型的管段總長中，有多少比例被受測模型重現。這個數字不受分段方式影響，最能回答「管線路徑有沒有建出來」。

輸出（資料夾「比對結果_日期時間」）：

- `比對摘要.txt`：各專業的重點數字
- `差異明細.csv`：每筆差異一列，附兩邊的 ElementId，可以在 Revit 用「依 ID 選取」查看
- `管段比對.csv`、`元件比對.csv`：每一個配對判定
- `shots.csv`：給「差異截圖」用的清單

## 安裝

### 步驟 1：安裝 pyRevit（Revit 裡已經有 *pyRevit* 頁籤就跳過）

1. 關閉 Revit。
2. 到 [pyRevit Releases 頁面](https://github.com/pyrevitlabs/pyRevit/releases)，下載最新版的 `pyRevit_x.x.x_signed.exe`。要裝給所有使用者，或沒有安裝權限時，改用 `pyRevit_x.x.x_admin_signed.exe`。
3. 執行安裝檔，再開啟 Revit，功能區會出現 **pyRevit** 頁籤。

本工具在 pyRevit 7.0 與 Revit 2024 上開發和測試，其他版本應可使用，但尚未測試。

### 步驟 2：安裝 Revit Model Compare

#### 方法 A：pyRevit 命令列

```
pyrevit extend ui ModelCompare https://github.com/kidge-io/revit-model-compare.git
```

#### 方法 B：手動安裝

1. 下載本 repo 的 ZIP 並解壓縮。
2. 把解壓後的資料夾改名為 `ModelCompare.extension`（pyRevit 只載入 `.extension` 結尾的資料夾），例如放在 `D:\pyRevitExt\ModelCompare.extension`。
3. 在 Revit 中：**pyRevit 頁籤 → pyRevit ▾ → Settings → Custom Extension Directories → Add folder**，選擇**上一層**資料夾（`D:\pyRevitExt`），然後按 **Save Settings and Reload**。

功能區會出現 **ModelCompare** 頁籤，裡面有三個按鈕。

## 使用

1. 開啟參考模型（例如業主模型），按「匯出 MEP」。受測模型也做一次。
2. 開著參考模型按「比對模型」，依序選參考 CSV 和受測 CSV，再挑要比對的專業與系統，最後指定存放資料夾。
3. 在兩個模型各按一次「差異截圖」，選第 2 步產生的 `shots.csv`。每組差異會得到 `Sxx_ref.png` 和 `Sxx_test.png`，視角相同。

手邊沒有模型也可以先試：`examples/sample/` 裡有一組合成的範例資料，刻意埋了幾種已知差異，直接用「比對模型」比對這兩份 CSV 即可。

**語言**：介面跟隨 pyRevit 的語言設定。選中文顯示繁體中文，選其他語言顯示英文。

## 前提與限制

- 兩個模型必須使用相同的**內部原點**，本工具不做座標對齊。
- 「差異截圖」只新增 `MC_` 開頭的 3D 視圖，不會修改元件，但仍建議在模型副本上執行。
- 容差目前是固定值（5 mm／50 mm／1 m），設定在 `lib/mc_compare.py`。
- 如果目前開啟模型的樓層高程和 CSV 吻合，就依實際高程判定樓層；不吻合時改用元件的參考樓層。
- 目前已驗證的範圍：一個實際專案（風管），以及合成範例（風管、水管、電纜架）。如果你的模型結果異常，歡迎開 issue。

## 開發

比對核心 `lib/mc_compare.py` 是純 Python，可以在 IronPython 2.7（Revit 內）和 CPython 3 上執行，所以不用開 Revit 就能測試：

```
python examples/make_sample.py
python -m unittest discover -s tests -v
```

修改核心時請避免 f-string 等 Python 3 專屬語法。

## 服務與支援

Revit Model Compare 免費提供，採用 MIT 授權，由[格界科技 KIDGE Ltd.](https://kidge.io)（台北）開發。

我們也提供：

- **模型比對報告服務**：代為執行比對，交付完整報告（摘要、差異分析、並排截圖、PPT 與 PDF）
- **導入協助**：依團隊、專案與建模標準建立比對流程
- **技術支援**：安裝、問題排除與客製化

聯繫信箱：[support@kidge.io](mailto:support@kidge.io)

錯誤回報與功能建議，歡迎在 [GitHub issues](../../issues) 提出。

## 授權

[MIT](LICENSE)
