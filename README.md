# CoachOS

一個以跑者與教練視角設計的本機產品。

它不是把 Garmin 數據換一種方式排版，而是把每一堂課、每一週、每一個月，重新整理成「值得理解」的訓練回顧。

## Release Status

- `v1.4.0` 正在整理為下一個正式版本
- 產品對外主名稱維持 `CoachOS`
- 核心資料鏈路已固定為 `FIT -> Excel -> SQLite -> Semantic Layer -> Dashboard`
- `Workout Sequence Intelligence` 已接進 `Activity -> Weekly -> Monthly -> AI 交棒`
- `AI 延伸分析` 可把整理結果複製給 AI，並可將回覆寫回頁面
- `每日 / 每週 / 每月訓練圖卡 prompt` 已可直接從平台交給圖像 AI
- `GPS backfill`、`課表結構 backfill` 與 `心率 / 欄位修補` 已可回補到 Excel 與 SQLite
- `訓練序列理解` 可從資料匯入工具批次重算並寫回 SQLite，Excel 仍保持單純

目前產品由兩個一起工作的本機小程式組成：

- `資料匯入工具`  
  負責 `FIT -> Excel -> SQLite`
- `CoachOS`  
  負責 `Activity / Overview / Weekly / Monthly` 的教練式判讀

---

## 這個專案目前在做什麼

CoachOS 現在主要提供四個產品面：

- `Activity`：今天這堂課，在整個訓練中的位置是什麼？
- `Overview`：今天，我最該關心的是什麼？
- `Weekly`：這週真正留下來的是什麼？
- `Monthly`：這個月最後建立了什麼？
- `Metadata / Settings`：補標註、修正來源、管理鞋款與課表對照
- `AI 延伸分析`：把整理好的內容交給外部 AI 繼續分析，結果也能寫回頁面

`Journey` 目前保留在程式裡，但暫時不作為公開產品面。

CoachOS optimizes for understanding, not information density.

---

## AI 回覆與圖檔

CoachOS 會把貼回來的 AI 回覆與附加圖檔存到專案根目錄下的 `AI_REPLIES/`。

- 文字回覆與 metadata：`AI_REPLIES/<surface>/<identifier>.json` 與 `.md`
- 圖檔附件：`AI_REPLIES/<surface>/<identifier>/attachments/`

例如單堂課、週回顧、月回顧的圖檔都會各自放在對應的附件資料夾裡。

---

## 本機使用方式

### 1. 安裝需求

```bash
pip install -r requirements.txt
```

### 2. 啟動 CoachOS

macOS：

```text
CoachOS.command
```

Windows：

```text
CoachOS.bat
```

雙擊後會先打開平台首頁；需要轉檔與匯入時，再從首頁進入資料匯入工具。

或直接啟動平台：

```bash
python3 analysis_platform/dashboard_app.py analysis_platform/running_analytics.sqlite
```

預設網址：

```text
http://127.0.0.1:8766
```

### 3. 直接啟動資料匯入工具

如果你只想單獨開資料轉檔工具，也可以直接啟動：

```bash
python3 app.py
```

預設網址：

```text
http://127.0.0.1:8765
```

現在 Platform 首頁已經可以直接進入資料匯入工具，所以日常使用會像同一套產品。

---

## 產品流程

### Event Flow

```text
Run
↓
Import FIT
↓
Activity
↓
Weekly
↓
Monthly
↓
AI Handoff
```

### Routine Flow

```text
Open App
↓
Overview
↓
Weekly / Monthly / Shoes
```

---

## 專案結構

```text
app.py                             資料匯入工具
fit_to_excel.py                    FIT 轉 Excel 主程式
analysis_platform/dashboard_app.py CoachOS
analysis_platform/running_analytics.sqlite
                                   本機 SQLite 資料庫
config/dropdown_options.json       下拉選單設定
assets/                            品牌與介面圖片
docs/                              架構、知識與產品設計文件
跑步分析系統 Prompt v1.0.docx       提供給 ChatGPT / LLM 參考的 Excel 分析 prompt 範例
```

---

## 資料夾說明

```text
FIT/       Garmin Original FIT 檔
EXCEL/     轉出的 Excel 檔
config/    下拉選單設定
assets/    產品圖片與品牌素材
docs/      架構與產品文件
```

---

