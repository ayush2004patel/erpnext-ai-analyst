# MVP_PLAN.md — V1: Inventory Analyst

Target: first complete, usable product. Read-only. Single domain (Inventory) only.

---

## 1. V1 Scope

| In Scope (Skills) | Out of Scope |
|---|---|
| Stockout Risk | Sales, Production, Purchase/Supplier Skills |
| Reorder/Demand Analysis | Cross-module chaining |
| Dead Stock | Insight/anomaly auto-detection |
| Slow-Moving Stock | Write/approve actions |
| Overstock | LangGraph or any agent framework |
| Inventory Concentration | Charts (defer to post-UI-MVP) |

---

## 2. Example Questions V1 Must Answer

| # | Question | Primary Skill |
|---|---|---|
| 1 | "Which items are at risk of stockout?" | Stockout Risk |
| 2 | "Which items are below reorder level but have no pending PO?" | Reorder/Demand |
| 3 | "Which inventory has not moved for 90 days?" | Dead Stock |
| 4 | "Why is Item X's stock so high?" | Overstock → may chain to Slow-Moving |

---

## 3. Build Sequence

| Step | Deliverable | Status |
|---|---|---|
| 1 | Shared inventory Tools | ✅ Done |
| 2 | Tool tests | ✅ Done |
| 3 | `reorder_demand.py` Skill | ✅ Done |
| 4 | `stockout_risk.py` Skill | ✅ Done |
| 5 | `dead_stock.py` + `slow_moving_stock.py` Skills | ✅ Done |
| 6 | `overstock.py` + `inventory_concentration.py` Skills | ✅ Done |
| 7 | Skill unit tests | ✅ Done (built alongside each Skill, not as a separate pass) |
| 8 | Planner loop — hardcoded keyword router | ✅ Done, then retired — superseded by Step 9's LLM decisions |
| 9 | LLM classifier + LLM RUN/CONCLUDE decision | ✅ Done — Ollama-first (`qwen2.5:3b-instruct` confirmed working; `qwen2.5-coder:7b` OOM'd on dev machine, `qwen2.5-coder:1.5b` made wrong decisions despite a clear prompt) |
| 10 | `AI Investigation Log` / `AI Investigation Step` DocTypes | ✅ Done |
| 11 | Wire Log persistence into planner loop | ✅ Done — `agent/persistence.py` + `agent/service.py` |
| 12 | Chat UI | ✅ Done — Desk Page (`ai-analyst-chat`), table + expandable evidence, no charts. **Known open issue:** natural-language questions that don't closely match a Skill's `triggers` wording return no findings even when a relevant Skill exists — being investigated next, tracked outside this plan |
| 13 | MCP server exposing Tools | Not started — last, per original sequencing |

---

## 4. Known Risks

| Risk | Status |
|---|---|
| Classifier accuracy is untested across domains (V1 = inventory only) | Still applies — real test comes in V2 |
| Bad Tool output poisons every downstream Skill | Mitigated — Step 2 tests run before any Skill was built |
| `Inventory Concentration` metric was under-specified | **Resolved** — defined as warehouse concentration by quantity (§5 below, kept for history) |
| LLM cost/latency in planner loop | Mitigated — `max_hops` cap; findings-only (not raw evidence) sent to planner LLM. N/A for cost with Ollama (local, free) |
| Natural-language question routing misses relevant Skills | **New, open** — real questions phrased differently from a Skill's `triggers` list can fail to match; next work item |

---

## 5. Resolved Decision — Inventory Concentration (kept for history)

Defined as warehouse concentration **by quantity**, not value, not supplier dependency:
`concentration_pct = (max_warehouse_stock / total_stock) * 100`, only for items held in 2+ warehouses, flagged at `>= 80%` (configurable). Implemented in `skills/inventory/inventory_concentration.py`.

---

## 6. Definition of Done (V1)

| Checklist |
|---|
| ✅ All 6 Skills return structured `SkillResult` matching contract |
| ⚠️ Planner answers all 4 example questions from §2 — works when phrased close to a Skill's `triggers`; **not yet reliable for naturally-phrased questions** (open issue, see §4) |
| ✅ Every finding traceable to Evidence with real `query_meta` |
| ✅ Chat UI usable end-to-end on `business-analyst` site |
| ❌ MCP server exposes all inventory Tools to an external client — not started (Step 13) |
| ✅ No write operations anywhere in Tools or Skills |