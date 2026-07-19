# CoachOS v1.4.0 正式發布

CoachOS v1.4.0 是 `Workout Sequence Intelligence Product Layer` 的第一個正式版本。

## 中文

CoachOS v1.4.0 的重點，是把訓練序列理解從研究文件帶進日常產品介面。

過去 CoachOS 已經能整理單堂課、週回顧與月回顧；這一版開始，它會把每一堂課放回前後訓練裡看，並用跑者真正看得懂的教練語言呈現出來。Activity 會回答「今天這堂課的位置」，Weekly 會回答「這週真正留下來的是什麼」，Monthly 則會回答「這個月最後建立了什麼」。

這代表使用者不需要理解 WSI 裡的 Mission、Status 或 Continuity。CoachOS 會把這些推理翻譯成像「準備下一堂」、「已準備好下一堂」、「以銜接為主的建構月」這樣的產品語言。

這一版也讓 WSI 進入 AI 交棒與資料匯入工具。AI 延伸分析會先收到序列理解，再做後續推理；既有 SQLite 活動也可以從資料匯入工具批次重算 WSI。Excel 則維持單純，不塞入 WSI 欄位，讓檔案仍然保留作為乾淨資料交換格式。

如果說 v1.3.6 是把資料校準乾淨，那 v1.4.0 就是讓 CoachOS 開始真正用教練的時間尺度說話：今天、這週、這個月，各自回答不同層級的訓練問題。

## English

CoachOS v1.4.0 is the first release of the `Workout Sequence Intelligence Product Layer`.

This release brings sequence-aware coaching into the everyday product experience. Activity now explains where today’s workout sits in the surrounding training sequence. Weekly summarizes what the week actually left behind. Monthly turns the month into a coaching position rather than a raw mission count.

The user does not need to understand Mission Category, Mission Status, or Continuity State. CoachOS translates those internal judgments into product language that feels closer to what a coach would actually say.

WSI also now flows into AI handoff, so external AI analysis starts from sequence understanding rather than raw activity facts alone. Existing SQLite activities can be recomputed from the import tool, while Excel remains intentionally simple and does not export WSI fields.

## 這個版本代表什麼

- `v1.3.6`：把 daily use 裡最容易失真的地方校正乾淨
- `v1.4.0`：把訓練序列理解正式變成產品語言
- 下一步：讓 Overview 接上同一套跨時間尺度的教練語言

## 目前版本狀態

- `v1.4.0` 準備發布
- `Workout Sequence Intelligence` 已接進 Activity / Weekly / Monthly / AI 交棒
- 資料匯入工具可批次重算 SQLite 裡的 WSI
- Workbook schema 仍維持 `v1.1`

CoachOS 現在開始回答的不只是「這堂課跑了什麼」，而是「這堂課、這週、這個月，在整個訓練裡代表什麼」。
