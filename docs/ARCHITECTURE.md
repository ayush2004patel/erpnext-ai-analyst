# ARCHITECTURE.md — ERPNext AI Business Analyst

App: `erpnext_ai_business_analyst` · Repo: `erpnext-ai-analyst` · Current target: **V1 — Inventory Analyst**

---

## 1. Core Pipeline

```
Chat UI  →  Investigation Agent (Planner)  →  Skills  →  Tools  →  ERPNext
                        ↓                        ↓
                   Evidence/Log  ←────────────────┘
```

MCP sits **beside** this pipeline, exposing the Tools layer only, for external AI clients. It is not in the internal call path.

```
                 ┌───────────────┐
External Client → │  MCP Server   │ → Tools
(Claude Desktop,  └───────────────┘
 other agents)
```

---

## 2. Layer Contracts

| Layer | Responsibility | Side Effects | Domain-Specific? |
|---|---|---|---|
| **Tool** | One typed, read-only ERPNext query | None (enforced by lint) | No — generic per DocType |
| **Skill** | Runs analysis using Tools → structured findings + evidence | None | Yes — lives in domain folder |
| **Planner** | Classifies question, chains Skills, decides when to conclude | None | No |
| **Evidence/Log** | Persists every query + finding for audit/replay | Writes to Log DocType only | No |
| **Chat UI** | Renders findings, tables, evidence | None (calls whitelisted API) | No |

**Rule:** Tool / Skill Registry / Planner / Evidence / Chat UI layers must contain **zero** inventory-specific (or any domain-specific) logic. All domain logic lives inside individual Skill + Tool implementations under their domain folder. This is what lets V2 (Sales) sit next to V1 (Inventory) without touching the core.

---

## 3. Tool Contract

| Field | Description |
|---|---|
| `name` | Unique string, e.g. `inventory.get_reorder_status` |
| `description` | For planner/LLM understanding |
| `params` | Typed schema (item_code, warehouse, date_range...) |
| `permission_mode` | Always runs as **invoking user** — never `ignore_permissions=True` |
| `output.data` | List of typed records |
| `output.query_meta` | `{ doctype, filters, fields, row_count }` — mandatory, feeds Evidence layer |
| `on_permission_denied` | Returns partial-result flag + reason, never silently escalates |

---

## 4. Skill Contract

| Field | Description |
|---|---|
| `name / description / triggers` | Example phrasings + keywords for planner routing |
| `input_schema` | Typed params the Skill needs |
| `tools_used` | Declared Tool names — validated at registry load time |
| `run(inputs, tools) → SkillResult` | The analysis itself |

**`SkillResult`:**

| Field | Description |
|---|---|
| `findings` | `[{ claim, confidence, supporting_evidence_ids }]` |
| `metrics` | Structured, chartable numbers |
| `evidence` | `[{ id, source_tool, query_meta, records, summary }]` |
| `suggested_next_skills` | `[{ skill_name, reason, inputs_to_pass }]` |
| `status` | `ok \| partial \| no_data \| error` |

---

## 5. Skill/Tool Registry (Pluggable)

| Mechanism | Purpose |
|---|---|
| `hooks.py → ai_analyst_tools` | List of dotted paths; any installed app can add Tools |
| `hooks.py → ai_analyst_skills` | List of dotted paths; any installed app can add Skills |
| `ToolRegistry` | Loads all hooks on boot, validates schemas |
| `SkillRegistry` | Loads all hooks on boot, validates `tools_used` exist in `ToolRegistry` |

A future client-specific app can add its own Skills via its own `hooks.py` — no fork of this app required.

---

## 6. Investigation Agent (Planner) Loop

| Step | Action |
|---|---|
| 0 | `hop_count = 0`, `max_hops = 4` |
| 1 | If `hop_count == 0`: classify question → candidate Skills (small LLM call) |
| 2 | Else: candidates = last `SkillResult.suggested_next_skills` |
| 3 | Planner LLM call → `RUN(skill, inputs)` \| `CONCLUDE` \| `ASK_USER` |
| 4 | If `RUN`: execute, append to history, `hop_count += 1`, → step 2 |
| 5 | If `CONCLUDE`: synthesize final answer from findings + evidence refs |
| 6 | If `hop_count == max_hops` and not concluded: force conclude, flag "truncated" |

