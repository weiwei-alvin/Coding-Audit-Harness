# software-development-assurance-harness V2 — UI Design Integration Implementation Directive

> **V2 主線決策（2026-10-24）**：本檔「UI Design Integration」是 software-development-assurance-harness V2 的**唯一主線**。「Audit Console」（見 `PLAN.md`／`SPEC.md`）保留為**後續獨立里程碑**，不與本檔並行實作，亦不共用「V2」命名。

你正在修改專案：

`software-development-assurance-harness`

## Objective

在不破壞 V1 的前提下，實作 V2。

V1 的核心目標是：

> 驗證 AI 是否真的寫出可運作、可驗證、符合需求的軟體。

V2 增加第二個品質維度：

> 若產品包含 UI，除了功能必須正確，也必須驗證使用者是否能透過合理、可追溯、可驗收的 UI 完成已核准的 User Stories。

V2 不應將 Harness 變成完整 Design Platform。

只新增足以形成以下閉環的能力：

User Story
→ UI Design Contract
→ Ticket
→ UI Implementation
→ UI Evidence
→ UI Review
→ PASS / FIX_REQUIRED

---

# 0. Core Architecture

V2 Pipeline：

DISCOVERY
→ SPEC
→ UI_DESIGN
→ TICKETS
→ IMPLEMENTATION
→ REVIEW
→ COMPLETE

其中：

- `UI_DESIGN` 僅在產品包含 user-facing UI 時啟用。
- CLI、API-only、library、backend-only 等沒有 UI 的專案可以跳過 UI_DESIGN。
- 不得要求 Technical Ticket 人為加入 UI。
- 不得把 UI 拆成獨立 horizontal implementation phase。
- User-facing Tickets 仍應維持 vertical slice。

UI_DESIGN 的內部方法可以使用：

- UI discovery
- information architecture
- screen planning
- user flow design
- design system
- UI critique

但這些不得各自變成新的 Harness Pipeline Stage。

UI Design 的既有方法論強調先釐清主要使用者、高頻任務、資料量、操作流程、限制與成功標準，再進入畫面與視覺設計，不應直接從 mockup 或 styling 開始。:chatgpt-content-reference{index="0"}

---

# 1. Non-Negotiable Constraints

整個 V2 實作必須遵守以下規則。

## 1.1 Preserve V1

V1 已存在的：

- Runner
- State Machine
- Payload validation
- Ticket lifecycle
- Finding lifecycle
- Retry / Pause / Resume
- Dependency scheduler
- Traceability
- Golden Path Verification
- Functional Review
- Final Integrated Verification
- CI

不得因 V2 被破壞。

所有既有 tests 必須持續 PASS。

---

## 1.2 Minimum Complete Solution

不得順便新增：

- Web Dashboard
- Figma integration
- Storybook platform
- autonomous browser design agent
- visual analytics platform
- design asset management system
- full design-token compiler
- AI image grading infrastructure
- pixel-perfect visual regression framework
- multi-agent design orchestration

除非完成 V2 核心需求必須使用。

---

## 1.3 Traceability First

任何 UI artifact 都必須能回答：

> 這項 UI decision 支援哪個已核准 User Story 或 Design Constraint？

如果不能回答，不得成為 V2 requirement。

禁止因為以下理由自行加入 UI：

- 「一般產品都有」
- 「看起來比較完整」
- 「Best Practice」
- 「未來可能需要」
- 「Dashboard 應該有」
- 「這樣比較現代」

既有 UI 設計規則本身也明確反對「Dashboard 一定要有很多圖表」、「卡片一定比表格好」、「所有資料都應放在同一頁」、「功能越多介面越完整」等假設。:chatgpt-content-reference{index="1"}

---

# Milestone 0 — Baseline Lock

## Objective

在修改任何 V2 code 前，建立 V1 baseline。

## Tasks

1. 執行完整 Harness test suite。
2. 記錄目前：
   - test count
   - PASS / FAIL
   - current main commit
3. 確認目前 Runner 可完整執行 V1 lifecycle。
4. 不修改 production code。

## Output

建立：

`docs/V2_BASELINE.md`

最低內容：

- baseline commit
- test command
- test result
- known failures
- V1 behavior summary

## Acceptance Criteria

- 現有 Harness Validation tests 全部執行。
- 若 baseline 本身有 failing test，必須明確記錄。
- 不得把既有 failure 假裝成 V2 regression。
- 此 Milestone 不得改變任何 Runtime behavior。

