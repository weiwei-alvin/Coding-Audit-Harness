# AGENTS.md — Software Development Assurance Harness (SDAH)

本檔是 Codex、OpenCode、Gemini CLI 等 Agent 在此儲存庫工作的**唯一共同操作規範**。先閱讀本檔；一般介紹見 `README.md`，完整 CLI、payload 與信任邊界見 `docs/TECHNICAL_GUIDE.md`。不需要安裝或執行 `trail`。

## 儲存庫結構

- `harness/runner/runner.py`：可執行的驗收 CLI、狀態轉移入口；`harness/runner/workflow.py` 實作受控驗證與審查。
- `harness/runner/run_tests.py`：Repository 回歸測試入口。
- `harness/pipeline.default.json`：純程式專案的 Pipeline 範本，入口為 TICKETS。
- `skills/`：五階段開發與 Audit Skills（上游技能位於 `skills/matt-upstream/`）。
- `packs/ui/`：可選用的 UI Design Contract、Rules、瀏覽器證據與 Review/Fix；其 Pipeline 從 DISCOVERY 開始。
- `docs/`：技術指南、決策與發版說明；`scripts/`：驗證腳本；`.github/workflows/`：CI。
- `README.md`：一般使用者起手說明，不是 Runner 指令或驗收收據的權威來源。

**修改此 Repo 後的基本測試（在 Repo 根目錄執行）：**

```powershell
python harness/runner/run_tests.py
```

測試失敗就回報失敗原因，不可宣稱驗收完成。文件或 CLI 改動也要檢查相關 CI／整合測試。

## 使用 Harness 時的硬性規則

以下的 `.harness/` 是**目標專案根目錄**的執行資料，不是本 Repo 的範例檔案。

1. **禁止手動修改或重建** `.harness/state.json`；只能由 Runner 的受控 CLI 轉移狀態。也不可手動改成 `PASS`、`COMPLETE` 或清除阻擋狀態。
2. **禁止手動產生、篡改或刪除 Runner 的受控驗證收據與審查紀錄**：例如 `.harness/verifications/`、`.harness/reviews/`、`.harness/decisions/`。不得偽造 `verification_id`、`source_hash`、測試輸出、Review PASS 或 SHA-256。`.harness/inbox/review.json` 和 `handoff.json` 是**可正常準備的送審輸入**，不是已核准的審查紀錄；內容必須真實，並經 Runner 核對。
3. **工單的執行驗收只認** `python harness/runner/runner.py verify-ticket --ticket T-001 --trust-commands` **產生、存入受控位置且 `all_passed: true` 的收據**。自行跑 `pytest`、貼終端機輸出、在文字報告宣稱 PASS，都不能替代這份收據；UI 設計 Gate 收據是另一種階段性證據，也不能替代工單收據。
4. **TICKETS Gate PASS 與最後一張工單的 REVIEW PASS 必須由操作者在自己的互動式終端機確認。** Runner 顯示當前計畫 SHA-256，要求輸入前 8 碼。stdin 不是 TTY、輸錯或取消會以 exit code `23` 拒絕且不變更 state。Agent 不得偽造終端機輸入、修改驗證器或使用測試注入點繞過。其他 Gate/Review PASS 沒有這項終端機門檻。`--trust-commands` 僅在確認 Golden Path 指令可信且獲准執行後使用；不要以此繞過安全審查。
5. 不得使用已停用的 `complete-ticket`、`ready-for-review`、`increment-review` 來冒充正常流程。計畫（`SPEC.md`、`.harness/tickets/`、`golden_path.json`、Pipeline）核准後若有變更，按 Runner 的 `PLAN_CHANGE_REQUIRES_DECISION` 與 `decide`／`resume` 流程處理，不可直接修改 state 或收據解除暫停。原始碼在驗證後再改動，必須重新執行 `verify-ticket` 並更新送審 payload。

## 一張工單：TICKETS Gate → REVIEW PASS

**從目標專案根目錄執行下列指令。** 專案需先放妥 `harness/`、`.harness/pipeline.json`、`.harness/tickets/T-001.md`、`.harness/golden_path.json`、`SPEC.md`，且 Golden Path 的可執行驗收步驟對得上工單和 User Story。純程式專案可先把 `harness/pipeline.default.json` 複製成 `.harness/pipeline.json`。既有專案有 `state.json` 時**不得重跑 `init` 覆蓋**；直接依當前階段操作。

