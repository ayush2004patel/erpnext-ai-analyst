"""Tests for required defaults on approved ERPNext reports."""

from unittest import TestCase
from unittest.mock import patch

from erpnext_ai_business_analyst.tools.inventory.builtin_report import (
    COMPANY_CONTEXT_REPORTS,
    MAX_REPORT_ROWS,
    REPORT_DEFAULT_FILTERS,
    _run_builtin_report,
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

    def test_report_result_limit_is_positive(self):
        self.assertGreater(MAX_REPORT_ROWS, 0)

    @patch("erpnext_ai_business_analyst.tools.inventory.builtin_report.run")
    @patch("erpnext_ai_business_analyst.tools.inventory.builtin_report._get_default_company", return_value="Test Company")
    def test_sales_order_analysis_keeps_a_scalar_warehouse_filter(self, _company, run_report):
        run_report.return_value = {"result": []}

        _run_builtin_report("Sales Order Analysis", {"warehouse": "Stores - TC"})

        self.assertEqual(run_report.call_args.kwargs["filters"]["warehouse"], "Stores - TC")

    @patch("erpnext_ai_business_analyst.tools.inventory.builtin_report.run")
    def test_report_rows_are_bounded_with_total_count_preserved(self, run_report):
        run_report.return_value = {"result": [{"item_code": str(index)} for index in range(MAX_REPORT_ROWS + 1)]}

        result = _run_builtin_report("Batch Item Expiry Status")

        self.assertEqual(len(result.data), MAX_REPORT_ROWS)
        self.assertEqual(result.query_meta.total_row_count, MAX_REPORT_ROWS + 1)
        self.assertTrue(result.query_meta.truncated)
