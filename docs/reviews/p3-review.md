# P3 獨立審查記錄（agy）

- 審查對象：commit `a5b9ecc`（P3 統一驗收）
- 審查者：agy CLI（plan mode，唯讀）
- 執行時間：2026-10-24 14:38
- exit code：0

---

Verdict: P3_ACCEPTED

---

### 1. Blocking findings
無（No blocking findings）。

---

### 2. Non-blocking notes

#### Note 1: `pipeline_definition.py` 語法檢查變數判斷筆誤
- **檔案與行號**：[harness/runner/pipeline_definition.py](file:///D:/Workplace/01_Projects/Coding-Audit-Harness/harness/runner/pipeline_definition.py#L172-L180)
- **問題**：在 `_semantic_errors(data)` 函式中：
  ```python
  if hook_name == "on_gate_pass":
      hooks = [hook] if isinstance(hook, str) else hook
      if isinstance(hook, list):
          for name in hooks:
              if name not in GATE_HOOKS: ...
  ```
  前一行已建立正規化清單 `hooks`，但後一行判斷條件誤寫為 `if isinstance(hook, list):`（檢查原始變數 `hook`）。當 `on_gate_pass` 為單一字串（如 `"validate_ticket_dependencies"`）時，此分支不會執行。
- **影響評估**：無安全漏洞。因為 `load_definition` 在進入 `_semantic_errors` 前已先跑 `Draft202012Validator(schema)`，`pipeline.schema.json` 中的 `enum` 已嚴格限制字串必須為 `"validate_ticket_dependencies"` 或 `"require_conditional_gates"`，非法字串會在 Schema 驗證階段被阻擋。
- **建議**：改為 `if isinstance(hooks, list):` 或直接遍歷 `for name in hooks:`，使語意檢查函式具備獨立防禦力。

#### Note 2: `_condition_active` 讀檔編碼與語法錯誤靜默處理
- **檔案與行號**：[harness/runner/state_transition.py](file:///D:/Workplace/01_Projects/Coding-Audit-Harness/harness/runner/state_transition.py#L264-L267)
- **問題**：`_condition_active` 以 `encoding="utf-8"` 讀取 `.harness/golden_path.json`，且 `except (OSError, ValueError): return False`。若 Windows 環境下檔案帶有 UTF-8 BOM，`json.loads` 會拋出 `JSONDecodeError`（繼承自 `ValueError`），導致 `_condition_active` 判定為 `False`。此外，若 JSON 語法損毀，亦會被靜默當成「未宣告 collector」。
- **影響評估**：在正規流程中，`Workflow.gate` 在呼叫 StateTransitionEngine 前會先跑 `coverage_errors`，該處透過 `GoldenPathVerifier` 解析檔案，遇語法錯誤或 BOM 會直接拋錯中斷，因此在 Workflow 層不會被繞過。但若透過單元測試或底層 Engine 直接呼叫，會產生靜默降級。
- **建議**：改用 `encoding="utf-8-sig"`，並在 JSON 解析失敗時拋出或回報錯誤，而非靜默回傳 `False`。

#### Note 3: `verify_unified_e2e.py` 舊證據預設路徑與封存目錄脫節
- **檔案與行號**：[scripts/verify_unified_e2e.py](file:///D:/Workplace/01_Projects/Coding-Audit-Harness/scripts/verify_unified_e2e.py#L190-L191)
- **問題**：腳本內 `old_evidence` 預設路徑為 `D:\Workplace\01_Projects\UI-Design-Harness\outputs\validation\t005-e2e-fix1`。因 UI-Design-Harness 本體已唯讀封存並移至 `D:\Workplace\04_Archives\UI-Design-Harness`，未來若有維護者直接無參數執行此腳本，會因找不到來源目錄而失敗。
- **建議**：預設路徑加入 fallback 檢查 `04_Archives` 目錄。

#### Note 4: 靜態管線結構與條件式 Stage 語意
- **檔案與行號**：[packs/ui/pipeline.json](file:///D:/Workplace/01_Projects/Coding-Audit-Harness/packs/ui/pipeline.json#L24-L35)
- **分析**：目前 `packs/ui/pipeline.json` 的 Stage 順序為單向鏈（`DISCOVERY -> SPEC -> DESIGN -> TICKETS`），`SPEC.next` 固定為 `"DESIGN"`。此時 `conditional: true` 與 `require_conditional_gates` 的實際語意為「**閘門守衛（Guard）**」，即：若啟用了 collector，則進入 TICKETS 前必須完成 DESIGN PASS，不能跳過；而非動態分支跳過 Stage。這符合當前架構設計，但後續若要支援「無 collector 專案使用 ui-pack 時自動跳過 DESIGN」，需進一步實作條件式分支躍遷。

---

### 3. 審查範圍與查核結果

#### (1) 正確性分析（Correctness）
- **多 Hook 語意**：
  - `pipeline.schema.json` 採用 `oneOf` 支援單一字串相容與 `minItems: 1, uniqueItems: true` 的陣列模式，並限制 enum。
  - `pipeline_definition.py` 的 `gate_hooks()` 將 `None` 轉為 `[]`、字串轉為單元清單、陣列轉為清單，介面統一。
  - `conditional_stage_errors()` 確保只要宣告了 `require_conditional_gates`，所有標記 `conditional: true` 的 stage 之 `condition` 必須存在於 `CONDITION_KEYS`（目前包含 `"golden_path_declares_collector"`），否則 pipeline 載入即拒絕，無法偽造或宣告不可執行的條件。
- **Stage Gates 記錄與防禦漏洞檢視**：
  - 記錄點位於 [state_transition.py:179](file:///D:/Workplace/01_Projects/Coding-Audit-Harness/harness/runner/state_transition.py#L179)，僅在 `gate_verdict == GateVerdict.PASS` 時寫入 `new_state["stage_gates"][stage_id] = "PASS"`，`FIX_REQUIRED` 或 `USER_DECISION_REQUIRED` 絕不記錄。
  - `_conditional_gate_errors()` 遍歷所有條件式 Stage，只要條件被判定為 active，且 `state.stage_gates` 缺少對應 Stage 的 PASS，立即拒絕 TICKETS gate。
  - 舊 State 相容性：`state.schema.json` 將 `stage_gates` 設為非必填；`state.get("stage_gates") or {}` 確保無此欄位之舊狀態可正常讀取，且 pure-code 預設管線未宣告此 hook，不受任何阻擋。
- **Workflow Gate 改動等價性**：
  - [workflow.py:355-357](file:///D:/Workplace/01_Projects/Coding-Audit-Harness/harness/runner/workflow.py#L355-L357) 由原本檢查單一 hook 字串改為 `'validate_ticket_dependencies' in hooks`，對既有行為 100% 等價，且後續流程與 `approved_plan` hash 機制完全維持原狀。

#### (2) 範圍紀律（Scope Discipline）
- **Kernel 邊界保持潔淨**：
  - `harness/` 核心完全無 UI 概念、無 HTML/CSS 解析、無 Playwright 引用。
  - `CONDITION_KEYS` 綁定至 P2 已建立的通用架構概念（`verification_type == "collector"`）。
- **Pack 邊界清楚分離**：
  - 所有 UI 專案規範、Schema、Collector（Playwright）、Rules、Contract 均完整收斂於 `packs/ui/`。
- **無夾帶無關改動**：
  - commit `a5b9ecc` 包含的 47 個檔案全數屬於 T-009（Kernel 守衛與 ui-pack 吸收）及 T-010（統一 E2E 驗證腳本與 fixture），無無關代碼或格式擾動。

#### (3) 測試嚴謹度（Test Defense）
- [harness/runner/test_pack_gates.py](file:///D:/Workplace/01_Projects/Coding-Audit-Harness/harness/runner/test_pack_gates.py)：實測 14 項單元測試全數通過（耗時 1.2s）。
- **守衛行為驗證**：
  - 確實包含負向測試：非法 hook 拒絕、重複 hook 拒絕、未受支援 condition 拒絕。
  - 確實包含跳關攔截測試：`test_active_design_without_recorded_pass_refuses_and_names_reason` 驗證缺少 DESIGN PASS 時 TICKETS 拒絕通過並精確報出原因；`test_legacy_state_without_history_refuses` 驗證舊狀態無記錄時亦無法跳過。
  - 包含正面測試：條件不啟用時正常放行、Pure-code 專案完全不受干擾且能平滑升級寫入 `stage_gates`。
- 全套回歸測試（174 tests）已在 `t010-superset-2026-10-24` 留存完整結果，`implementation_unchanged: True`。

#### (4) 證據誠實性核對（Evidence Verification）
實體讀取 `test-results/t010-unified-e2e-2026-10-24-fix5/` 檔案核對結果如下：

| 查核項目 | 宣告 / 記錄值 | 實際驗證比對依據 | 結果 |
| :--- | :--- | :--- | :--- |
| **CLI 步驟數** | 35 passed / 35 cases | [summary.json](file:///D:/Workplace/01_Projects/Coding-Audit-Harness/test-results/t010-unified-e2e-2026-10-24-fix5/summary.json#L36-L37) 列出的 35 個 steps 均為 `passed: true` | **一致** |
| **Case Contract SHA-256** | `ddcd2fa64b...` | 實測 `packs/ui/examples/e2e-case/contract.json` 雜湊 | **完全相符** |
| **Original Source SHA-256**| `207ce752a7...` | 實測 `packs/ui/examples/e2e-case/telling-time.html` 雜湊 | **完全相符** |
| **Final Build SHA-256** | `c22d7901da...` | 實測修復後檔案與原始 UI-Design-Harness 封存之 `final-gate.json` | **完全相符** |
| **三大 Cross-Check** | engine / document / build 全部 match | 比對 `04_Archives/UI-Design-Harness` 歷史 receipt 雜湊 | **完全真確** |
| **限制標註（Limitations）** | 誠實列出 5 項限制 | 包含單一案例限制、Chromium 快取共用、無真實無障礙/使用者測試、固定鍵盤 Tab 走訪、對比度未實測 | **誠實完整** |

---

## 4. 處置（作者回應，2026-10-24）

| Note | 處置 | 依據 |
|---|---|---|
| Note 1（`isinstance(hook, list)` 筆誤） | **已修** 為 `isinstance(hooks, list)` | `python -m unittest test_pack_gates test_pipeline_definition test_state_transition` → 39 tests OK |
| Note 2（`_condition_active` BOM／靜默 False） | **不改** | `Workflow.gate` 先以 GoldenPathVerifier 驗 golden_path，正常流程到不了靜默分支；condition 未宣告＝inactive 為刻意語意 |
| Note 3（舊證據預設路徑已封存） | **已修** 預設候選 `01_Projects` → `04_Archives`；實測解析到封存副本 | 路徑檢查輸出 `D:\Workplace\04_Archives\UI-Design-Harness\outputs\validation\t005-e2e-fix1` |
| Note 4（條件式 stage 僅為 guard，非動態跳關） | 接受並記錄為後續設計輸入 | 本批（P3）目標即為 guard；動態跳關未在 T-009 範圍 |