## 目前的產品狀態

- `Activity`：Stable，已具備教練判讀、教練知識、訓練序列理解、證據、AI 交棒、每日圖卡 prompt
- `Overview`：Beta，作為注意力入口，已開始讀取 connected knowledge 狀態
- `Weekly`：Stable，已讀取 confirmed 教練知識與訓練序列理解，並支援 AI 交棒 / 週圖卡 prompt
- `Monthly`：Stable，已讀取 confirmed 教練知識與訓練序列理解，並支援 AI 交棒 / 月圖卡 prompt
- `Metadata / Settings`：Stable，已具備建議值、provenance、補標註與鞋款狀態管理
- `Shoes`：Beta，已可進行鞋款狀態調整，但仍會持續收斂

---

## 設計原則

這個專案目前最核心的原則不是「先設計完整架構」，而是：

> We don’t design products. We discover them.

也就是：

> 我們不是設計產品，而是發現產品。

---

## 對外發布方向

這個 repo 現在正在整理 `v1.4.0`，主題是 `Workout Sequence Intelligence Product Layer`：

- 統一名稱：`CoachOS`
- 把資料匯入工具作為產品裡的資料入口，而不是獨立散落的小工具
- 以 deterministic、本機可用、knowledge-first 的方式建立跑步教練產品
- 讓 `Activity` 裡確認的知識與序列理解，實際回流到 `Weekly / Monthly / AI 交棒`
- 讓 `課表結構`、`GPS`、`活動最高心率修補`、`每日 / 每週 / 每月圖卡 prompt` 成為日常使用的一部分
- 把 Activity / Weekly / Monthly 的 WSI 翻譯成一致的教練語言
- 保持 Excel 單純，讓 WSI 留在 SQLite 與 CoachOS 產品層

`v1.4.0` 之後的下一步，不再只是把 WSI 放進頁面，而是繼續收斂：

- Overview 接上同一套跨時間尺度的教練語言
- WSI rule review 與 validation evidence 持續回饋產品
- 為後續 `Memory / Belief` 階段保留乾淨的產品基礎

正式發布說明與版本備註可參考：

[`LAUNCH_ANNOUNCEMENT.md`](/Users/perryliu/Documents/Running%20Analytics/LAUNCH_ANNOUNCEMENT.md)

[`RELEASE_NOTES_v1.2.0.md`](/Users/perryliu/Documents/Running%20Analytics/RELEASE_NOTES_v1.2.0.md)

[`RELEASE_NOTES_v1.3.0.md`](/Users/perryliu/Documents/Running%20Analytics/RELEASE_NOTES_v1.3.0.md)

[`RELEASE_NOTES_v1.3.5.md`](/Users/perryliu/Documents/Running%20Analytics/RELEASE_NOTES_v1.3.5.md)

[`RELEASE_NOTES_v1.3.6.md`](/Users/perryliu/Documents/Running%20Analytics/RELEASE_NOTES_v1.3.6.md)

[`RELEASE_ANNOUNCEMENT_v1.3.6.md`](/Users/perryliu/Documents/Running%20Analytics/RELEASE_ANNOUNCEMENT_v1.3.6.md)

[`RELEASE_NOTES_v1.4.0.md`](/Users/perryliu/Documents/Running%20Analytics/RELEASE_NOTES_v1.4.0.md)

[`RELEASE_ANNOUNCEMENT_v1.4.0.md`](/Users/perryliu/Documents/Running%20Analytics/RELEASE_ANNOUNCEMENT_v1.4.0.md)

[`docs/00_Governance/CoachOS Product Roadmap v1.0 Draft.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Product%20Roadmap%20v1.0%20Draft.md)

---

## License

This project is released under the MIT License.

See [`LICENSE`](/Users/perryliu/Documents/Running%20Analytics/LICENSE).

---

## Prompt Reference

[`跑步分析系統 Prompt v1.0.docx`](/Users/perryliu/Documents/Running%20Analytics/%E8%B7%91%E6%AD%A5%E5%88%86%E6%9E%90%E7%B3%BB%E7%B5%B1%20Prompt%20v1.0.docx) 是公開提供的 prompt reference。

它示範的是：當跑步資料已先整理成固定格式 Excel 後，如何把這份資料交給 ChatGPT 或其他 LLM，產生一致的訓練分析文字。