## Gate

只有 baseline 明確後才進入 Milestone 1。

完成後停止並回報。

---

# Milestone 1 — UI Design Contract

## Objective

先定義 V2 的 UI contract，不修改 Runner behavior。

## Tasks

建立：

`rules/ui-design.md`

並正式定義兩個 artifacts：

- `UI-SPEC.md`
- `DESIGN.md`

---

## UI-SPEC.md Contract

最低必須支援：

### 1. User Story Mapping

每個 UI requirement 必須 reference：

`US-NNN`

### 2. User Flow

唯一 ID：

`FLOW-NNN`

每個主要 UI User Story 至少對應一條 Flow。

### 3. Screen

唯一 ID：

`SCREEN-NNN`

每個 Screen 必須定義：

- purpose
- supported user stories
- supported flows
- primary actions

### 4. UI States

只要求相關狀態：

- default
- loading
- empty
- success
- validation error
- system error
- disabled
- destructive confirmation

不得強迫所有 Screen 擁有全部 states。

### 5. UI Acceptance Criteria

唯一 ID：

`UI-AC-NNN`

每條必須：

- observable
- testable 或 reviewable
- reference User Story / Screen / Flow
- 不使用模糊詞作為唯一判準

以下不得單獨作為 Acceptance Criterion：

- beautiful
- modern
- intuitive
- clean
- professional
- simple
- polished

既有 UI discovery 規則已明確要求這類抽象描述必須轉換成可檢查條件。:chatgpt-content-reference{index="2"}

---

## DESIGN.md Contract

最低包含：

- Art Direction
- Information Hierarchy
- Layout Principles
- Typography
- Spacing / Density
- Color Semantics
- Component Rules
- Interaction Principles
- Responsive Rules
- Accessibility Rules
- Do
- Don't

DESIGN.md 是跨畫面的穩定 design rules。

不得把每個 User Story 的特定 requirements 全部塞入 DESIGN.md。

---

## UI Design Gate

建立 acceptance rules：

### UI-1 Traceability

所有 UI requirements 必須可追溯至：

- User Story
或
- explicit approved Design Constraint

### UI-2 Core Task Coverage

每個需要 UI 的主要 User Story 必須至少有一條 User Flow。

### UI-3 Screen Coverage

每條主要 Flow 必須有足以完成該工作所需的 Screens。

### UI-4 State Coverage

重要 interaction 必須定義 relevant states。

### UI-5 Information Hierarchy

主要任務與高頻資訊優先於低頻資訊。

### UI-6 Accessibility

至少處理：

- 不只依賴顏色傳遞 critical state
- readable hierarchy
- keyboard requirements when applicable
- platform-specific accessibility requirements

### UI-7 No Speculative UI

不得建立不能追溯至 approved requirement 的：

- Screen
- Component
- Dashboard section
- Chart
- Navigation item
- Setting
- Animation
- interaction

---

## Acceptance Criteria

- `rules/ui-design.md` 存在。
- `UI-SPEC.md` Contract 明確。
- `DESIGN.md` Contract 明確。
- 每個 Entity 都有穩定 ID scheme。
- UI Gate 可明確判斷 PASS / FAIL。
- V1 code 尚未改變。
- 不增加多餘 Pipeline Stage。

完成後停止並回報。

---

# Milestone 2 — ui-design-audit Skill

## Objective

把 UI 設計方法封裝成正式 Audit Skill。

## Tasks

建立：

`skills/ui-design-audit/SKILL.md`

UI skill 的責任：

1. 讀取：
   - PLAN.md
   - SPEC.md
   - relevant existing UI
   - platform constraints
   - brand constraints

2. 執行 UI discovery。

3. 建立：
   - UI-SPEC.md
   - DESIGN.md

4. 自我檢查 `rules/ui-design.md`。

5. 不修改產品程式碼。

---

## Skill Routing

可借用既有 UI/Web design skill 思路。

過去 UI Harness 曾採用：

frontend-design
→ ui-ux-pro-max
→ design-taste-frontend
→ implementation
→ frontend-design-review
→ fix
→ Final Gate

但 V2 不要求所有 upstream skills 固定全部執行。:chatgpt-content-reference{index="3"}

設計成 conditional routing：

### Required

- UI requirement analysis
- information architecture
- user flow
- design contract generation

### Optional

只有符合任務時才使用：

- redesign existing project
- image-to-code
- animation skill
- data visualization skill
- advanced component design

---

## Acceptance Criteria

