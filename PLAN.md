# Coding Audit Harness — Audit Console PLAN.md（後續獨立里程碑）

> **命名與範圍澄清（2026-10-24）**：本檔描述的「Audit Console」（本機 Web UI）保留為**後續獨立里程碑**，不與 `milestone.md` 的「UI Design Integration」主線並行。「V2」一名保留給 `milestone.md`；本方向不再稱「Coding Audit Harness 2.0」。
>
> Status: PROPOSED（deferred）· 2026-10-19
> Product: Audit Console（本機 Web UI，後續里程碑）
> UI module: Audit Console
> Scope: Single-user local developer experience, CLI UX, and evidence-first review UI

## 1. 目標與定位

Coding Audit Harness 2.0 要讓使用者能從單一操作介面了解專案狀態、檢視工單與驗證證據、執行允許的工作流程，以及做出有依據的人工審查決策。原有 Runner 仍是狀態轉換與證據驗證的唯一權威。

2.0 的成功標準不是「有 Dashboard」，而是新使用者能完成一個示範工單的 Gate、驗證、handoff、Review 流程，並在發生錯誤時知道原因及正確的恢復方式，且 UI 無法繞過 Runner 的任何完成條件。

### 設計原則

1. **Runner-authoritative**：UI 不直接寫入 `.harness/state.json`、受控證據或審查歷史；不自行宣告 `PASS`/`COMPLETE`。
2. **Evidence-first**：核准前呈現可追溯收據、指紋、審查判準、阻擋性問題與已知限制。
3. **Progressive disclosure**：先顯示「目前狀態、阻擋原因、下一步」，再按需展開 `source_hash`、`verification_id`、原始 JSON 與 stdout/stderr。
4. **Safe by default**：不自動核准；需執行 Golden Path 指令時明確提示其以目前 OS 使用者權限運行，並取得當次授權。此工具不提供 sandbox。
5. **CLI parity**：保留完整既有 CLI 路徑；GUI 是另一個入口，不提供任何繞過 CLI/Runner 規則的捷徑。

## 2. 範圍

### 2.0 必做（MVP）

- **README 與 Onboarding**：重整 README 首屏，明確說明價值、適用對象、限制與快速入口；新增可直接使用的 calculator example，並保留完整手動示範步驟。
- **CLI UX**：對常見錯誤提供可讀的錯誤代碼、原因、受影響的狀態與合法下一步；不淡化安全相關警告。
- **Audit Console（本機 Web UI）**：顯示專案摘要、階段、active ticket、依賴與阻擋原因、已核准計畫、各項 Golden Path 驗證結果、受控收據、handoff、review findings 及審查歷史。
- **Gate 操作**：在 TICKETS 階段展示工單圖、每張工單的必要 Golden Path coverage、User Story coverage 與目前計畫指紋；讓操作者確認後呼叫既有 `set-ready-for-gate` / `gate-verdict`。不得假稱 DISCOVERY/SPEC 已受到 Runner 階段強制。
- **T-001 Review 工作流（可套用到其他工單）**：支援 PASS、FIX_REQUIRED、USER_DECISION_REQUIRED 三種決策，根據既有 schema 編輯或產生 payload，顯示預檢結果、操作影響與最後確認，再透過 Runner 提交。
- **失敗恢復 UX**：針對 stale hash、核准計畫變更、缺少證據、blocking finding、修正次數上限、PAUSED、並行狀態衝突，顯示理由和合法恢復步驟。

### 2.0 不做

- Agent runtime、LLM 直接呼叫、MCP orchestration、排程、多人協作、登入與 RBAC。
- 改寫 Golden Path 驗收邏輯、放寬審查條件或直接編輯 runtime state。
- 將 hash 宣稱為防竄改簽章，或將本機 Web UI 宣稱為沙箱／安全隔離環境。
- 新增無依據的 PASS override、ABORT、INVALIDATE 等操作。
- 以 GUI 存在為理由，宣稱 DISCOVERY / SPEC 的階段控制已實作。

## 3. 使用者旅程與資訊架構

主導覽僅保留：**Overview → Tickets → Evidence & Review → Decisions**。以當前 active ticket 為主要操作焦點；文件與技術設定置於次層。

### 3.1 Overview

必須顯示：`project_status`、`pipeline_stage`、`stage_status`、`active_ticket_id`、工單完成數量、目前待處理事項及下一個合法動作。若為 PAUSED，首頁優先顯示 pause reason 和 decision ref，且停用不合法操作。

### 3.2 Tickets

每張工單顯示：ID、名稱、狀態、直接相依工單、阻擋原因、對應 User Stories/Golden Path steps；可展開原始工單內容。僅在 Runner 規則允許時提供啟動與標記待審操作。

### 3.3 Evidence & Review

將「機器執行證據」與「人工審查判斷」分為兩個區塊：

