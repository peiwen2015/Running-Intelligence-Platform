# CoachOS v1.2.0 正式發布

CoachOS 是一個本機優先、knowledge-first 的跑步分析產品。

`v1.2.0` 代表這個專案已經完成 Canonical Data Model 的定版，
並把產品鏈路收斂成一條可以持續演進的本機跑步分析系統。

## 這次發布包含什麼

- `資料匯入工具`：把 Garmin FIT 轉成 Excel 與 SQLite
- `CoachOS`：把資料變成 Activity / Overview / Weekly / Monthly 的教練式回顧
- `Canonical Data Model v1.2`：核心概念與資料模型完成定版
- `Semantic Layer v1.0`：把重複的 SQL 與頁面邏輯收斂成可重用的產品語意
- `SQLite Schema v1.0`：已完成真實資料驗證的核心物理模型
- `Metadata Repository v1.1`：把產品裡的關鍵名詞與規則先治理好

## 產品現在回答的問題

- 這堂課真正練到了什麼？
- 這週身體學到了什麼？
- 這個月目前位於哪個訓練位置？
- 今天最該關心的是什麼？

## 目前公開的產品面

- `Activity`
- `Overview`
- `Weekly`
- `Monthly`

`Journey` 目前仍保留在程式裡，但暫時不作為公開產品面。

## 使用方式

macOS：

```text
CoachOS.command
```

Windows：

```text
CoachOS.bat
```

或直接啟動平台：

```bash
python3 analysis_platform/dashboard_app.py analysis_platform/running_analytics.sqlite
```

資料匯入工具也可以獨立啟動：

```bash
python3 app.py
```

## 這個 release 的意義

這次不只是把一組檔案整理成可以打包的形式，
而是把產品、文件、版本與入口收斂成一個可以長期維護的本機跑步分析系統。

如果一般跑步平台是在幫你讀數據，
CoachOS 想做的，是幫跑者慢慢學會像教練一樣理解訓練。