Context sent to planner LLM = **findings + confidence only**, never raw evidence records (evidence stays addressable by ID).

No LangGraph/agent framework — state is a flat list + counter, one structured decision per hop.

---

## 7. Evidence / Audit Model

| DocType | Type | Fields |
|---|---|---|
| **AI Investigation Log** | Parent | question, user, timestamp, final_answer, hop_count, status |
| **AI Investigation Step** | Child | skill_name, inputs (JSON), findings (JSON), evidence (JSON incl. query_meta), confidence |

Written incrementally as the planner runs — not reconstructed after the fact. Chat UI renders each finding with an expandable evidence section linking back to the same filtered ERPNext list view.

---

## 8. MCP Layer

| Aspect | Decision |
|---|---|
| What it exposes | **Tools only** — not Skills, not the Planner |
| Why not Skills | Skills are stateful/multi-hop; don't map to a single MCP call |
| Internal calls | In-process, no MCP round-trip (performance) |
| External calls | MCP server iterates `ToolRegistry`, exposes each as an MCP tool |
| Auth | MCP client auth (API key/OAuth) mapped to a Frappe session/user — permissions still enforced |
| Build order | Last — after Tools are stable |

---

## 9. Repo Structure

```
erpnext_ai_business_analyst/
├── hooks.py                                # declares ai_analyst_tools, ai_analyst_skills
├── erpnext_ai_business_analyst/
│   ├── tools/
│   │   ├── registry.py                     # ToolRegistry, Tool dataclass
│   │   └── inventory/
│   │       ├── stock_ledger.py
│   │       ├── reorder.py
│   │       ├── pending_procurement.py      # PR/STR/PO/DWO
│   │       └── item_movement.py            # last-movement-date, consumption trend
│   ├── skills/
│   │   ├── registry.py                     # SkillRegistry, Skill base class
│   │   ├── base.py                         # Skill ABC, SkillResult dataclass
│   │   └── inventory/
│   │       ├── reorder_demand.py
│   │       ├── stockout_risk.py
│   │       ├── dead_stock.py
│   │       ├── slow_moving_stock.py
│   │       ├── overstock.py
│   │       └── inventory_concentration.py
│   ├── agent/
│   │   ├── planner.py
│   │   ├── classifier.py
│   │   └── synthesizer.py
│   ├── mcp_server/
│   │   └── server.py                       # built last
│   ├── doctype/
│   │   ├── ai_investigation_log/
│   │   └── ai_investigation_step/
│   ├── www/ or page/
│   │   └── ai_analyst_chat/                # chat UI
│   └── api.py                              # whitelisted endpoints
├── docs/
│   ├── ARCHITECTURE.md                     # this file
│   ├── MVP_PLAN.md
│   └── SKILLS.md
├── README.md
└── tests/
    ├── test_tools_inventory.py             # incl. no-side-effects lint
    ├── test_skills_reorder_demand.py
    └── ...
```

**Note:** `tools/inventory/` and `skills/inventory/` are domain-namespaced from day one — V2 adds `tools/sales/` and `skills/sales/` beside them, core layers untouched.

---

## 10. Roadmap Awareness (What Each Version Exercises)

| Version | New Domain | What It Proves in the Architecture |
|---|---|---|
| V1 | Inventory | Core pipeline end-to-end; single-domain Skill chaining |
| V2 | Sales | Classifier accuracy **across** domains; registry holds 2 domains |
| V3 | Production | Third domain; more chaining pairs |
| V4 | Purchase/Supplier | Fourth domain |
| V5 | Cross-Module | Planner chains Skills **across** domains (e.g. Delivery → Production → Inventory → Purchase) |
| V6/V7 | Proactive | A new "Insight" producer feeds the **same** Planner as a trigger instead of a user question — Evidence/Log schema already supports this (no breaking change needed) |

---

## 11. Explicit Non-Goals (V1)

| Not in scope for V1 |
|---|
| Any Sales, Production, or Purchase Tool/Skill |
| Cross-module chaining |
| Insight/anomaly auto-detection |
| Write actions (approve/execute) — read-only only |
| LangGraph or any agent framework |