- 執行證據：step ID、命令、PASSED/FAIL/UNVERIFIED、return code、收據引用、當前與收據 source hash 是否一致；技術欄位按需展開。
- 審查判斷：review round、criteria、finding、變更摘要、人工 criterion 的 source/limitations、verdict 與影響預覽。

### 3.4 Decisions

顯示目前 pause 原因、有效決策參照、唯一可用選項、rationale 與 source；使用 Runner `decide`/`resume`，不直接編輯決策檔。若原始計畫在決策後又變更，顯示新的決策需求。

## 4. T-001 人工審查 UX 規格

> 示範假設：T-001 是 README 的 calculator 工單，`US-001` 由 `GP-001` 驗證。實際 UI 必須讀取目標專案資料，不硬編碼這些內容。

### 4.1 審查前置條件

- 專案狀態必須為 `IN_PROGRESS`。
- T-001 必須是 active ticket，狀態為 `READY_FOR_REVIEW`。
- 已核准計畫不得在 Gate 後無決策地變更。
- `review` payload 符合 `review-result.schema.json`；CLI verdict 與 payload verdict 相同。
- 若提交 `PASS`：必須有符合 `handoff.schema.json` 的 handoff，並符合 Runner 的證據與判準條件。

### 4.2 PASS 預覽與提交

1. 顯示 ticket ID、review round、計畫版本、收據時間／識別資訊（若資料有提供）、驗證狀態、阻擋問題、人工審查限制。
2. 檢查 review/handoff/receipt 的 `ticket_id`、`review_round`、`source_hash` 綁定，以及兩份 payload 與 receipt 的 `verification_id` 一致性。
3. 檢查受控 artifact 的存在及 digest；每項 receipt result 都必須為 `PASSED`、`returncode == 0`，且 `all_passed == true`。
4. 每個 receipt step 都須在 review criteria 內有唯一的 `id`，且為 `critical: true`、`status: PASS`。額外的人工必要 criterion 須為 PASS，並具有非空的 `source` 與 `limitations`。
5. 拒絕存在 OPEN/REOPENED 的 blocking findings；`PASS` payload 也不可包含 blocking finding。
6. 如 T-001 為最後一張工單，告知使用者 Runner 還會執行 Final Integrated Verification。成功與否以 Runner 最終 commit 為準。
7. 操作者明確確認後，執行 `review-verdict --ticket T-001 --verdict PASS --review ... --handoff ... --trust-commands`；收到成功返回後重新讀取正式 state 和 review history，再顯示 COMPLETE 或下一張 active ticket。

### 4.3 FIX_REQUIRED

要求至少一項 blocking finding（包括穩定的 `finding_key`、對應 criterion 與問題描述），用符合 schema 的 review payload 送交 `review-verdict --verdict FIX_REQUIRED`。結果成功時呈現 T-001 回到 `IN_PROGRESS`、`review_attempts` 增加；達到 retry limit 時呈現 PAUSED。不能以自由文字取代 finding 結構。

### 4.4 USER_DECISION_REQUIRED

要求完整 `decision_context`，依既有 schema 顯示有效選項；提交後顯示 `PAUSED` 與決策參照。對 `REVIEW_USER_DECISION_REQUIRED` 只呈現既有支援的 `FIX_REQUIRED` 選項，不顯示 PASS override。

## 5. 防誤操作設計

| 風險 | UX 防護 | 最終權威 |
|---|---|---|
| 頁面過期、原始碼或計畫已更動 | 確認時刷新 state、計畫與 source hash；提示重新驗證／重新決策 | Runner `check_plan`、binding、source_hash 驗證 |
| Handoff 或收據不一致 | 顯示差異欄位並禁止正常 PASS 流程 | Runner payload/schema/artifact 驗證 |
| 誤將測試通過當作品質保證 | 明顯區分「執行證據通過」與「人工核准」；顯示未涵蓋範圍 | 人工判斷 + Runner 必要判準 |
| 重複點擊或提交狀態不明 | 提交時鎖定 UI；錯誤／連線中斷後先重新讀取 state 與 review history，不盲目重送 | Runner atomic write / state conflict 保護 |
| 未經授權執行專案命令 | 每次可能執行 Golden Path 前告知 OS 權限、指令內容及非 sandbox 特性，要求明確授權 | Runner `--trust-commands` |
| 出現未知錯誤 | 顯示原始錯誤碼、受影響操作、可安全採取的步驟；保留未提交草稿 | Runner 的正式狀態 |

**信任邊界：** UI 上的核准確認是防誤操作設計，並非已實現的身分驗證或「人類在場」強制安全邊界。現有 CLI 與本機檔案對同權限操作者沒有防竄改保證。

## 6. 建議技術實作方式

採用**本機 Web Console + 薄型本機服務／adapter + 現有 Runner**。本機服務僅負責讀取、轉譯、驗證 UI 輸入和呼叫允許的 CLI 操作，不獨立維護 workflow state machine。

