# SKILLS.md — Skill Registry (Live Reference)

Update this file as Skills are built. One row per Skill. Grouped by domain.

---

## Domain: Inventory (V1)

| Skill | Status | Example Triggers | Tools Used | Key Inputs | Output Summary |
|---|---|---|---|---|---|
| **Reorder/Demand Analysis** | Planned | "below reorder level", "no pending PO", "reorder" | `stock_ledger`, `reorder`, `pending_procurement` | item_code, warehouse | Projected Qty, Trigger Qty, items below ROL with no coverage |
| **Stockout Risk** | Planned | "at risk of stockout", "will run out" | `stock_ledger`, `reorder`, `item_movement` | item_code, warehouse | Ranked risk list w/ days-to-stockout estimate; may chain → Reorder/Demand |
| **Dead Stock** | Planned | "not moved for X days", "dead stock" | `item_movement`, `stock_ledger` | days_threshold (default 90), warehouse | Items with zero movement in threshold window |
| **Slow-Moving Stock** | Planned | "slow moving", "low turnover" | `item_movement`, `stock_ledger` | days_threshold, warehouse | Items below turnover-rate threshold (between Dead Stock and normal) |
| **Overstock** | Planned | "stock is too high", "why is stock high" | `stock_ledger`, `item_movement`, `reorder` | item_code, warehouse | Items with stock >> demand trend; may chain → Slow-Moving |
| **Inventory Concentration** | **Blocked — metric undefined** | "concentration", "dependency risk" | TBD | TBD | TBD — see MVP_PLAN.md §5 |

---

## Domain: Sales (V2 — not started)

| Skill | Status |
|---|---|
| Sales Decline | Future |
| Customer Decline | Future |
| Product Performance | Future |
| Sales Anomalies | Future |

---

## Domain: Production (V3 — not started)

| Skill | Status |
|---|---|
| Delayed Work Orders | Future |
| Production Efficiency | Future |
| Material Shortages | Future |
| Capacity Analysis | Future |

---

## Domain: Purchase/Supplier (V4 — not started)

| Skill | Status |
|---|---|
| Supplier Delays | Future |
| Price Changes | Future |
| Supplier Performance | Future |

---

## Status Legend

| Status | Meaning |
|---|---|
| Planned | Scoped, not yet coded |
| In Progress | Actively being built |
| Built | `run()` implemented + unit tested |
| Wired | Reachable via Planner + Chat UI |
| Blocked | Cannot start — missing decision/dependency |
| Future | Belongs to a later version, not started |