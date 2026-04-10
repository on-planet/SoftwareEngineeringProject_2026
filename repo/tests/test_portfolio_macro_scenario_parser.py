from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.services.portfolio_macro_scenarios import resolve_portfolio_macro_scenario


class PortfolioMacroScenarioParserTests(unittest.TestCase):
    def test_uses_dictionary_scoring_to_match_template(self) -> None:
        resolved = resolve_portfolio_macro_scenario("油价上涨8%")

        self.assertEqual(resolved.matched_template_code, "oil_up")
        self.assertEqual(resolved.clauses[0].parser, "template")
        self.assertIn("dictionary keyword scoring", resolved.clauses[0].explanation)
        self.assertTrue(any(rule.scope_type == "sector" and rule.scope_value == "能源" for rule in resolved.rules))

    def test_alias_and_keyword_scoring_match_rate_template(self) -> None:
        resolved = resolve_portfolio_macro_scenario("央行加息50bp")

        self.assertEqual(resolved.matched_template_code, "rate_up")
        self.assertEqual(resolved.clauses[0].parser, "template")
        self.assertTrue(any(rule.scope_type == "sector" and rule.scope_value == "科技" for rule in resolved.rules))

    def test_multi_clause_can_merge_template_rules(self) -> None:
        resolved = resolve_portfolio_macro_scenario("美元走强，同时油价回落")

        codes = set(resolved.matched_template_codes)
        self.assertIn("rmb_depreciation", codes)
        self.assertIn("oil_down", codes)
        self.assertGreaterEqual(len(resolved.rules), 2)

    def test_split_supports_list_and_or_keywords(self) -> None:
        resolved = resolve_portfolio_macro_scenario("油价涨8%、人民币贬值、美债收益率上行50bp，或者港股科技跌6%")

        codes = set(resolved.matched_template_codes)
        self.assertIn("oil_up", codes)
        self.assertIn("rmb_depreciation", codes)
        self.assertIn("rate_up", codes)
        self.assertGreaterEqual(len(resolved.rules), 3)

    def test_unparsed_text_uses_fallback_parser_instead_of_validation_error(self) -> None:
        resolved = resolve_portfolio_macro_scenario("全球风险偏好骤降，市场恐慌下跌")

        self.assertEqual(resolved.clauses[0].parser, "fallback")
        self.assertEqual(resolved.rules[0].scope_type, "all")
        self.assertLess(float(resolved.rules[0].shock_pct), 0.0)

    def test_oil_up_and_down_support_shangsheng_xiajiang_words(self) -> None:
        up = resolve_portfolio_macro_scenario("油价上升25%")
        down = resolve_portfolio_macro_scenario("油价下降25%")

        self.assertIn("oil_up", set(up.matched_template_codes))
        self.assertIn("oil_down", set(down.matched_template_codes))


if __name__ == "__main__":
    unittest.main()
