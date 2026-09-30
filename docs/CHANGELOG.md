# 變更紀錄

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