- `ui-design-audit` Skill 存在。
- Skill 不直接寫 frontend code。
- Skill 能產生符合 Milestone 1 Contract 的兩份文件。
- 缺少 required upstream capability 時明確 FAIL。
- 不 silent fallback 成 generic UI prompt。
- 無 UI 專案可以被明確判斷為 `UI_NOT_REQUIRED`。

完成後停止並回報。

---

# Milestone 3 — State Machine Integration

## Objective

讓 Runner 正式理解 `UI_DESIGN`。

## Tasks

修改 State Schema 與 State Transition Engine。

Pipeline Stage 增加：

`UI_DESIGN`

合法 Planning transitions：

SPEC / READY_FOR_GATE
→ SPEC PASS
→ UI_DESIGN / IN_PROGRESS

若 UI 不需要：

SPEC PASS
→ UI_DESIGN SKIPPED
→ TICKETS

可以採用 explicit routing event，例如：

- `UI_REQUIRED`
- `UI_NOT_REQUIRED`

不要讓 Agent自由決定 next stage。

---

## State Requirements

State 必須能明確表達：

- 是否需要 UI
- UI Design stage status
- UI Gate outcome

推薦：

```json
"ui": {
  "required": true
}
```

保持 state 最小。

不要把完整 UI-SPEC 內容複製進 state。

Artifacts 才是 design truth。

---

## Acceptance Criteria

- 舊 V1 state migration / compatibility 有明確策略。
- `UI_DESIGN` 成為合法 Stage。
- 無 UI 專案可安全跳過。
- 有 UI 專案不得未通過 UI Gate 就進入 TICKETS。
- Agent 不得自行指定 Stage。
- Illegal transitions 被拒絕。
- 原有 V1 transition tests 持續 PASS。
- 新增 UI transition tests。

完成後停止並回報。

---

# Milestone 4 — UI Traceability Extension

## Objective

把現有：

Scope
→ User Story
→ Ticket

擴充成：

Scope
→ User Story
→ UI Flow / Screen / UI-AC
→ Ticket

## Tasks

擴充 Traceability subsystem。

支援 Entity：

- `FLOW-NNN`
- `SCREEN-NNN`
- `UI-AC-NNN`

最低 relationships：

US
→ FLOW

FLOW
→ SCREEN

UI-AC
→ US / FLOW / SCREEN

Ticket
→ US
→ optional UI-AC references

---

## Ticket Rules

若 Ticket 為 user-facing 且涉及 UI：

必須 reference 至少一個：

`UI-AC-NNN`

如果 Ticket 不涉及 UI：

不得強迫建立假 UI references。

Technical Ticket 仍依 V1 rules。

---

## Acceptance Criteria

Validator 必須能偵測：

- UI User Story 沒有 Flow
- Flow 沒有 Screen
- UI-AC 沒有 upstream source
- Ticket reference 不存在的 UI-AC
- orphan Screen
- duplicate UI IDs
- dangling references

Traceability report 能顯示：

```text
US-001
├─ FLOW-001
│  ├─ SCREEN-001
│  └─ SCREEN-002
└─ UI-AC-001
   └─ T-003
```

V1 non-UI traceability 仍能正常使用。

完成後停止並回報。

---

# Milestone 5 — UI Evidence Contract

## Objective

讓 Implementation 能提交 UI Evidence，但不做 AI aesthetic grading。

## Tasks

新增：

`ui-evidence.schema.json`

或合理擴充 existing handoff schema。

每項 UI Evidence 最低包含：

- ticket_id
- ui_criterion_id
- screen_id
- evidence_type
- artifact path / reference
- viewport when relevant
- actual result

允許的 evidence_type 可先限制為：

- screenshot
- automated_test
- manual_verification

不要建立複雜 media platform。

---

## Evidence Binding

UI Evidence 應沿用 V1 evidence integrity 原則。

盡可能綁定：

- Ticket
- review round
- source hash
- verification run

如果 source code 在 evidence 產生後修改：

舊 evidence 不得直接視為 current evidence。

---

## Acceptance Criteria

- UI Ticket 可提交 UI Evidence。
- Evidence 能追溯至 `UI-AC-NNN`。
- Screenshot 不存在 → REJECT。
- Missing required viewport → REJECT。
- Wrong ticket binding → REJECT。
- Stale evidence → REJECT。
- Runner 只驗證 evidence completeness / integrity。
- Runner 不判斷 screenshot「好不好看」。

