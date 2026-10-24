"""Tests for the safe LLM-to-approved-dataset router."""

from unittest import TestCase

from erpnext_ai_business_analyst.reports.qa import (
    is_inventory_question,
    select_general_analyst_datasets,
)


class _RouterLLM:
    def __init__(self, response):
        self.response = response

    def complete(self, *_args, **_kwargs):
        return self.response


class TestGeneralReportRouter(TestCase):
    def test_accepts_only_approved_dataset_names(self):
        datasets = select_general_analyst_datasets(
            "How will incoming supply affect inventory?",
            _RouterLLM('{"datasets": ["stock_balance", "not-a-real-dataset"]}'),
        )
        self.assertEqual([dataset.name for dataset in datasets], ["stock_balance"])

    def test_limits_the_llm_to_two_approved_datasets(self):
        datasets = select_general_analyst_datasets(
            "Analyse inventory broadly",
            _RouterLLM('{"datasets": ["stock_balance", "order_commitments", "monthly_consumption"]}'),
        )
        self.assertEqual([dataset.name for dataset in datasets], ["stock_balance", "order_commitments"])

    def test_unrelated_question_is_not_sent_to_general_router(self):
        self.assertFalse(is_inventory_question("What is the weather today?"))
