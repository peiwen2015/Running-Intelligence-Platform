# Running Intelligence Platform v1.0.0

Running Intelligence Platform 的第一個正式版本。

這個版本把跑步資料、產品語意、以及對外入口收斂成一條可持續維護的本機產品鏈路。

## Highlights

- `資料匯入工具` 已納入正式產品流程，負責 `FIT -> Excel -> SQLite`
- `Running Intelligence Platform` 已固定為對外主名稱
- `Semantic Layer v1.0` 已成為 Dashboard 與 Query Layer 的產品語意層
- `SQLite Schema v1.0` 已完成真實資料驗證
- `Metadata Repository v1.1` 已成為名詞與規則的治理基礎

## Current product surfaces

- `Activity`
- `Overview`
- `Weekly`
- `Monthly`

`Journey` 目前保留在程式裡，但暫時不作為公開產品面。

## What this release answers

- 這堂課真正練到了什麼？
- 這週身體學到了什麼？
- 這個月目前位於哪個訓練位置？
- 今天最該關心的是什麼？

## Notable changes

- 新增正式發布敘述與 release status
- 對齊 architecture roadmap 與 architecture index 的版本狀態
- 收斂 launch announcement，讓對外說明可以直接發布
- 固定核心資料鏈路為 `FIT -> Excel -> SQLite -> Semantic Layer -> Dashboard`

## Notes

- 這是本機優先、knowledge-first 的跑步分析產品
- 設計理念是先治理資料，再讓頁面長出來
- `v1.0.0` 是產品對外的正式起點