完成後停止並回報。

---

# Milestone 6 — Implementation Audit Extension

## Objective

讓 `implement-audit` 理解 UI Contract。

## Tasks

擴充：

`skills/implement-audit/SKILL.md`

對涉及 UI 的 Ticket，Implementation Context 必須包括：

- relevant User Story
- relevant UI-AC
- relevant Screen
- relevant Flow
- relevant DESIGN.md sections

不得一次把整份 Design corpus 全塞入 context。

沿用 symbol-first / minimum relevant context 原則。

---

## UI Implementation Rules

Developer 必須：

1. 實作 Ticket functional requirements。
2. 實作 referenced UI acceptance criteria。
3. 不自行新增 UI feature。
4. 產生 required UI evidence。
5. 保留 functional verification evidence。

Ticket Completion 仍然需要：

Functional Evidence
+
UI Evidence（if required）

---

## Acceptance Criteria

- Non-UI Ticket behavior 不受影響。
- UI Ticket 缺 required UI evidence 不可 Ready for Review。
- UI implementation 必須 trace 到 UI-AC。
- UI 與 backend 不得被強制拆成 horizontal tickets。
- DESIGN.md 不得被 Implementation Agent偷偷改來配合自己的實作。
- 若 Design Contract 本身錯誤，走正式 invalidation / decision flow。

完成後停止並回報。

---

# Milestone 7 — UI Review

## Objective

在現有 Review 增加 UI review dimension。

不要新增第二套完全獨立 Ticket lifecycle。

Review 仍回傳：

- PASS
- FIX_REQUIRED
- USER_DECISION_REQUIRED

---

## UI Review Dimensions

只有涉及 UI 的 Ticket 才執行。

### UIR-1 Task Usability

使用者能否透過介面完成 User Story？

### UIR-2 Interaction Correctness

Relevant states 是否正確：

- loading
- error
- empty
- success
- validation
- destructive action

### UIR-3 Information Hierarchy

主要 task / action / information 是否容易辨識？

### UIR-4 Design Consistency

是否符合 DESIGN.md：

- components
- typography
- spacing
- semantic colors
- hierarchy

### UIR-5 Accessibility

依 project requirement 驗證：

- color independence
- keyboard access
- readable contrast
- semantic structure

### UIR-6 Responsive Behavior

若 UI-SPEC 有指定 required viewports：

必須檢查。

---

## Severity

沿用現有 Finding model：

- blocking
- non-blocking

不要新增第二套 finding system。

---

## Acceptance Criteria

UI Ticket PASS 必須同時：

```text
Functional Review PASS
AND
Required UI Review PASS
```

Non-UI Ticket：

```text
Functional Review PASS
```

UI cosmetic minor finding 不應自動阻止 PASS，除非對應 blocking UI criterion。

同一 UI problem 必須使用穩定 `finding_key`，納入既有 Fix Loop Memory。

完成後停止並回報。

---

# Milestone 8 — UI Fix Loop

## Objective

防止 UI Agent 每一輪亂改整個介面。

## Tasks

擴充既有 Fix Loop Memory。

下一輪 Implementation 只取得：

- active UI finding
- criterion
- screenshot / evidence reference
- previous fix summary
- latest review reason
- relevant DESIGN.md rule

不得把所有歷史 screenshot 與 review 全部載入。

---

## Acceptance Criteria

例如：

```text
Finding:
button-primary-action-not-discoverable

Attempt 1:
moved button to toolbar

Review 2:
still visually secondary to export action
```

Attempt 2 Agent 必須能知道前一次修了什麼。

同一問題不得被重新建立成完全不同 Finding。

沿用 V1 retry / pause mechanism。

不要建立 UI 專屬 retry system。

完成後停止並回報。

---

# Milestone 9 — Final Integrated UI Verification

## Objective

將 V1 Final Integrated Verification 擴展到 UI product flow。

不是做 pixel-perfect comparison。

---

## Verification

最終至少需要驗證：

Functional Golden Path
+
UI Golden Path

UI Golden Path 必須從 SPEC / UI-SPEC 已核准流程產生。

例如：

```text
Open Dashboard
→ Create Project
→ Fill Form
→ Submit
→ Confirm Project Appears
```

驗證的是：

- core user flow 可完成
- required state 正確
- critical UI Acceptance Criteria 有 evidence

不是：

- 每個 pixel 完全相同
- screenshot hash 完全相同

---

## Acceptance Criteria

Project COMPLETE 前：

