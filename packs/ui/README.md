---
document_title: UI pack
chinese_title: UI pack 註冊、契約檢查與證據綁定
version: 0.2.0
aka: []
established_date: 2026-10-23
updated_date: 2026-10-25
---

# UI pack

UI pack 是 Coding Audit Harness 的選用元件。它提供 UI 設計契約、規則檢查、瀏覽器證據收集、Review/Fix 與故事交接。Runtime kernel 本身不判斷 UI 視覺品質。

此目錄 `packs/ui/` 是目前整合版本的來源。歷史 UI-Design-Harness 不能視為同步的最新版本。

## 啟用與檔案位置

把 `harness/` 和 `packs/ui/` 原結構複製到目標專案，將 `packs/ui/pipeline.json` 複製到 `.harness/pipeline.json`。純 code 專案繼續使用 `harness/pipeline.default.json`，不會要求 UI 證據。

預設 UI 專案目錄結構：

```text
contract.json
docs/
design-receipt.json
packs/ui/
.harness/pipeline.json
```

`DESIGN` 階段的 `gate_receipt` 宣告位於 `packs/ui/pipeline.json`，其中路徑皆相對於專案根目錄。實際採用其他檔名或位置時，必須同步修改專案的 `.harness/pipeline.json`。不會自動搜尋或猜測證據。

管線為 `DISCOVERY → SPEC → DESIGN* → TICKETS → IMPLEMENTATION → REVIEW`。`*` 表示條件式守衛：有 collector 時，TICKETS gate 要求 DESIGN 已 PASS；目前仍會依固定順序走過 DESIGN，沒有自動跳過的分支。

## DESIGN Gate：先生成，再檢查，再核准

在專案根目錄執行：

```powershell
python packs/ui/cli.py render --contract contract.json --stage design --output docs
python packs/ui/cli.py check --contract contract.json --stage design --documents docs --receipt design-receipt.json
```

`check` exit 0 且回報 `status: PASS` 後，才可執行 Runner 的 `set-ready-for-gate` 與 `gate-verdict --verdict PASS`。Runner 現在會重新比對：

- 契約原始檔的 SHA-256（`source_hash`）
- pack 檢查器及契約 schema 的內容 SHA-256（`engine_hash`）
- 收據記錄的每個渲染文件 SHA-256（`document_hashes`）
- 收據的 `status: PASS`、`stage: design` 與證據用途

若收據不存在、不是 PASS、契約／引擎／文件後來有變更，DESIGN PASS 會被拒絕。collector 條件啟用時，TICKETS Gate 也重新檢查該證據，防止中途沿用過期 PASS。修改後必須使用新路徑或清理受控的舊輸出，重新 render 與 check；渲染和收據命令維持 create-only，不覆蓋既有檔案。

這是**內容新鮮度與結構性驗證**。它不能保證介面易用、符合審美或實際通過 WCAG，也不是防同權限惡意使用者的安全簽章。色彩對比僅檢查契約中明確宣告的 `design.color_pairs`；不能取代瀏覽器實測或人工確認。

## Color pairs（選用）

```json
"color_pairs": [
  {
    "id": "PAIR-001",
    "foreground_token_id": "TOK-003",
    "background_token_id": "TOK-002",
    "usage": "text"
  }
]
```

Token 要宣告在 `design.tokens`。color 必須使用六位色碼 `#RRGGBB`；spacing 與 layout token 必須為 `px` 或 `rem` 數值。`usage: text` 對比門檻 4.5:1，`usage: component_boundary` 為 3:1。這是可配置的**一般文字／非文字邊界簡化門檻**，目前不包含大字豁免、透明色、漸層、動態背景或實際 CSS 色彩組合。

## V2.1 契約規則與一次執行指令

`brief.unknowns[]` 的非阻斷問題必須帶 `deferred_to`（`design`、`implementation`、`review`）；延期到 design 的問題，在設計關卡前要解決。Guidance 若發現延期到 implementation（或更早）的問題尚未解決，拒絕產生交接。

`brief.success_criteria[]` 必須帶 `basis`（`data`、`stakeholder`、`proposal`）。`proposal` 可以作為設計階段的待驗證假設，但 `check --stage final` 會拒絕把它當成最終驗收門檻。這是收據檢查，不能取代 Operator 的最終實質審核。

設計規則可用 `@TOK-011` 引用 Token 並在 `token_ids` 明示 `["TOK-011"]`。Guidance 會輸出 `resolved_statement` 和 `resolved_verification`，依目前 Token 數值展開，不沿用寫死的尺寸或色碼。兩處引用須一致，否則設計關卡拒絕。檢查器不會自動更新專案 CSS。

`design.components[]` 可設 `shared: true` 表示獨立共用元件，不計入畫面根節點。Guidance 以 `shared_components[]` 將這些元件以 `read_only: true` 引用，`screen_ids` 只包含該 Story 擁有的畫面，不會帶入其他 Story 的 AC 或狀態。

表單可在 `brief.data_density.form` 填寫 `field_count`、`required_count` 與 `conditional_groups`。同一 screen state 可用 `variant` 區分不同流程，如 `loading:save` 與 `loading:submit`；每個 variant 都需要獨立的必要 UI-AC，否則設計關卡拒收。籠統的 Given/When 會產生 `VAGUE_AC` 警告，但警告不會單獨使關卡 FAIL。

```powershell
python packs/ui/cli.py pipeline --contract contract.json --output outputs
```

指令依 `metadata.version` 建立全新 `outputs/<version>/`，生成兩份（discovery、design）關卡收據、每個 User Story 的 Guidance，以及 `summary.json`。重複執行相同版本會拒絕覆寫。此指令**不會**代替 Kernel 的 `gate-verdict`、執行實作、Browser Review 或人類核准。若要將產生的收據用於 Kernel DESIGN Gate，須把專案 `.harness/pipeline.json` 中的 `gate_receipt.path`、`documents` 指向 `outputs/<version>/design-receipt.json` 和 `outputs/<version>/design`。

在最終驗收前另執行：

```powershell
python packs/ui/cli.py check --contract contract.json --stage final --documents outputs/<version>/design --receipt receipts/final-receipt.json
```

`status: PASS` 僅確認契約的 final basis／未決事項與設計結構；不宣稱完成實作或 UI 實機驗收。預設 UI Pipeline 的 `REVIEW.review_receipt` 指向 `receipts/final-receipt.json` 並會在 Review PASS 前重新核對契約、檢查器與文件 SHA-256；請把 `documents` 配置同步改為 `outputs/<version>/design`，否則預設值 `docs` 仍會造成拒收。正式的 Golden Path 也應列出相應的 final 契約檢查與實機驗收，不能只依摘要的 `final_gate_eligible`。

## 其他可用指令

| 指令 | 用途 |
| --- | --- |
| `guidance` | 依 User Story 與有效設計收據產出交接資料 |
| `rules` | 靜態 UI 規則掃描 |
| `collect` | Playwright/Chromium 收集瀏覽器證據，需另行安裝 |
| `review` / `fix` | 綁定 UI 審查結果、追蹤問題與修正 |

UI project 的 Golden Path 可使用 `assertion`（check、rules）與 `collector`（collect），並為 collector 宣告 `expected_artifacts`。REVIEW 階段要求 `deterministic`、`captured`、`declared` 三層證據；僅 DESIGN PASS 不等於 UI 最終驗收。
