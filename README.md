# CoachOS

一個以跑者與教練視角設計的本機產品。

它不是把 Garmin 數據換一種方式排版，而是把每一堂課、每一週、每一個月，重新整理成「值得理解」的訓練回顧。

## Release Status

- `v1.3.4` 已正式發布
- 產品對外主名稱維持 `CoachOS`
- 核心資料鏈路已固定為 `FIT -> Excel -> SQLite -> Semantic Layer -> Dashboard`
- `Connected Coach Knowledge` 已接進 `Activity -> Weekly -> Monthly -> AI handoff`
- `AI 延伸分析` 可把整理結果複製給 AI，並可將回覆寫回頁面
- `每日 / 每週 / 每月訓練圖卡 prompt` 已可直接從平台交給圖像 AI
- `GPS backfill` 與 `課表結構 backfill` 已可回補到 Excel 與 SQLite

目前產品由兩個一起工作的本機小程式組成：

- `資料匯入工具`  
  負責 `FIT -> Excel -> SQLite`
- `CoachOS`  
  負責 `Activity / Overview / Weekly / Monthly` 的教練式判讀

---

## 這個專案目前在做什麼

CoachOS 現在主要提供四個產品面：

- `Activity`：這堂課，我真正練到了什麼？
- `Overview`：今天，我最該關心的是什麼？
- `Weekly`：這週，我到底練到了什麼？
- `Monthly`：我現在在哪？
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

- `Activity`：Stable，已具備 Coach Review、Coach Knowledge、Evidence、AI handoff、每日圖卡 prompt
- `Overview`：Beta，作為 attention surface，已開始讀取 connected knowledge 狀態
- `Weekly`：Stable，已讀取 confirmed Coach Knowledge，並支援 AI handoff / 週圖卡 prompt
- `Monthly`：Stable，已讀取 confirmed Coach Knowledge，並支援 AI handoff / 月圖卡 prompt
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

這個 repo 現在反映的是正式對外的 `v1.3.4` 狀態，主題仍是 `Connected Coach Knowledge`：

- 統一名稱：`CoachOS`
- 把資料匯入工具作為產品裡的資料入口，而不是獨立散落的小工具
- 以 deterministic、本機可用、knowledge-first 的方式建立跑步教練產品
- 讓 `Activity` 裡確認的知識，實際回流到 `Weekly / Monthly / AI handoff`
- 讓 `課表結構`、`GPS`、`每日 / 每週 / 每月圖卡 prompt` 成為日常使用的一部分

`v1.3.4` 之後的下一步，不再只是把資料接進來，而是繼續收斂：

- 課表結構驅動的 Activity 判讀口徑
- 更穩定的本機 daily use flow
- 為後續 `Memory / Belief` 階段保留乾淨的產品基礎

正式發布說明與版本備註可參考：

[`LAUNCH_ANNOUNCEMENT.md`](/Users/perryliu/Documents/Running%20Analytics/LAUNCH_ANNOUNCEMENT.md)

[`RELEASE_NOTES_v1.2.0.md`](/Users/perryliu/Documents/Running%20Analytics/RELEASE_NOTES_v1.2.0.md)

[`RELEASE_NOTES_v1.3.0.md`](/Users/perryliu/Documents/Running%20Analytics/RELEASE_NOTES_v1.3.0.md)

[`docs/00_Governance/CoachOS Product Roadmap v1.0 Draft.md`](/Users/perryliu/Documents/Running%20Analytics/docs/00_Governance/CoachOS%20Product%20Roadmap%20v1.0%20Draft.md)

---

## License

This project is released under the MIT License.

See [`LICENSE`](/Users/perryliu/Documents/Running%20Analytics/LICENSE).

---

## Prompt Reference

[`跑步分析系統 Prompt v1.0.docx`](/Users/perryliu/Documents/Running%20Analytics/%E8%B7%91%E6%AD%A5%E5%88%86%E6%9E%90%E7%B3%BB%E7%B5%B1%20Prompt%20v1.0.docx) 是公開提供的 prompt reference。

它示範的是：當跑步資料已先整理成固定格式 Excel 後，如何把這份資料交給 ChatGPT 或其他 LLM，產生一致的訓練分析文字。