- 所有 Tickets COMPLETE
- 無 blocking findings
- Functional Final Verification PASS
- 若 UI required：
  - 所有 critical UI-AC 有 current evidence
  - UI Golden Path PASS
  - 無 blocking UI finding

否則不得 COMPLETE。

完成後停止並回報。

---

# Milestone 10 — Test Suite & Regression

## Objective

建立 V2 reliability tests。

## Required Tests

至少新增：

1. UI-required routing
2. UI-not-required routing
3. UI Design Gate PASS
4. UI Design Gate failure
5. orphan Flow rejection
6. orphan Screen rejection
7. invalid UI-AC reference rejection
8. UI Ticket without UI Evidence rejection
9. stale UI Evidence rejection
10. non-UI Ticket unaffected
11. UI Review PASS
12. UI Review FIX_REQUIRED
13. UI Finding reopen
14. UI Fix Loop Memory
15. UI Final Integrated Verification
16. V1 full regression

---

## Full E2E Fixture

建立至少一個小型 UI fixture：

```text
DISCOVERY
→ SPEC
→ UI_DESIGN
→ TICKETS
→ IMPLEMENTATION
→ FUNCTIONAL VERIFY
→ UI VERIFY
→ REVIEW
→ COMPLETE
```

再建立一個沒有 UI 的 fixture：

```text
DISCOVERY
→ SPEC
→ UI_NOT_REQUIRED
→ TICKETS
→ ...
→ COMPLETE
```

---

## Acceptance Criteria

- 全部 V1 tests PASS。
- 全部 V2 tests PASS。
- Windows CI PASS。
- Linux CI PASS。
- Tests 不修改 source repository。
- Runtime artifacts 使用 disposable fixture。
- Failure tests 能證明 bad UI evidence 無法讓 Ticket COMPLETE。

完成後停止並回報。

---

# Milestone 11 — Documentation & V2 Release

## Objective

使 repo 的正式規格與 Runtime behavior 一致。

## Tasks

更新：

- README
- Harness main specification
- Pipeline diagram
- State documentation
- Artifact Contract
- Traceability documentation
- Skill registry
- CLI documentation

建立：

`docs/V2_UI_DESIGN.md`

說明：

- V1 與 V2 差異
- 何時啟用 UI_DESIGN
- UI-SPEC
- DESIGN.md
- UI Evidence
- UI Review
- UI Final Verification

---

## Acceptance Criteria

文件不得宣稱尚未實作的能力。

所有文件中的：

- command
- file path
- schema
- stage
- transition

必須與 production code 一致。

提供至少一個完整 V2 example。

---

# Definition of Done

software-development-assurance-harness V2 完成，不代表：

- 有漂亮 Demo
- 有 UI screenshots
- 有 DESIGN.md
- Agent 成功產生 React components
- 有 frontend-design skill

V2 完成的條件是：

```text
Approved User Story
→ UI Design Contract
→ UI Gate PASS
→ Traceable Vertical Ticket
→ Functional Implementation
→ UI Implementation
→ Bound Functional Evidence
→ Bound UI Evidence
→ Functional Review PASS
→ UI Review PASS
→ Final Integrated Verification PASS
```

並且：

```text
V1 non-UI workflow remains fully functional.
```

---

# Implementation Rules

每個 Milestone：

1. 只修改完成該 Milestone 必要的內容。
2. 先讀現有 architecture，不重寫已存在的系統。
3. 優先延伸現有：
   - State Machine
   - Finding model
   - Payload model
   - Traceability system
   - Fix Loop
   - Review workflow
4. 不建立平行的第二套 framework。
5. 執行 relevant tests。
6. 執行 full regression。
7. 顯示實際 verification evidence。
8. 更新必要文件。
9. STOP。

不得自動進入下一 Milestone。

---

# Required Milestone Report

每個 Milestone 完成後只回報：

## Milestone
M<N> — <Name>

## Changes
實際新增／修改的檔案。

## Acceptance Criteria
逐項：

- PASS
- FAIL
- UNVERIFIED

## Verification
實際執行：

```text
command
result
```

## Regressions
V1 tests 是否仍 PASS。

## Deviations
與此 Implementation Directive 有任何差異時列出。

## Open Issues
尚未解決的 blocking issue。

## Recommendation
只能回答：

- READY_FOR_NEXT_MILESTONE
- FIX_REQUIRED
- USER_DECISION_REQUIRED

在收到人工確認前，不得開始下一個 Milestone。
``