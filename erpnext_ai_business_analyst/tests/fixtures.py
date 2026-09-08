"""
Shared minimal fixture helpers for tool/skill tests.

Not a fixture framework — just the handful of ERPNext record builders
reused across test files. Callers run inside FrappeTestCase, which rolls
back each test's transaction automatically; nothing here persists.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate


def get_or_create_company() -> str:
    default_company = frappe.db.get_single_value("Global Defaults", "default_company")
    if default_company:
        return default_company
    existing = frappe.db.get_value("Company", {"company_name": "_Test AI Co"})
    if existing:
        return existing
    company = frappe.get_doc({
        "doctype": "Company",
        "company_name": "_Test AI Co",
        "abbr": "TAIC",
        "default_currency": "USD",
        "country": "United States",
    }).insert(ignore_permissions=True)
    return company.name


def create_warehouse(company: str, suffix: str) -> str:
    wh = frappe.get_doc({
        "doctype": "Warehouse",
        "warehouse_name": f"AI Test WH {suffix}",
        "company": company,
    }).insert(ignore_permissions=True)
    return wh.name


def create_item_group(suffix: str) -> str:
    """Used to scope multi-item, cross-warehouse queries (e.g. Inventory
    Concentration, which has no warehouse filter) away from any
    pre-existing site data."""
    name = f"AI Test Group {suffix}"
    if frappe.db.exists("Item Group", name):
        return name
    frappe.get_doc({
        "doctype": "Item Group",
        "item_group_name": name,
        "parent_item_group": "All Item Groups",
        "is_group": 0,
    }).insert(ignore_permissions=True)
    return name


def create_item(suffix: str, reorder_rows: list[dict] | None = None,
                 item_group: str | None = None) -> str:
    item = frappe.get_doc({
        "doctype": "Item",
        "item_code": f"AI-TEST-ITEM-{suffix}",
        "item_name": f"AI Test Item {suffix}",
        "item_group": item_group or "All Item Groups",
        "stock_uom": "Nos",
        "is_stock_item": 1,
        "is_purchase_item": 1,
        "reorder_levels": reorder_rows or [],
    })
    item.insert(ignore_permissions=True)
    return item.item_code


def insert_sle(item_code: str, warehouse: str, qty_after_transaction: float,
                actual_qty: float, days_ago: int, voucher_no: str) -> None:
    """Direct db_insert (bypasses SLE's normal controller, which blocks manual
    creation) — fine for testing query logic, not simulating real stock flow."""
    posting_dt = add_days(nowdate(), -days_ago)
    sle = frappe.get_doc({
        "doctype": "Stock Ledger Entry",
        "item_code": item_code,
        "warehouse": warehouse,
        "posting_date": posting_dt,
        "posting_datetime": posting_dt,
        "actual_qty": actual_qty,
        "qty_after_transaction": qty_after_transaction,
        "voucher_type": "Stock Entry",
        "voucher_no": voucher_no,
        "stock_uom": "Nos",
        "docstatus": 1,
        "is_cancelled": 0,
        "company": get_or_create_company(),
    })
    sle.db_insert()


def create_material_request(item_code: str, warehouse: str, qty: float,
                             mr_type: str) -> None:
    mr = frappe.get_doc({
        "doctype": "Material Request",
        "material_request_type": mr_type,
        "schedule_date": nowdate(),
        "items": [{
            "item_code": item_code,
            "warehouse": warehouse,
            "qty": qty,
            "schedule_date": nowdate(),
        }],
    })
    mr.insert(ignore_permissions=True)
    mr.submit()


def create_purchase_order(item_code: str, warehouse: str, qty: float, suffix: str) -> None:
    """db_insert (bypasses supplier/party-details enrichment, contact lookup,
    etc.) — the pending_po query only reads Purchase Order/Purchase Order Item
    columns directly, so full document lifecycle isn't needed here."""
    company = get_or_create_company()
    po = frappe.get_doc({
        "doctype": "Purchase Order",
        "supplier": f"AI Test Supplier {suffix}",
        "company": company,
        "transaction_date": nowdate(),
        "schedule_date": nowdate(),
        "currency": frappe.db.get_value("Company", company, "default_currency") or "USD",
        "conversion_rate": 1,
        "status": "To Receive and Bill",
        "docstatus": 1,
    })
    po.db_insert()

    poi = frappe.get_doc({
        "doctype": "Purchase Order Item",
        "parent": po.name,
        "parenttype": "Purchase Order",
        "parentfield": "items",
        "idx": 1,
        "item_code": item_code,
        "warehouse": warehouse,
        "qty": qty,
        "stock_qty": qty,
        "uom": "Nos",
        "stock_uom": "Nos",
        "conversion_factor": 1,
        "rate": 1,
        "amount": qty,
        "schedule_date": nowdate(),
    })
    poi.db_insert()


def create_bin(item_code: str, warehouse: str, actual_qty: float) -> None:
    frappe.get_doc({
        "doctype": "Bin",
        "item_code": item_code,
        "warehouse": warehouse,
        "actual_qty": actual_qty,
        "stock_uom": "Nos",
    }).insert(ignore_permissions=True)