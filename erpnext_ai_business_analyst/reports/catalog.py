"""Approved, read-only ERP datasets available to the hybrid Q&A fallback."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApprovedDataset:
    name: str
    label: str
    description: str
    triggers: tuple[str, ...]
    tool_name: str
    default_inputs: dict = field(default_factory=dict)


DATASETS = (
    ApprovedDataset("stock_balance", "Stock Balance", "Current stock, reservations, incoming quantity, and valuation by item and warehouse.", ("stock balance", "stock in warehouse", "how much stock", "available quantity"), "inventory.get_stock_balance"),
    ApprovedDataset("stock_movement", "Stock Movement", "Recent incoming and outgoing stock movement by item and warehouse.", ("received most stock", "stock received", "stock issued", "stock movement", "goods received"), "inventory.get_item_movement", {"window_days": 90}),
    ApprovedDataset("order_commitments", "Open Orders", "Outstanding purchase-order supply and sales-order demand.", ("pending orders", "open orders", "supplier orders", "customer orders", "outstanding orders"), "inventory.get_order_commitments"),
    ApprovedDataset("monthly_consumption", "Monthly Consumption", "Monthly outgoing quantities for demand analysis.", ("monthly consumption", "monthly demand", "consumption trend", "demand trend"), "inventory.get_monthly_consumption", {"months": 6}),
    ApprovedDataset("batch_expiry", "Batch Expiry", "Active batches with an expiry date in the next 90 days.", ("batch expiry", "expiry report", "expiring batches"), "inventory.get_batch_expiry", {"days_ahead": 90}),
)


def select_dataset(question: str) -> ApprovedDataset | None:
    normalized = question.lower()
    def trigger_score(trigger: str) -> int:
        words = trigger.split()
        return len(words) if all(word in normalized for word in words) else 0

    scored = [(sum(trigger_score(trigger) for trigger in dataset.triggers), dataset) for dataset in DATASETS]
    score, dataset = max(scored, key=lambda pair: pair[0])
    return dataset if score else None
