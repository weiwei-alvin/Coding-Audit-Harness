# 變更紀錄

## 2026-10-26 — V2.1 assurance milestone／Software Development Assurance Harness

- 專案正式更名為 `Software Development Assurance Harness`（原 `Coding Audit Harness`），GitHub Repository 名稱與定位描述同步更新；五份 README 及後續 Audit Console 規劃文件已統一品牌。
- 整合 PR [#1](https://github.com/weiwei-alvin/software-development-assurance-harness/pull/1) 和 [#2](https://github.com/weiwei-alvin/software-development-assurance-harness/pull/2)，新增可追溯的 UI 契約驗證：Token 與色彩配對檢查、DESIGN/final 收據新鮮度、成功標準依據與未決問題延後規則、Story-scoped shared components、表單與 state variants、結構化 scope findings、AC 品質警告、一鍵產生版本化設計交接。
- CI 新增 README 連結檢查及 Ubuntu Chromium 實際單案例統一 E2E。合併後 Windows、Ubuntu 皆通過 201/201 Python 回歸測試；Chromium 流程檢查 37/37 通過。歷史 T-005 SHA 基準比對為 `NOT_RUN`，未提供跨瀏覽器或真人／輔助科技驗收。
- 詳見 [V2.1 里程碑與驗證證據](releases/2026-10-26-v2-1-assurance.md)；本次紀錄**不表示正式 GitHub Release 或 Git tag 已發布**。


## 2026-10-20 — P2 審查後修復（agy round 1）

- **F-01（major）**：`required_evidence_tiers` 只在 `PASS` 驗收時強制；`FIX_REQUIRED`／`USER_DECISION_REQUIRED` 仍可提交並記錄，避免設有 tier 要求的 stage 無法進入「失敗→修正→PASS」流程。`declared` 的 `source`／`limitations` 仍在所有 verdict 檢查。新增兩個回歸測試。
- **F-02（minor）**：核准計畫指紋納入 `.harness/pipeline.json`；Gate PASS 後修改 pipeline 定義會觸發 `PLAN_CHANGE_REQUIRES_DECISION`，不再靜默採用新 stage／gate 定義。新增回歸測試。
- **F-03（minor）**：`review-result.schema.json` 對 `tier: "declared"` 加上條件必填 `source`／`limitations`（non-empty），讓獨立 payload validator 與 runtime 一致；新增 schema 負例測試。`test_state_transition.py` 的 docstring 明示 canonical 入口是 `run_tests.py`，直接 `python -m unittest` 不適用於此 legacy function-style 模組。
- 測試數 156 → 160，`python harness/runner/run_tests.py` 全綠（160/160、protected state unchanged）。

## 2026-10-20 — P2 kernel：pipeline 定義、typed verification、三層證據

- Stage 定義移出程式碼：`.harness/pipeline.json` 宣告 stage 順序、planning／execution 類型、gate verdict、`next`、hook 與 `required_evidence_tiers`；`init` 缺少定義檔時拒絕並明示原因，不再猜預設。既有 state 沒有 `pipeline_definition` 記錄時，執行期才回退到 `harness/pipeline.default.json`。
- Golden Path step 可宣告 `verification_type: "collector"` 與 `expected_artifacts`；收據新增 `tier` 與 `artifacts`（專案相對路徑＋SHA-256），宣告的 artifact 缺失即 FAILED、`verify-ticket` exit 非 0。未宣告型別的舊 step 仍是 assertion，行為不變。artifact 目錄可用 `source_hash_exclude` 排除，變更偵測仍覆蓋原始碼與計畫檔。
- Review criteria 新增必填 `tier`（`deterministic`／`captured`／`declared`）。`declared` 缺 `source` 或 `limitations` 一律拒收；execution stage 可用 `required_evidence_tiers` 要求三層齊備。舊 review payload 沒有 `tier` 會被明示拒收，歷史 review／verification artifact 不改寫。
- README 補上 pipeline 定義、collector step、新收據欄位與 review tier 範例；快速上手改為先複製 `harness/pipeline.default.json` 到 `.harness/pipeline.json`。
- 測試數 119 → 156（新增 pipeline 資料驅動、typed verification、三層證據測試），`python harness/runner/run_tests.py` 全綠。

## 2026-10-01 — Golden Path 必須對應 User Story

- TICKETS Gate PASS（以及計畫變更後的 `resume`）新增檢查：`SPEC.md` 必須存在並在「User Stories」段落以 `US-NNN` 定義需求、ID 不可重複；每個 Golden Path step 的 `user_story_ids` 不可為空且只能引用已定義的 ID；每個 User Story 至少被一個有指令的 step 覆蓋。過去 `user_story_ids: []` 也能過關，驗收可以跟任何需求都無關。
- `to-spec-audit` 要求 User Story 清單項目以 `US-NNN` 開頭；`to-tickets-audit` TKT-5 加入 User Story 對應規則。
- README 補上稽核技能與 Matt Pocock 五個技能的對應（`*-audit` 為入口、內部呼叫上游），說明 DISCOVERY／SPEC 只有 agent 自我稽核；快速上手加入 `SPEC.md` 步驟。文件版本 3.0.0 → 3.1.0。
- 測試 fixture 加上 `SPEC.md`；新增 7 個 Gate 回歸測試（共 119 個）。
- 中文副標題改為「AI 寫的程式，驗過才算數」。新增簡體中文（`README.zh-CN.md`，大陸用語）、英文（`README.en.md`）、法文（`README.fr.md`）、新拉丁文（`README.la.md`）版 README，五份互相連結，章節、程式碼區塊與表格與繁中版一一對應。

## 2026-10-01 — README 重構

- README 改為「情境 → 元件心智模型 → 一次完整工單旅程 → 細節」的信息順序。開頭用一個 AI coding 的具體失敗情境說明工具為什麼存在，前 20% 足以回答「做什麼／防什麼／各元件角色／為何不能只信 Agent／工單如何走完」。
- 五個元件改用比喻帶入（audit skills＝規則書、Runner＝裁判、state.json＝流程紀錄、evidence＝驗收收據、Gate＝關卡），比喻後緊接正式定義。
- 術語下沉：`source_hash`／`verification_id`／`review_round`／Golden Path 等技術細節移到讀者已建立流程心智模型之後，且首次出現即附中文解釋。
- 補上原本完全沒寫的部分：三層分工、`.harness/` 執行時目錄結構、五個輔助 CLI 的指令表、完整 Runner 指令表與全域參數、快速上手第 0 步（把 `harness/` 複製進目標專案）。
- 明確寫出 `init` 直接把階段設為 `TICKETS`，因此 `DISCOVERY` 與 `SPEC` 沒有 CLI 路徑可達；這兩階段目前只由 agent 側 audit skills 自律執行。
- 補上 `--timeout` 合法範圍、未帶 `--trust-commands` 時的拒絕行為、指令與模組數量。
- 文風掃掉 AI 痕跡：破掉「不是 X，是 Y」式對稱排比與三項等長列舉、刪 meta 開場白與預告句、統一 CLI 語境的「命令／指令」用字（20 處 → 單一用語）、減少機械式粗體（84 → 77）。
- 保留全部原有的信任界線、雜湊／鎖／artifact 順序語意與 Gate 規則，未刪減任何限制條件。文件版本 1.1.0 → 3.0.0。

## 2026-09-30 — 發布目錄整理

- 移出舊專案 ZIP、Python 快取、根目錄一次性 JSON 測試資料及歷史審查產物。
- 移出舊登入系統的 SPEC 與 `.harness/` 狀態；新使用者依 README 在目標專案建立資料。
- 保留全部正式測試、audit skills、上游依賴及其授權文件。
- 測試結果統一預設寫入 `test-results/`，並排除於 Git。
- 新增 `requirements.txt`；README 與 CI 共用依賴安裝方式。
- 將歷史可靠性及審查修復報告整理為以下摘要。

## 2026-09-29 — 可靠性與流程修復

- 完成工單須具備綁定 ticket、review round、source hash 與 verification ID 的驗證及審查證據；最後一張工單完成前重跑全部 Golden Path。
- 修正依賴排程、跨檔 schema 引用、finding 重開狀態及省略 Expected 的解析；未支援命令明確失敗。
- pause/resume 綁定當次決策並保留重試歷史；新增 state lock 與 stale-writer 拒絕。
- 外部命令須明確授權，加入 timeout 子程序清理與環境變數過濾；所有正式測試使用隔離暫存專案。
- TICKETS Gate 檢查每張工單都有可執行的驗證步驟；跨工單整合步驟不能取代單張工單驗證。
- 核准計畫加入內容雜湊；計畫改動須經決策及重新驗證，禁止以放寬驗證規則直接繞過流程。
- 加入 `source_hash_exclude` 與 `env_passthrough`，同步 audit skills 的命令、路徑及 payload 格式。

## 已知界線

工具供可信本機專案與單一操作者使用，不是 sandbox；沒有 Agent runtime、LLM/MCP 串接或多人協作機制。命令輸出量未設硬上限；舊版 pause 無自動遷移。完整操作與信任界線以 [README](../README.md) 為準，未實作項目見 [Deferred Items](DEFERRED_ITEMS.md)。
