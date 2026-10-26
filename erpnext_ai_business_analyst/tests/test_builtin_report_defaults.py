"""Tests for required defaults on approved ERPNext reports."""

from unittest import TestCase

from erpnext_ai_business_analyst.tools.inventory.builtin_report import (
    COMPANY_CONTEXT_REPORTS,
    REPORT_DEFAULT_FILTERS,
)


class TestBuiltinReportDefaults(TestCase):
    def test_trend_reports_have_required_grouping_defaults(self):
        self.assertEqual(REPORT_DEFAULT_FILTERS["Purchase Order Trends"]["based_on"], "Item")
        self.assertEqual(REPORT_DEFAULT_FILTERS["Purchase Order Trends"]["period"], "Monthly")
        self.assertEqual(REPORT_DEFAULT_FILTERS["Sales Order Trends"]["based_on"], "Item")
        self.assertEqual(REPORT_DEFAULT_FILTERS["Sales Order Trends"]["period"], "Monthly")

    def test_company_required_reports_use_the_user_company_context(self):
        self.assertIn("Stock Ledger", COMPANY_CONTEXT_REPORTS)
        self.assertIn("Stock Ageing", COMPANY_CONTEXT_REPORTS)
        self.assertIn("Item Shortage Report", COMPANY_CONTEXT_REPORTS)
        self.assertIn("Stock and Account Value Comparison", COMPANY_CONTEXT_REPORTS)
