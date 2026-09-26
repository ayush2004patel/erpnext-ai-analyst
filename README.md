# ERPNext AI Business Analyst

An AI investigation engine inside ERPNext — not a chatbot, not another generic MCP server. It asks its own follow-up questions, runs deterministic business-rule analysis, and shows the evidence behind every finding.

## Why this exists

Most "AI + ERP" projects fall into one of two shapes:

- **A generic NL-to-SQL chatbot** — ask a question, an LLM writes a query, you trust it and hope. No repeatability, no verification, no way to know if the logic was right.
- **A generic tool-calling agent** (Frappe's own [Flow](https://github.com/frappe/flow_client) is a good example) — give it tools, it improvises how to use them, every time.

This project deliberately isn't either. Business logic — "is this item overstocked," "how many days until this stocks out" — is written once, in tested Python, with fixed formulas and deterministic confidence scoring. The LLM's only job is deciding *which* pre-built investigation to run next, never *how* to investigate. That's the entire architectural bet: **reliability over generality**, for a narrow but real set of inventory questions.

## Architecture

```
Chat UI (Desk Page)          MCP Server (stdio)
        │                            │
        └──────────┬─────────────────┘
                    │
              Investigation Agent (Planner)
              — LLM decides RUN skill / CONCLUDE, one hop at a time
              — semantic retrieval narrows candidates before the LLM sees them
                    │
                 Skills
              — deterministic business logic, confidence bands, evidence
                    │
                 Tools
              — permission-checked, read-only ERPNext queries
                    │
                ERPNext
```

Full design rationale, contracts, and decisions: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Build sequence and current status: [`docs/MVP_PLAN.md`](docs/MVP_PLAN.md).

## What's built (V1 — Inventory Analyst)

| Skill | Answers |
|---|---|
| Reorder/Demand | "Which items are below reorder level with no pending PO?" |
| Stockout Risk | "Which items are at risk of stockout?" |
| Dead Stock | "Which inventory hasn't moved in 90 days?" |
| Slow-Moving Stock | "Show me slow-moving inventory" |
| Overstock | "Why is stock too high for some items?" |
| Inventory Concentration | "Which items are risky because they sit in one warehouse?" |
| Stock Balance | "How much stock do we have in each warehouse?" |
| Available Stock | "What quantity is free after reservations?" |
| Negative Stock | "Which items have negative stock?" |
| Inventory Valuation | "Which inventory has the highest value?" |
| Warehouse Imbalance | "Which items should we consider transferring between warehouses?" |
| Stock Coverage | "How many days will the current stock last?" |
| Fast-Moving Stock | "Which items have high recent consumption?" |
| Open Purchase Orders | "Which purchase orders will supply inventory?" |
| Sales Commitments | "What outstanding sales orders need stock?" |
| Expiring Batches | "Which batches will expire soon?" |
| Reorder Configuration Gaps | "Which stocked items have no reorder level?" |
| Stock Movement Summary | "What stock was received and issued recently?" |

Skills chain automatically when relevant — e.g. Dead Stock findings can trigger an Overstock follow-up, Overstock can trigger a Slow-Moving check.

Every investigation is asked in **your own words**, not exact keyword matches — semantic retrieval (local embeddings, no external API) ranks candidate Skills by meaning before the LLM ever sees them. Questions outside V1's scope get an honest answer explaining what's not covered yet, not a silent wrong answer.

Every finding is backed by real evidence — the exact ERPNext records and query filters that produced it — and every investigation is permanently logged (`AI Investigation Log` doctype) for audit.

## Also exposed via MCP

The read-only Tool layer is available to any MCP client (Claude Code, Claude Desktop, etc.) over stdio — runs as a dedicated, permission-restricted service user, never Administrator. Skills and the Planner are intentionally *not* exposed this way; they're stateful multi-step investigations, not single tool calls. See `docs/ARCHITECTURE.md` §8 and `mcp_server/`.

## Stack

- **Frappe/ERPNext v16** — the app itself
- **Ollama** — local, free LLM inference (planner decisions + embeddings), no external API dependency for V1
- Provider-agnostic by design (`LLMClient`/`EmbeddingClient` interfaces) — swapping in a hosted model later is a new implementation, not a rewrite

## Setup

```bash
bench get-app https://github.com/ayush2004patel/erpnext-ai-analyst
bench --site <site> install-app erpnext_ai_business_analyst
bench --site <site> migrate
```

Configure Ollama (defaults shown; override only if needed):
```bash
bench --site <site> set-config ollama_model "qwen2.5:3b-instruct"
bench --site <site> set-config ollama_embedding_model "nomic-embed-text"
bench --site <site> set-config ollama_host "http://localhost:11434"
```
```bash
ollama pull qwen2.5:3b-instruct
ollama pull nomic-embed-text
```

Optional — enable the MCP server:
```bash
bench --site <site> execute erpnext_ai_business_analyst.setup.mcp_service_user.create_mcp_service_user --args "['mcp-service@yoursite.local']"
bench --site <site> set-config mcp_service_user "mcp-service@yoursite.local"
```

Open the chat UI at `/app/ai-analyst-chat`.

## Tests

```bash
bench --site <site> run-tests --module erpnext_ai_business_analyst.tests.<module_name>
```
Every layer — Tools, Skills, Planner, decision validation, retrieval, persistence, API, DocTypes, MCP server — has its own test module under `erpnext_ai_business_analyst/tests/`.

## Roadmap

V1 (Inventory) is complete. Planned next: V2 Sales Analyst, V3 Production Analyst, V4 Purchase/Supplier Analyst, V5 cross-module investigations (e.g. "why are deliveries late?" chaining Delivery → Production → Inventory → Purchase), V6/V7 proactive anomaly detection. See `docs/MVP_PLAN.md` for the full sequencing and what each version is meant to validate architecturally.

## License

MIT
