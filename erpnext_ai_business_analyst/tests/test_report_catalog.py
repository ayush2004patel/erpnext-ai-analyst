"""Tests for natural-language routing to approved ERP report datasets."""

from erpnext_ai_business_analyst.reports.catalog import select_dataset


def test_routes_projected_stock_question():
    assert select_dataset("What stock will be available next month?").name == "erpnext_stock_projected_qty"


def test_routes_item_shortage_question():
    assert select_dataset("Which materials are short?").name == "erpnext_item_shortage"


def test_routes_hyphenated_warehouse_stock_question():
    assert select_dataset("Show warehouse-wise stock").name == "erpnext_warehouse_stock_balance"
