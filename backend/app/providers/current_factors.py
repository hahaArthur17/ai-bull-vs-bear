from app.providers.evidence_factors import FilingFactorProvider, NewsFactorProvider
from app.providers.financial_fact_factors import FinancialFactsProvider
from app.providers.macro_factors import MacroFactorProvider
from app.providers.technical_factors import TechnicalFactorProvider
from app.services.factor_registry import FactorRegistry


def build_current_factor_registry() -> FactorRegistry:
    return FactorRegistry(
        [
            TechnicalFactorProvider(),
            MacroFactorProvider(),
            NewsFactorProvider(),
            FilingFactorProvider(),
            FinancialFactsProvider(),
        ],
        expected_categories=("technical", "macro", "company", "fundamental"),
    )

