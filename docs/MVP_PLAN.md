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

| Step | Deliverable | Depends On | Notes |
|---|---|---|---|
| 1 | Shared inventory Tools | ERPNext instance | Stock Ledger, Item Reorder, Pending PR/STR/PO/DWO, Item Movement — build once, reused by all 6 skills |
| 2 | Tool tests | Step 1 | Incl. automated "no side effects" lint scan |
| 3 | `reorder_demand.py` Skill | Step 1 | Reuses existing Reorder Level Report logic — lowest risk, do first |
| 4 | `stockout_risk.py` Skill | Step 1, 3 | Shares tools with Reorder/Demand — first real chain (`suggested_next_skills`) |
| 5 | `dead_stock.py` + `slow_moving_stock.py` Skills | Step 1 | Same tool family: last-movement-date queries — build together |
| 6 | `overstock.py` + `inventory_concentration.py` Skills | Step 1 | Same tool family: stock value/qty distribution — **Concentration metric must be pinned down before coding** (see §5) |
| 7 | Skill unit tests | Steps 3–6 | Call `.run()` directly, no planner, against known cases |
| 8 | Planner loop — hardcoded keyword router | Steps 3–6 | e.g. "stockout"→Stockout Risk, "reorder"→Reorder/Demand — validates hop/chain/conclude mechanics before LLM cost |
| 9 | Swap in LLM classifier + LLM RUN/CONCLUDE decision | Step 8 | Real planner behavior |
| 10 | `AI Investigation Log` / `AI Investigation Step` DocTypes | — | Can be built in parallel with steps 3–9 |
| 11 | Wire Log persistence into planner loop | Steps 9, 10 | Written incrementally, not after the fact |
| 12 | Chat UI (desk page) | Step 11 | Table rendering first, evidence expandable sections — **no charts yet** |
| 13 | MCP server exposing Tools | Step 2 (stable tools) | Last — additive, orthogonal to core loop |

---

## 4. Known Risks

| Risk | Mitigation |
|---|---|
| Classifier accuracy is untested across domains (V1 = inventory only) | Explicitly flagged — real validation happens in V2, not before |
| Bad Tool output poisons every downstream Skill | Step 2 tests run before any Skill is built |
| `Inventory Concentration` metric is under-specified | Must be pinned down at Step 6, not deferred further |
| LLM cost/latency in planner loop | `max_hops = 4` hard cap; findings-only (not raw evidence) sent to planner LLM |

---

## 5. Open Decision — Inventory Concentration

Must be answered before Step 6:

| Question | Options |
|---|---|
| Concentration of what? | By Warehouse? By Item Group? By single-supplier dependency? |
| Metric | e.g. "X% of stock value sits in 1 warehouse" |

---

## 6. Definition of Done (V1)

| Checklist |
|---|
| ☐ All 6 Skills return structured `SkillResult` matching contract |
| ☐ Planner answers all 4 example questions from §2 correctly |
| ☐ Every finding traceable to Evidence with real `query_meta` |
| ☐ Chat UI usable end-to-end on `business-analyst` site |
| ☐ MCP server exposes all inventory Tools to an external client |
| ☐ No write operations anywhere in Tools or Skills |