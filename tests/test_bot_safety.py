import pytest
from bot.intent_classifier import _rule_based_classify
from bot.system_prompt import DISCLAIMER_TEXT, SYSTEM_PROMPT


class TestIntentClassification:
    def test_personal_tax_rate(self):
        assert _rule_based_classify("What's the tax rate for RM 80k?") == "personal_tax_rate"

    def test_corporate_tax(self):
        assert _rule_based_classify("What's the corporate tax rate for Sdn Bhd?") == "corporate_tax"

    def test_sst_registration(self):
        assert _rule_based_classify("Do I need to register for SST?") == "sst_registration"

    def test_rpgt(self):
        assert _rule_based_classify("I'm selling my property") == "rpgt"

    def test_relief(self):
        assert _rule_based_classify("Can I claim medical relief?") == "personal_relief"

    def test_greeting(self):
        assert _rule_based_classify("Hello") == "greeting"

    def test_efiling(self):
        assert _rule_based_classify("How to file my tax online?") == "efiling_procedure"

    def test_withholding(self):
        assert _rule_based_classify("Withholding tax on payments to non-resident") == "withholding_tax"


class TestDisclaimer:
    def test_disclaimer_mentions_advice(self):
        assert "not professional advice" in DISCLAIMER_TEXT

    def test_disclaimer_mentions_tax_agent(self):
        assert "tax agent" in DISCLAIMER_TEXT


class TestSafetyBoundaries:
    def test_system_prompt_no_calculation(self):
        assert "calculate" in SYSTEM_PROMPT.lower()

    def test_system_prompt_no_planning(self):
        assert "tax planning" in SYSTEM_PROMPT.lower()

    def test_system_prompt_boundaries(self):
        assert "BOUNDARIES" in SYSTEM_PROMPT

    def test_system_prompt_has_disclaimer_instruction(self):
        assert "DISCLAIMER" in SYSTEM_PROMPT

    def test_system_prompt_refuses_illegal(self):
        assert "illegal" in SYSTEM_PROMPT.lower()
