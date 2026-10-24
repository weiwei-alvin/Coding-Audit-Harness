---
document_title: ui-pack
chinese_title: ui-pack 註冊與啟用說明
version: 0.1.0
aka: []
established_date: 2026-10-23
updated_date: 2026-10-23
---

# ui-pack（T-009）

ui-pack 是吸收合併（absorb）自 UI-Design-Harness 的資料＋指令包：**kernel 程式不因本包改動 UI 語意**，註冊全靠 pipeline 定義檔（設定）。本目錄對每個檔案的來源與狀態：

| 檔案 | 狀態 | 說明 |
| --- | --- | --- |
| `ui_design_harness/` | 自 `D:\Workplace\01_Projects\UI-Design-Harness\ui_design_harness\`（commit 7527830，2026-10-23）原樣複製，未改寫 | 無狀態 CLI：check／guidance／rules／collect／review／fix，exit code 0/1/2 契約不變 |
| `schemas/contract.schema.json` | 自同 repo `schemas/contract.schema.json` 原樣複製 | `contract.py` 以 `parents[1]/schemas/` 相對路徑定位，目錄結構對齊後不需改碼 |
| `examples/` | 自同 repo `examples/` 原樣複製 | rules／review／collector fixtures 與 telling-time 案例（contract + build） |
| `cli.py` | 本包新增 | cwd 無關的進入 shim：typed verification command 以絕對路徑 `[python, <repo>/packs/ui/cli.py, ...]` 呼叫 |
| `pipeline.json` | 本包新增 | ui-pack 管線定義；`load_definition()` 可驗證（有測試護住） |

## 啟用方式（以設定註冊）

把 `packs/ui/pipeline.json` 複製到專案的 `.harness/pipeline.json`（或以 init 的 explicit path 指向本檔）。純 code 專案繼續用 `harness/pipeline.default.json`，管線不含 DESIGN stage，行為完全由既有測試護住。

## 管線

`DISCOVERY* → SPEC → DESIGN → TICKETS(entry) → IMPLEMENTATION → REVIEW`

- DESIGN 為條件式 stage：條件 `golden_path_declares_collector`（kernel 評估）＝專案 `.harness/golden_path.json` 宣告了任一 `verification_type: "collector"` 步驟。
- TICKETS gate 帶 `["validate_ticket_dependencies", "require_conditional_gates"]`：條件作用中而 DESIGN gate 沒有 recorded PASS 時，gate 拒收並指名 stage 與條件（US-007／US-008 的 UI 拒收防線）。
- REVIEW 階段要求三層證據齊備才收 PASS：`required_evidence_tiers: [deterministic, captured, declared]`。

## typed command 宣告（T-007 型別＋本包指令）

golden path 步驟沿用 kernel 的兩種型別，本包不新增型別：

| 指令 | 型別 | 範例 command |
| --- | --- | --- |
| UI 契約檢查（DESIGN gate 證據） | `assertion` | `[python, "<repo>/packs/ui/cli.py", "check", "--contract", "<case>/contract.json", "--stage", "design", "--documents", "<case>/docs", "--receipt", "<case>/design-receipt.json"]` |
| 規則掃描 | `assertion` | `[python, "<repo>/packs/ui/cli.py", "rules", "--input", "<build>", "--output", "<receipt>"]` |
| 瀏覽器收集器 | `collector` | `[python, "<repo>/packs/ui/cli.py", "collect", "--input", "<build>/index.html", "--output", "<evidence>"]`，並宣告 `expected_artifacts`（kernel 逐件記 SHA-256） |

執行環境：收集器需要 Playwright Chromium（`.venv\Scripts\python -m playwright install chromium`；比對 Kernel 的 1.60+）。規則掃描／契約檢查零外部依賴。

## DESIGN gate 證據

DISCOVERY／SPEC／DESIGN gate 是 operator 判斷；kernel 不驗證 planning gate 內容。典型 DESIGN 證據＝design receipt（`check --stage design`）加上 contract 文件渲染物，由 operator 自行保留於專案內。
