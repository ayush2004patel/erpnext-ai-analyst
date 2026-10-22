"""Tests for natural-language routing to approved ERP report datasets."""

from unittest import TestCase

from erpnext_ai_business_analyst.reports.catalog import select_dataset


class TestReportCatalogRouting(TestCase):
    def test_every_approved_dataset_has_a_routed_question(self):
        questions = {
            "stock_balance": "How much stock do we have?",
            "stock_movement": "Which warehouse received most stock?",
            "order_commitments": "Show open customer orders",
            "monthly_consumption": "Show monthly consumption",
            "batch_expiry": "Show the batch expiry data",
            "erpnext_stock_balance": "Open the ERPNext Stock Balance",
            "erpnext_stock_ledger": "Open the ERPNext Stock Ledger",
            "erpnext_stock_ageing": "Open the ERPNext Stock Ageing",
            "erpnext_purchase_order_analysis": "Open the standard purchase order report",
            "erpnext_sales_order_analysis": "Open the standard sales order report",
            "erpnext_warehouse_stock_balance": "Show warehouse-wise stock",
            "erpnext_stock_projected_qty": "What stock will be available next month?",
            "erpnext_item_shortage": "Which materials are short?",
            "erpnext_batch_expiry": "Show the batch expiry status",
            "erpnext_item_consumption": "How much was consumed?",
            "erpnext_stock_account_value": "Show the inventory value difference",
            "erpnext_purchase_order_trends": "Show purchase order trends",
            "erpnext_sales_order_trends": "Show sales order trends",
        }

        for expected_dataset, question in questions.items():
            with self.subTest(question=question):
                dataset = select_dataset(question)
                self.assertIsNotNone(dataset)
                self.assertEqual(dataset.name, expected_dataset)
