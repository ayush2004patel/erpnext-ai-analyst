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
    allowed_filters: tuple[str, ...] = ()


DATASETS = (
    ApprovedDataset("stock_balance", "Stock Balance", "Current stock, reservations, incoming quantity, and valuation by item and warehouse.", ("stock balance", "stock in warehouse", "how much stock", "available quantity"), "inventory.get_stock_balance", allowed_filters=("item_code", "warehouse", "item_group")),
    ApprovedDataset("stock_movement", "Stock Movement", "Recent incoming and outgoing stock movement by item and warehouse.", ("received most stock", "stock received", "stock issued", "stock movement", "goods received"), "inventory.get_item_movement", {"window_days": 90}, ("item_code", "warehouse", "item_group", "window_days")),
    ApprovedDataset("order_commitments", "Open Orders", "Outstanding purchase-order supply and sales-order demand.", ("pending orders", "open orders", "supplier orders", "customer orders", "outstanding orders"), "inventory.get_order_commitments", allowed_filters=("item_code", "warehouse")),
    ApprovedDataset("monthly_consumption", "Monthly Consumption", "Monthly outgoing quantities for demand analysis.", ("monthly consumption", "monthly demand", "consumption trend", "demand trend"), "inventory.get_monthly_consumption", {"months": 6}, ("item_code", "warehouse", "item_group", "months")),
    ApprovedDataset("batch_expiry", "Batch Expiry", "Active batches with an expiry date in the next 90 days.", ("batch expiry", "expiry report", "expiring batches"), "inventory.get_batch_expiry", {"days_ahead": 90}, ("item_code", "days_ahead")),
    ApprovedDataset("erpnext_stock_balance", "ERPNext: Stock Balance", "Standard ERPNext Stock Balance report.", ("erpnext stock balance", "standard stock balance report"), "inventory.run_builtin_report", {"report_name": "Stock Balance"}, ("company", "from_date", "to_date", "item_code", "warehouse", "item_group")),
    ApprovedDataset("erpnext_stock_ledger", "ERPNext: Stock Ledger", "Standard ERPNext Stock Ledger report for detailed transactions.", ("erpnext stock ledger", "standard stock ledger report"), "inventory.run_builtin_report", {"report_name": "Stock Ledger"}, ("company", "from_date", "to_date", "item_code", "warehouse", "item_group")),
    ApprovedDataset("erpnext_stock_ageing", "ERPNext: Stock Ageing", "Standard ERPNext Stock Ageing report.", ("erpnext stock ageing", "standard stock ageing report"), "inventory.run_builtin_report", {"report_name": "Stock Ageing"}, ("company", "to_date", "item_code", "warehouse")),
    ApprovedDataset("erpnext_purchase_order_analysis", "ERPNext: Purchase Order Analysis", "Standard ERPNext Purchase Order Analysis report.", ("erpnext purchase order analysis", "standard purchase order report"), "inventory.run_builtin_report", {"report_name": "Purchase Order Analysis"}, ("company", "from_date", "to_date", "supplier")),
    ApprovedDataset("erpnext_sales_order_analysis", "ERPNext: Sales Order Analysis", "Standard ERPNext Sales Order Analysis report.", ("erpnext sales order analysis", "standard sales order report"), "inventory.run_builtin_report", {"report_name": "Sales Order Analysis"}, ("company", "from_date", "to_date", "warehouse", "customer")),
    ApprovedDataset("erpnext_warehouse_stock_balance", "ERPNext: Warehouse Wise Stock Balance", "Standard ERPNext warehouse-level stock balance report.", ("warehouse wise stock balance", "warehouse stock balance report"), "inventory.run_builtin_report", {"report_name": "Warehouse Wise Stock Balance"}, ("company",)),
    ApprovedDataset("erpnext_stock_projected_qty", "ERPNext: Stock Projected Qty", "Standard ERPNext projected inventory availability report.", ("stock projected quantity", "projected stock", "future stock position"), "inventory.run_builtin_report", {"report_name": "Stock Projected Qty"}, ("company", "warehouse", "item_code", "item_group")),
    ApprovedDataset("erpnext_item_shortage", "ERPNext: Item Shortage Report", "Standard ERPNext item shortage report for material planning.", ("item shortage report", "material shortage", "shortage report"), "inventory.run_builtin_report", {"report_name": "Item Shortage Report"}, ("company", "warehouse")),
    ApprovedDataset("erpnext_batch_expiry", "ERPNext: Batch Item Expiry Status", "Standard ERPNext batch expiry report.", ("batch item expiry status", "standard batch expiry report"), "inventory.run_builtin_report", {"report_name": "Batch Item Expiry Status"}, ("from_date", "to_date")),
    ApprovedDataset("erpnext_item_consumption", "ERPNext: Item Wise Consumption", "Standard ERPNext item consumption report.", ("item wise consumption", "standard consumption report"), "inventory.run_builtin_report", {"report_name": "Item Wise Consumption"}, ("from_date", "to_date", "supplier")),
    ApprovedDataset("erpnext_stock_account_value", "ERPNext: Stock and Account Value Comparison", "Standard ERPNext stock and accounting value comparison report.", ("stock and account value comparison", "stock account value", "inventory accounting difference"), "inventory.run_builtin_report", {"report_name": "Stock and Account Value Comparison"}, ("company",)),
    ApprovedDataset("erpnext_purchase_order_trends", "ERPNext: Purchase Order Trends", "Standard ERPNext purchase order trend report.", ("purchase order trends", "purchase trends"), "inventory.run_builtin_report", {"report_name": "Purchase Order Trends"}),
    ApprovedDataset("erpnext_sales_order_trends", "ERPNext: Sales Order Trends", "Standard ERPNext sales order trend report.", ("sales order trends", "sales trends"), "inventory.run_builtin_report", {"report_name": "Sales Order Trends"}),
)


def select_dataset(question: str) -> ApprovedDataset | None:
    normalized = question.lower()
    def trigger_score(trigger: str) -> int:
        words = trigger.split()
        return len(words) if all(word in normalized for word in words) else 0

    scored = [(sum(trigger_score(trigger) for trigger in dataset.triggers), dataset) for dataset in DATASETS]
    score, dataset = max(scored, key=lambda pair: pair[0])
    return dataset if score else None


def get_dataset(name: str | None) -> ApprovedDataset | None:
    return next((dataset for dataset in DATASETS if dataset.name == name), None)
