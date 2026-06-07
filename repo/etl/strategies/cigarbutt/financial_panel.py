# Financial Panel - Standardized financial panel for Cigar Butt Analysis
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional


@dataclass
class FinancialPanel:
    """Standardized financial panel (3 core statements)"""
    report_id: str = ""
    stock_code: str = ""
    stock_name: str = ""
    report_period: str = ""  # e.g. "2023-Q3", "2023-Annual"

    # Balance Sheet (Key items only)
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    inventory: Optional[float] = None
    accounts_receivable: Optional[float] = None
    fixed_assets: Optional[float] = None
    intangible_assets: Optional[float] = None
    goodwill: Optional[float] = None
    short_term_debt: Optional[float] = None
    long_term_debt: Optional[float] = None

    # T0/T1/T2 NAV specific items (v1.8)
    short_term_investments: Optional[float] = None
    time_deposits: Optional[float] = None
    restricted_cash: Optional[float] = None
    contract_liabilities: Optional[float] = None
    other_current_assets: Optional[float] = None
    other_non_current_assets: Optional[float] = None
    prepaid_expenses: Optional[float] = None
    notes_receivable: Optional[float] = None

    # Income Statement (Key items only)
    revenue: Optional[float] = None
    operating_cost: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_expenses: Optional[float] = None
    operating_profit: Optional[float] = None
    net_profit: Optional[float] = None
    net_profit_parent: Optional[float] = None
    eps: Optional[float] = None

    # Cash Flow Statement (Key items only)
    operating_cash_flow: Optional[float] = None
    investing_cash_flow: Optional[float] = None
    financing_cash_flow: Optional[float] = None
    free_cash_flow: Optional[float] = None

    # Share Structure
    total_shares: Optional[float] = None  # 总股本 (亿股)

    # Subtype analysis fields (Phase 2)
    market: str = "A股"
    dividend_yield: Optional[float] = None
    consecutive_dividend_years: Optional[int] = None
    dividend_payout_ratio: Optional[float] = None
    total_dividend: Optional[float] = None
    subsidiary_holdings: List[Dict] = None
    buyback_authorization: Optional[float] = None
    buyback_executed: Optional[float] = None
    pending_events: List[Dict] = None
    is_state_owned: bool = False
    state_owned_level: str = ""
    state_owned_ratio: Optional[float] = None

    # Phase 3: Fact Check fields
    pledged_assets: Optional[float] = None
    goodwill_impairment_history: bool = False
    ar_over_90_days: Optional[float] = None
    related_party_ar: Optional[float] = None
    dio_years: List[float] = None
    industry_avg_dio: Optional[float] = None
    unidentifiable_intangible_assets: Optional[float] = None

    off_balance_sheet_liabilities: Optional[float] = None
    capital_commitments: Optional[float] = None
    pension_deficit: Optional[float] = None
    other_payables: Optional[float] = None

    related_party_revenue: Optional[float] = None
    top5_customer_revenue_ratio: Optional[float] = None
    q4_revenue: Optional[float] = None
    annual_revenue: Optional[float] = None
    audit_opinion: str = ""
    management_fraud_history: bool = False
    govt_subsidy: Optional[float] = None

    non_current_financial_assets: Optional[float] = None
    investment_income: Optional[float] = None
    listed_securities_in_non_current: Optional[float] = None
    non_current_fv_volatility: Optional[float] = None
    level3_disclosure_adequate: bool = True

    dividend_history: List[float] = None
    cost_basis: Optional[float] = None
    current_position_ratio: Optional[float] = None

    currency: str = "CNY"
    unit: str = "亿元"
    source_page: int = 0

    def __post_init__(self):
        if self.subsidiary_holdings is None:
            self.subsidiary_holdings = []
        if self.pending_events is None:
            self.pending_events = []
        if self.dio_years is None:
            self.dio_years = []
        if self.dividend_history is None:
            self.dividend_history = []

    def to_dict(self) -> Dict:
        return asdict(self)