### 1. 初始化、核准 TICKETS Gate

新專案僅執行一次 `init`；純程式預設在 TICKETS。包含 UI 的 Pipeline 先依序完成 DISCOVERY、SPEC、DESIGN 的 Gate（必要時附通過的 DESIGN 收據），再執行下面的 TICKETS Gate。

```powershell
python harness/runner/runner.py init
python harness/runner/runner.py set-ready-for-gate
# 以下 PASS 必須由操作者審閱、核准後才執行
python harness/runner/runner.py gate-verdict --verdict PASS
python harness/runner/runner.py read
```

執行上面的 TICKETS Gate PASS 時，請在你自己的終端機核對畫面上的計畫指紋並輸入前 8 碼；非互動式 Agent shell 無法直接完成。

TICKETS Gate PASS 會檢查工單依賴、Golden Path／User Story 覆蓋並記錄計畫指紋，然後**自動啟動第一張可執行工單**（通常 T-001）。不要對已自動開工的 T-001 重複呼叫 `start-ticket`。僅在有可開工的 TODO、且沒有別張 active ticket 時，才使用 `python harness/runner/runner.py start-ticket --ticket T-002` 等指令。

### 2. 實作、由 Runner 執行 Golden Path 並取得收據

完成 T-001 的實作與測試後，確認 Golden Path 指令安全並獲允許，才執行：

```powershell
python harness/runner/runner.py verify-ticket --ticket T-001 --trust-commands
python harness/runner/runner.py mark-ticket-ready-for-review --ticket T-001
```

`verify-ticket` **必須成功回傳 `all_passed: true`**，其受控收據須包含 `ticket_id`、`review_round`、`source_hash`、`verification_id`、每個步驟的狀態與執行結果；FAIL 時不可進入 REVIEW PASS。`--trust-commands` 是允許執行專案指令的明確選項，不是證據豁免。

### 3. 準備送審輸入，才可 REVIEW PASS

根據**剛剛的 verify-ticket 收據**準備 `.harness/inbox/review.json` 和 `.harness/inbox/handoff.json`；兩份都要帶相同且真實的 `ticket_id`、`review_round`、`source_hash`、`verification_id`。Review 的 `verdict` 設 `PASS`、`findings` 列出實際發現、所有已啟用的 Golden Path 步驟均需對應 `critical: true`、`status: PASS` 的 criterion（`tier` 與收據一致）。人工宣告的必要 criterion 必須有可追溯的 `source` 與 `limitations`，不得照抄虛構觀察。Handoff 的變更與驗證敘述須符合實際結果。

```powershell
python harness/runner/runner.py review-verdict --ticket T-001 --verdict PASS --review .harness/inbox/review.json --handoff .harness/inbox/handoff.json --trust-commands
python harness/runner/runner.py validate
python harness/runner/status.py --json
```

若 T-001 是**最後一張工單**，這個 REVIEW PASS 同樣要求操作者在互動式終端機輸入計畫指紋前 8 碼；缺 TTY 則不會完成工單。

`review-verdict PASS` 會核對來源指紋、收據 ID、判準、未解阻斷問題；**最後一張工單**還會跑整合驗證（UI Pipeline 另要求新鮮 final contract receipt）。只有 Runner 接受 PASS，工單才會變成 COMPLETE；非最後一張完成後，Runner 可自動啟動下一張。

若 Review 為 `FIX_REQUIRED`，使用有效的 `--review` payload 執行 `review-verdict --ticket T-001 --verdict FIX_REQUIRED --review .harness/inbox/review.json`，修正後重新 `verify-ticket`、`mark-ticket-ready-for-review`、提交新一輪的 review/handoff；**不得跳過重驗或手改收據**。

**可獨立複述的最短正確順序：** `init`（僅新專案）→ `set-ready-for-gate` → 操作者核准 `gate-verdict PASS` → 自動開工／實作 → `verify-ticket --ticket T-001 --trust-commands` → `mark-ticket-ready-for-review --ticket T-001` → 根據該收據建立 review＋handoff → `review-verdict --ticket T-001 --verdict PASS --review ... --handoff ... --trust-commands` → `validate`／`status`。缺受控 verify-ticket 收據、缺核准或證據不新鮮，一律不得宣稱完成。