- 審查或 Gate 提交直接委派現有 Runner 指令；保留它的 exit code、stdout/stderr 與原子寫入結果。
- 透過獨立 adapter 將 Runner state、verification receipts、review history 轉成 UI view model；不增加第二份權威 state。
- 服務預設只綁定 loopback，對跨來源請求進行防護，避免其他網頁任意觸發本機操作；禁止對外暴露能任意執行指令的 endpoint。
- payload 先按現有 schema 預檢，但正式提交時一律由 Runner 再驗證。
- 以最小組件與最少依賴實作；先完成單一專案、單一 operator 的垂直切片。無須為未確立的遠端與多使用者需求設計架構。

## 7. 實作順序與交付成果

### Phase 1 — 基線與開發者體驗

- 盤點既有 Runner 指令、state schema、review/handoff schema、證據與 Gate 規則，產生實作映射。
- 重整 README：價值主張、快速開始、使用限制、參考連結。
- 加入可重複執行的 calculator demo（使用隔離／一次性範例目錄，不覆蓋現有 `.harness`）。
- 改善常見 CLI 錯誤：明確原因、狀態與合法恢復路徑。

**完成條件：** 新使用者可按照文件在乾淨的範例中完成一次工作流；既有測試不退步。

### Phase 2 — Audit Console 最小可用流程

- 實作本機服務／adapter 與 Overview、Tickets、Evidence & Review、Decisions 畫面。
- 完整支援 TICKETS Gate 的可見性與人工操作。
- 以 T-001 審查作為第一條端到端切片：讀取真實證據、編輯合法 payload、確認與送交 Runner、重新讀取提交結果。
- 實作三種 review verdict 與 pause/decision 的已支援分支。

**完成條件：** 單一使用者能不手動編輯 JSON 完成 calculator 示範的正式流程；無法經由 UI 提交繞過 Runner 的 PASS。

### Phase 3 — 錯誤體驗與回歸驗收

- 測試 stale state、hash mismatch、missing receipt、invalid handoff、blocking finding、retry limit、plan change、final integration failure。
- 檢查 Windows/Ubuntu 平台的 Runner/Console 一致性；確認 CLI 與 GUI 不產生不同的 state 結果。
- 確認鍵盤操作、focus、非顏色狀態辨識及錯誤訊息可讀性。

**完成條件：** 下節列出的主要防誤操作測試全數通過，並提供可重現的測試紀錄。

## 8. 核心驗收案例

1. 尚未 `READY_FOR_REVIEW` 的 T-001 不能提交 review。
2. 修改原始碼導致收據 `source_hash` 過期時，PASS 不得完成。
3. Handoff `verification_id` 不符收據時，PASS 不得完成。
4. 缺失 GP-001 的 critical PASS criterion 時，PASS 不得完成。
5. 存在 OPEN/REOPENED blocking finding 時，PASS 不得完成。
6. `FIX_REQUIRED` 缺 blocking finding 時，必須拒絕。
7. `USER_DECISION_REQUIRED` 只能導向現有支援的決策狀態，不提供虛構覆寫功能。
8. 同一次操作重複提交或網路中斷時，UI 不可誤報完成或直接盲目重送。
9. 最後一張工單的 Final Integrated Verification 失敗時，不得顯示 COMPLETE。
10. Runner 實際提交成功後，UI 必須重新讀取正式 state 才顯示已完成及下一張工單。
11. 未授權 Golden Path 命令執行時不得偷偷加入 `--trust-commands`。
12. 既有 CLI 驗收與安全邊界測試持續通過。

## 9. 命名與版本策略

**保留專案及 Repository 名稱：`Coding Audit Harness`。** 它代表驗收框架，不限定 CLI 或 GUI。版本名稱為 `Coding Audit Harness 2.0`；新增的圖形操作介面稱為 `Audit Console`，驗證核心沿用 `Harness Runner`，既有 `Audit Skills` 不更名。

README 標題可採：

> **Coding Audit Harness**  
> Evidence-backed verification and review for AI-generated code.  
> **2.0: Audit Console + Runner + Audit Skills**

不因加入可視化介面就重命名 repository，以免破壞既有連結、使用者辨識與外部引用。若未來產品功能超出程式碼驗收範圍，再獨立評估品牌更名。

## 10. 實作約束與來源

此文件是 2.0 **規劃**，不代表 Audit Console、上述 API 或身分控管已存在。實作前以倉庫當下版本為準重新確認行為；若 README 與程式碼不符，以實際程式碼與測試查明後記錄差異。保留現有強制驗證，不以 UI 表單驗證替代 Runner。

參考實作：

- `README.md`
- `harness/runner/workflow.py`
- `harness/runner/runner.py`
- `harness/review-result.schema.json`
- `harness/handoff.schema.json`
- `harness/gate-result.schema.json`
- `docs/DEFERRED_ITEMS.md`

Repository: https://github.com/weiwei-alvin/Coding-Audit-Harness
