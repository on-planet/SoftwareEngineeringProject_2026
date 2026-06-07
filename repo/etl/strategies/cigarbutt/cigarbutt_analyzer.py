# Cigar Butt Stock Analyzer (Static Value Deep Value Screening)
# Core logic: T0/T1/T2 NAV + Subtype A/B/C + Redemption Path Check (v1.8)
import json
import math
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Tuple
from enum import Enum
from pathlib import Path
from etl.strategies.cigarbutt.financial_panel import FinancialPanel


class TLevel(Enum):
    """T-level classification for asset cushion"""
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    NONE = "NONE"


class InventoryType(Enum):
    """Inventory discount coefficients by industry"""
    CONSUMER_STAPLES = 0.8   # 白酒/消费品（低报废率）
    MANUFACTURING = 0.7      # 一般制造业
    ELECTRONICS = 0.5        # 电子/时尚（高过时风险）
    REAL_ESTATE = 0.7        # 房地产在建项目（接近完工）
    DEFAULT = 0.6            # 默认


class MarketType(Enum):
    """Stock market types for dividend yield thresholds"""
    HK = "港股"
    A_SHARE = "A股"
    US = "美股"


# ==================== Subtype Result Dataclasses ====================

@dataclass
class SubTypeAResult:
    """High-dividend below-NAV type (子类型A)"""
    is_valid: bool = False
    # Core conditions
    dividend_yield_pass: bool = False
    pb_pass: bool = False
    consecutive_dividend_pass: bool = False
    # Safety conditions
    payout_ratio_pass: bool = False
    fcf_coverage_pass: bool = False
    interest_debt_ratio_pass: bool = False
    # Score (0-10)
    sustainability_score: float = 0.0
    # Details
    dividend_yield_threshold: float = 0.0  # 4/5/6 depending on market
    recovery_years: Optional[float] = None  # 理论回收年限
    details: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class SubTypeBResult:
    """Holding company arbitrage type (子类型B)"""
    is_valid: bool = False
    # Core conditions
    discount_rate_pass: bool = False
    min_holding_ratio_pass: bool = False
    coverage_pass: bool = False
    parent_net_cash_pass: bool = False
    # Calculated values
    sotp_value: Optional[float] = None  # SOTP估值 (亿元)
    discount_rate: Optional[float] = None  # 控股折价率
    visible_holding_value: Optional[float] = None  # 可见持股价值 (亿元)
    coverage_ratio: Optional[float] = None  # 持股价值覆盖率
    # Details
    details: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class SubTypeCResult:
    """Event-driven type (子类型C)"""
    is_valid: bool = False
    subtype: str = ""  # C1a / C1b / C1c / C2 / ""
    # C1a: asset disposal
    c1a_valid: bool = False
    # C1b: buyback
    c1b_valid: bool = False
    # C1c: liquidation/privatization
    c1c_valid: bool = False
    # C2: policy risk repair
    c2_valid: bool = False
    c2_score: float = 0.0
    # Event probability (A/B/C/D)
    event_probability: str = ""
    expected_return: Optional[float] = None
    # Details
    details: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class RedemptionPathResult:
    """Redemption path completeness check (兑现路径完整性检验)"""
    valid_path_count: int = 0
    has_valid_path: bool = False
    # Hold return floor check
    dividend_vs_risk_free: Optional[float] = None
    risk_free_rate: float = 0.0
    hold_return_warning: bool = False
    # Rating cap
    rating_cap: Optional[str] = None  # If no path, cap at "C"
    details: List[str] = field(default_factory=list)


@dataclass
class CigarButtMetrics:
    """Core metrics for cigar butt stock analysis"""
    # === Legacy metrics (kept for backward compatibility) ===
    ncav_per_share: Optional[float] = None
    ncav_ratio: Optional[float] = None
    liquidation_value_per_share: Optional[float] = None
    liquidation_ratio: Optional[float] = None
    bvps: Optional[float] = None
    pb_ratio: Optional[float] = None
    tangible_bvps: Optional[float] = None
    tangible_pb_ratio: Optional[float] = None
    safety_margin_ncav: Optional[float] = None
    safety_margin_liquidation: Optional[float] = None
    safety_margin_book: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    cash_to_debt: Optional[float] = None
    pe_ratio: Optional[float] = None
    pc_ratio: Optional[float] = None
    fcf_yield: Optional[float] = None
    quality_score: int = 0
    is_net_net: bool = False
    is_liquidation_candidate: bool = False
    is_deep_value: bool = False
    risk_flags: List[str] = None
    
    # === T0/T1/T2 Three-Tier NAV System (Phase 1) ===
    t0_nav_per_share: Optional[float] = None
    t1_nav_per_share: Optional[float] = None
    t2_nav_per_share: Optional[float] = None
    t0_ratio: Optional[float] = None
    t1_ratio: Optional[float] = None
    t2_ratio: Optional[float] = None
    t0_safety_margin: Optional[float] = None
    t1_safety_margin: Optional[float] = None
    t2_safety_margin: Optional[float] = None
    t0_buy_threshold: Optional[float] = None
    t1_buy_threshold: Optional[float] = None
    t2_buy_threshold: Optional[float] = None
    is_t0_pass: bool = False
    is_t1_pass: bool = False
    is_t2_pass: bool = False
    best_t_level: str = "NONE"
    asset_burn_rate: Optional[float] = None
    fcf_conversion_rate: Optional[float] = None
    restricted_cash_ratio: Optional[float] = None
    restricted_cash_warning: str = ""
    contract_liabilities_included: bool = False
    
    # === Subtype Analysis (Phase 2) ===
    subtype_a: SubTypeAResult = None
    subtype_b: SubTypeBResult = None
    subtype_c: SubTypeCResult = None
    redemption_path: RedemptionPathResult = None
    
    # State-owned bonus (#21 raw)
    state_owned_bonus: int = 0
    
    # Phase 3: Fact Check results
    fact_check_results: Dict = None
    fact_check_rating: str = ""  # A/B/C/D
    
    # Phase 4: Bonus system
    listed_subsidiary_bonus: int = 0  # #20 raw bonus
    total_bonus: int = 0  # Capped at +5
    bonus_adjusted_rating: str = ""  # Rating after bonus upgrade
    
    # Phase 5: Trading plan
    trade_plan: 'TradePlanResult' = None
    
    def __post_init__(self):
        if self.risk_flags is None:
            self.risk_flags = []
        if self.subtype_a is None:
            self.subtype_a = SubTypeAResult()
        if self.subtype_b is None:
            self.subtype_b = SubTypeBResult()
        if self.subtype_c is None:
            self.subtype_c = SubTypeCResult()
        if self.redemption_path is None:
            self.redemption_path = RedemptionPathResult()
        if self.fact_check_results is None:
            self.fact_check_results = {}


# ==================== Subtype Analyzers ====================

class SubTypeAAnalyzer:
    """
    子类型A：高股息破净型
    通过持续高股息派发逐步兑现账面价值
    """
    
    # Dividend yield thresholds by market
    DIVIDEND_YIELD_THRESHOLDS = {
        MarketType.HK: 6.0,
        MarketType.A_SHARE: 4.0,
        MarketType.US: 5.0,
    }
    
    def analyze(self, panel: FinancialPanel, metrics: CigarButtMetrics,
                stock_price: float) -> SubTypeAResult:
        result = SubTypeAResult()
        
        # Determine market type
        market = self._detect_market(panel.market)
        result.dividend_yield_threshold = self.DIVIDEND_YIELD_THRESHOLDS[market]
        
        # Core Condition 1: Dividend yield >= threshold
        if panel.dividend_yield is not None:
            result.dividend_yield_pass = panel.dividend_yield >= result.dividend_yield_threshold
        else:
            result.warnings.append("股息率数据缺失，无法判定核心条件1")
        
        # Core Condition 2: PB <= 0.5
        if metrics.pb_ratio is not None:
            result.pb_pass = metrics.pb_ratio <= 0.5
        else:
            result.warnings.append("PB数据缺失，无法判定核心条件2")
        
        # Core Condition 3: Consecutive dividend >= 5 years
        if panel.consecutive_dividend_years is not None:
            result.consecutive_dividend_pass = panel.consecutive_dividend_years >= 5
        else:
            result.warnings.append("连续派息年数缺失，无法判定核心条件3")
        
        # Safety Condition 4: Payout ratio < 80%
        if panel.dividend_payout_ratio is not None:
            result.payout_ratio_pass = panel.dividend_payout_ratio < 80.0
        else:
            result.warnings.append("派息率数据缺失")
        
        # Safety Condition 5: FCF coverage > 0.8 (FCF / total dividend)
        if panel.free_cash_flow is not None and panel.total_dividend is not None and panel.total_dividend > 0:
            fcf_coverage = panel.free_cash_flow / panel.total_dividend
            result.fcf_coverage_pass = fcf_coverage > 0.8
            result.details["fcf_coverage"] = round(fcf_coverage, 2)
        else:
            result.warnings.append("FCF或股息总额缺失，无法计算FCF覆盖率")
        
        # Safety Condition 6: Interest-bearing debt / total assets < 30%
        interest_debt = (panel.short_term_debt or 0) + (panel.long_term_debt or 0)
        if panel.total_assets is not None and panel.total_assets > 0:
            interest_debt_ratio = interest_debt / panel.total_assets
            result.interest_debt_ratio_pass = interest_debt_ratio < 0.30
            result.details["interest_debt_ratio"] = round(interest_debt_ratio * 100, 1)
        else:
            result.warnings.append("总资产数据缺失")
        
        # Calculate sustainability score (0-10)
        result.sustainability_score = self._calculate_sustainability_score(panel, result)
        
        # Calculate recovery years
        if metrics.bvps is not None and metrics.pb_ratio is not None and metrics.pb_ratio > 0:
            market_cap = stock_price * panel.total_shares  # 亿元
            book_value = metrics.bvps * panel.total_shares  # 亿元
            discount = book_value - market_cap
            if panel.total_dividend is not None and panel.total_dividend > 0:
                result.recovery_years = discount / panel.total_dividend
        
        # Final validity: ALL core conditions must pass
        result.is_valid = (
            result.dividend_yield_pass and
            result.pb_pass and
            result.consecutive_dividend_pass
        )
        
        return result
    
    def _detect_market(self, market_str: str) -> MarketType:
        """Detect market type from string"""
        s = market_str.lower()
        if "港" in s or "hk" in s or "hong" in s:
            return MarketType.HK
        elif "美" in s or "us" in s or "america" in s:
            return MarketType.US
        else:
            return MarketType.A_SHARE
    
    def _calculate_sustainability_score(self, panel: FinancialPanel,
                                        result: SubTypeAResult) -> float:
        """Dividend sustainability score (0-10, 5 dimensions × 2 points max)"""
        score = 0.0
        
        # Dimension 1: Dividend years (>=10:2, 5-9:1, <5:0)
        if panel.consecutive_dividend_years is not None:
            if panel.consecutive_dividend_years >= 10:
                score += 2
            elif panel.consecutive_dividend_years >= 5:
                score += 1
        
        # Dimension 2: Payout ratio (30-60%:2, 60-80%:1, else:0)
        if panel.dividend_payout_ratio is not None:
            if 30 <= panel.dividend_payout_ratio <= 60:
                score += 2
            elif 60 < panel.dividend_payout_ratio < 80:
                score += 1
        
        # Dimension 3: FCF coverage (>1.2:2, 0.8-1.2:1, <0.8:0)
        if "fcf_coverage" in result.details:
            fcf_cov = result.details["fcf_coverage"]
            if fcf_cov > 1.2:
                score += 2
            elif fcf_cov >= 0.8:
                score += 1
        
        # Dimension 4: Dividend growth (5y CAGR >3%:2, flat:1, decline:0)
        # This requires historical data; mark as 1 (neutral) if unavailable
        score += 1
        
        # Dimension 5: Debt pressure (interest debt / assets <15%:2, 15-30%:1, >30%:0)
        if "interest_debt_ratio" in result.details:
            debt_ratio = result.details["interest_debt_ratio"]
            if debt_ratio < 15:
                score += 2
            elif debt_ratio <= 30:
                score += 1
        else:
            score += 1  # neutral if unknown
        
        return score


class SubTypeBAnalyzer:
    """
    子类型B：控股套利型
    利用母公司市值相对于子公司持股价值的折价获利
    """
    
    def analyze(self, panel: FinancialPanel, metrics: CigarButtMetrics) -> SubTypeBResult:
        result = SubTypeBResult()
        
        if not panel.subsidiary_holdings:
            result.warnings.append("无子公司持股数据")
            return result
        
        # Calculate visible holding value
        visible_holding_value = 0.0
        listed_holdings = []
        min_holding_ratio = 0.0
        
        for holding in panel.subsidiary_holdings:
            market_cap = holding.get("market_cap", 0)
            ratio = holding.get("holding_ratio", 0)
            is_listed = holding.get("is_listed", False)
            
            if is_listed and market_cap > 0 and ratio > 0:
                holding_value = market_cap * ratio
                visible_holding_value += holding_value
                listed_holdings.append({
                    "name": holding.get("name", ""),
                    "market_cap": market_cap,
                    "ratio": ratio,
                    "value": holding_value
                })
                if ratio > min_holding_ratio:
                    min_holding_ratio = ratio
        
        result.details["listed_holdings"] = listed_holdings
        result.visible_holding_value = visible_holding_value
        
        # Core Condition 2: At least one subsidiary holding ratio >= 10%
        result.min_holding_ratio_pass = min_holding_ratio >= 0.10
        if not result.min_holding_ratio_pass:
            result.warnings.append(f"最大子公司持股比例{min_holding_ratio*100:.1f}% < 10%")
        
        # Calculate parent net cash (approximate)
        parent_net_cash = self._calculate_parent_net_cash(panel)
        result.details["parent_net_cash"] = parent_net_cash
        
        # Core Condition 4: Parent net cash > 0
        result.parent_net_cash_pass = parent_net_cash is not None and parent_net_cash > 0
        if not result.parent_net_cash_pass:
            result.warnings.append("母公司净现金 <= 0")
        
        # SOTP valuation
        if parent_net_cash is not None:
            result.sotp_value = visible_holding_value + parent_net_cash
        else:
            result.sotp_value = visible_holding_value
        
        # Calculate discount rate
        # Need parent market cap; derive from stock_price and total_shares
        if panel.total_shares is not None and panel.total_shares > 0:
            # We don't have stock_price here; calculate ratio only
            pass
        
        # Core Condition 3: Coverage ratio >= 30%
        # Coverage = visible_holding_value / parent_market_cap
        # This requires stock_price to calculate parent_market_cap
        # We'll calculate it in the main analyzer where stock_price is available
        
        result.details["visible_holding_value"] = visible_holding_value
        result.details["min_holding_ratio"] = min_holding_ratio
        
        return result
    
    def calculate_discount(self, result: SubTypeBResult,
                           stock_price: float, total_shares: float) -> SubTypeBResult:
        """Calculate discount rate and coverage (requires stock_price)"""
        if result.sotp_value is None or result.sotp_value <= 0:
            return result
        
        parent_market_cap = stock_price * total_shares  # 亿元 (total_shares already in 亿股)
        
        if parent_market_cap > 0:
            # Discount rate = (SOTP - Market Cap) / SOTP
            result.discount_rate = (result.sotp_value - parent_market_cap) / result.sotp_value
            result.coverage_ratio = result.visible_holding_value / parent_market_cap if parent_market_cap > 0 else 0
            
            # Core Condition 1: Discount rate >= 30%
            result.discount_rate_pass = result.discount_rate >= 0.30
            
            # Core Condition 3: Coverage >= 30%
            result.coverage_pass = result.coverage_ratio >= 0.30
            
            result.details["parent_market_cap"] = parent_market_cap
            result.details["discount_rate"] = round(result.discount_rate * 100, 1)
            result.details["coverage_ratio"] = round(result.coverage_ratio * 100, 1)
        
        # Final validity: ALL core conditions must pass
        result.is_valid = (
            result.discount_rate_pass and
            result.min_holding_ratio_pass and
            result.coverage_pass and
            result.parent_net_cash_pass
        )
        
        return result
    
    def _calculate_parent_net_cash(self, panel: FinancialPanel) -> Optional[float]:
        """Calculate parent company net cash"""
        cash = panel.cash_and_equivalents or 0
        st_invest = panel.short_term_investments or 0
        time_dep = panel.time_deposits or 0
        interest_debt = (panel.short_term_debt or 0) + (panel.long_term_debt or 0)
        return cash + st_invest + time_dep - interest_debt


class SubTypeCAnalyzer:
    """
    子类型C：事件驱动型
    C1a: 资产处置/分拆, C1b: 股份回购, C1c: 清算/私有化, C2: 政策风险修复
    """
    
    def analyze(self, panel: FinancialPanel, metrics: CigarButtMetrics,
                stock_price: float) -> SubTypeCResult:
        result = SubTypeCResult()
        
        # Check C1a: Asset disposal / spin-off
        result.c1a_valid = self._check_c1a(panel, metrics, stock_price)
        if result.c1a_valid:
            result.subtype = "C1a"
            result.is_valid = True
            result.event_probability = "B"
        
        # Check C1b: Buyback
        result.c1b_valid = self._check_c1b(panel, metrics, stock_price)
        if result.c1b_valid and not result.is_valid:
            result.subtype = "C1b"
            result.is_valid = True
            result.event_probability = "B"
        
        # Check C1c: Liquidation / privatization
        result.c1c_valid = self._check_c1c(panel, metrics, stock_price)
        if result.c1c_valid and not result.is_valid:
            result.subtype = "C1c"
            result.is_valid = True
            result.event_probability = "A"
        
        # Check C2: Policy risk repair
        c2_result = self._check_c2(panel, metrics, stock_price)
        result.c2_valid = c2_result["valid"]
        result.c2_score = c2_result["score"]
        if result.c2_valid and not result.is_valid:
            result.subtype = "C2"
            result.is_valid = True
            result.event_probability = c2_result["probability"]
        
        # If multiple subtypes valid, pick the one with highest confidence
        if result.c1a_valid and result.c1b_valid:
            result.subtype = "C1a+C1b"
        elif result.c1a_valid and result.c2_valid:
            result.subtype = "C1a+C2"
        elif result.c1b_valid and result.c2_valid:
            result.subtype = "C1b+C2"
        
        result.details = {
            "c1a": result.c1a_valid,
            "c1b": result.c1b_valid,
            "c1c": result.c1c_valid,
            "c2_score": result.c2_score,
        }
        
        return result
    
    def _check_c1a(self, panel: FinancialPanel, metrics: CigarButtMetrics,
                   stock_price: float) -> bool:
        """C1a: Asset disposal / spin-off"""
        # Condition 1: Non-core asset value > 50% of parent market cap
        # Condition 2: Has announcement or clear signal
        # Condition 3: Post-disposal net cash > current market cap
        
        # Check pending events for asset disposal signals
        for event in panel.pending_events:
            if event.get("type", "").lower() in ("asset_disposal", "spin_off", "divestiture", "资产处置", "分拆"):
                # Check probability
                prob = event.get("probability", "").upper()
                if prob in ("A", "B"):  # >50% probability
                    # Rough check: if T0_NAV > market cap after disposal
                    if metrics.t0_nav_per_share is not None:
                        market_cap = stock_price * panel.total_shares
                        # Simplified: if T0_NAV is significantly positive
                        if metrics.t0_nav_per_share > stock_price * 0.5:
                            return True
        
        return False
    
    def _check_c1b(self, panel: FinancialPanel, metrics: CigarButtMetrics,
                   stock_price: float) -> bool:
        """C1b: Buyback-driven"""
        # Condition 1: Net cash > 10% of market cap
        # Condition 2: PB < 0.6
        # Condition 3: Buyback authorization > 5% of total shares
        # Condition 4: Actual execution > 30% of authorization
        
        market_cap = stock_price * panel.total_shares / 1e8  # 亿元
        
        # Net cash check
        net_cash = (panel.cash_and_equivalents or 0)
        net_cash += (panel.short_term_investments or 0)
        net_cash += (panel.time_deposits or 0)
        net_cash -= (panel.short_term_debt or 0)
        net_cash -= (panel.long_term_debt or 0)
        
        if market_cap > 0 and net_cash / market_cap <= 0.10:
            return False
        
        # PB check
        if metrics.pb_ratio is None or metrics.pb_ratio >= 0.6:
            return False
        
        # Buyback authorization and execution
        auth = panel.buyback_authorization
        executed = panel.buyback_executed
        
        if auth is not None and auth > 5.0:  # > 5%
            if executed is not None and executed > auth * 0.30:  # > 30% of auth
                return True
        
        return False
    
    def _check_c1c(self, panel: FinancialPanel, metrics: CigarButtMetrics,
                   stock_price: float) -> bool:
        """C1c: Liquidation / privatization"""
        # Check pending events for liquidation/privatization announcements
        for event in panel.pending_events:
            event_type = event.get("type", "").lower()
            if event_type in ("liquidation", "privatization", "清算", "私有化"):
                prob = event.get("probability", "").upper()
                if prob in ("A", "B"):
                    # Check if offer price > current price
                    offer_price = event.get("offer_price")
                    if offer_price is not None and offer_price > stock_price * 1.05:
                        return True
                    # Or liquidation value > market cap
                    if metrics.t2_nav_per_share is not None:
                        liq_value_ps = metrics.t2_nav_per_share * 0.8  # 8折清算
                        if liq_value_ps > stock_price:
                            return True
        
        return False
    
    def _check_c2(self, panel: FinancialPanel, metrics: CigarButtMetrics,
                  stock_price: float) -> Dict:
        """C2: Policy / institutional risk repair. Returns {valid, score, probability}"""
        result = {"valid": False, "score": 0.0, "probability": "D"}
        
        # Check pending events for policy catalysts
        policy_events = []
        for event in panel.pending_events:
            event_type = event.get("type", "").lower()
            if event_type in ("policy", "regulation", "制度", "政策", "牌照"):
                policy_events.append(event)
        
        if not policy_events:
            return result
        
        # C2 scoring (0-10)
        score = 0.0
        best_prob = "D"
        
        for event in policy_events:
            prob = event.get("probability", "").upper()
            if prob == "A":
                score += 3
                best_prob = "A"
            elif prob == "B":
                score += 2
                if best_prob not in ("A",):
                    best_prob = "B"
            elif prob == "C":
                score += 1
                if best_prob not in ("A", "B"):
                    best_prob = "C"
        
        # Valuation safety cushion (0-2 points)
        if metrics.t0_nav_per_share is not None and stock_price > 0:
            nav_ratio = metrics.t0_nav_per_share / stock_price
            if nav_ratio > 2.0:
                score += 2
            elif nav_ratio > 1.5:
                score += 1
        elif metrics.t2_nav_per_share is not None and stock_price > 0:
            nav_ratio = metrics.t2_nav_per_share / stock_price
            if nav_ratio > 2.0:
                score += 2
            elif nav_ratio > 1.5:
                score += 1
        
        # Cap at 10
        score = min(10, score)
        
        # Hard threshold: score >= 6 and valuation cushion >= 1 point
        result["score"] = score
        result["probability"] = best_prob
        
        # Need at least some NAV cushion
        has_cushion = False
        if metrics.t0_nav_per_share is not None and metrics.t0_nav_per_share / stock_price > 1.5:
            has_cushion = True
        if metrics.t2_nav_per_share is not None and metrics.t2_nav_per_share / stock_price > 1.5:
            has_cushion = True
        
        result["valid"] = (score >= 6) and has_cushion
        
        return result


class RedemptionPathChecker:
    """
    兑现路径完整性检验
    防止"T级通过、Fact Check通过、但没有任何价值兑现机制"的价值陷阱
    """
    
    # Risk-free rates by market (%)
    RISK_FREE_RATES = {
        MarketType.HK: 4.0,
        MarketType.A_SHARE: 2.5,
        MarketType.US: 4.5,
    }
    
    def check(self, panel: FinancialPanel, metrics: CigarButtMetrics) -> RedemptionPathResult:
        result = RedemptionPathResult()
        
        market = self._detect_market(panel.market)
        result.risk_free_rate = self.RISK_FREE_RATES[market]
        
        # Step 1: Count valid subtypes
        valid_count = 0
        details = []
        
        # Subtype A valid?
        if metrics.subtype_a.is_valid:
            valid_count += 1
            details.append("子类型A（高股息破净型）：核心条件全部满足")
        
        # Subtype B valid?
        if metrics.subtype_b.is_valid:
            valid_count += 1
            details.append("子类型B（控股套利型）：核心条件全部满足")
        
        # Subtype C valid?
        if metrics.subtype_c.is_valid:
            valid_count += 1
            details.append(f"子类型C（事件驱动型）：{metrics.subtype_c.subtype} 满足")
        
        result.valid_path_count = valid_count
        result.has_valid_path = valid_count >= 1
        result.details = details
        
        # Step 2: If no valid path, cap rating at C
        if not result.has_valid_path:
            result.rating_cap = "C"
            details.append("无兑现路径：子类型A/B/C均不满足核心条件，存在价值陷阱风险")
        
        # Step 3: Hold return floor check (all stocks)
        if panel.dividend_yield is not None:
            result.dividend_vs_risk_free = panel.dividend_yield - result.risk_free_rate
            
            # If dividend < risk-free AND no B or C subtype -> WARNING
            if panel.dividend_yield < result.risk_free_rate:
                if not metrics.subtype_b.is_valid and not metrics.subtype_c.is_valid:
                    result.hold_return_warning = True
        
        return result
    
    def _detect_market(self, market_str: str) -> MarketType:
        s = market_str.lower()
        if "港" in s or "hk" in s:
            return MarketType.HK
        elif "美" in s or "us" in s:
            return MarketType.US
        else:
            return MarketType.A_SHARE


# ==================== State-Owned Bonus Calculator ====================

class StateOwnedBonusCalculator:
    """
    国企/央企控股属性加分 (加分项#21)
    
    层级加分:
      央企直属/控股 -> +3
      省/直辖市国企 -> +2
      市/区级国企  -> +1
      非国企        -> +0
    
    持股比例折扣:
      >=30%  -> 全额
      10-30% -> 减半(向下取整)
      <10%   -> 不适用
    """
    
    BONUS_MAP = {
        "央企": 3,
        "央企直属": 3,
        "央企控股": 3,
        "省级": 2,
        "省/直辖市": 2,
        "省": 2,
        "直辖市": 2,
        "市区级": 1,
        "市级": 1,
        "区级": 1,
        "市/区级": 1,
        "": 0,
    }
    
    def calculate(self, panel: FinancialPanel) -> int:
        if not panel.is_state_owned:
            return 0
        
        # Normalize level name
        level = panel.state_owned_level or ""
        base_bonus = 0
        for key, bonus in self.BONUS_MAP.items():
            if key and key in level:
                base_bonus = max(base_bonus, bonus)
        
        # Holding ratio adjustment
        ratio = panel.state_owned_ratio or 0
        if ratio >= 30:
            return base_bonus
        elif ratio >= 10:
            return base_bonus // 2  # Halve, round down
        else:
            return 0


class ListedSubsidiaryBonusCalculator:
    """
    上市子公司/联营公司持股价值加分 (加分项#20)
    
    可见持股价值 = Σ(上市子公司市值 × 持股比例)
    持股价值覆盖率 = 可见持股价值 / 母公司市值
    
    加分规则:
      >100%  -> +3
      50-100% -> +2
      20-50%  -> +1
      <20%    -> +0
    
    子类型B不额外加分（避免与SOTP重复计算）
    """
    
    def calculate(self, panel: FinancialPanel, stock_price: float) -> int:
        if not panel.subsidiary_holdings or stock_price <= 0 or not panel.total_shares:
            return 0
        
        # Calculate visible holding value (only listed subsidiaries)
        visible_holding_value = 0.0
        for holding in panel.subsidiary_holdings:
            if holding.get("is_listed"):
                market_cap = holding.get("market_cap", 0)
                ratio = holding.get("holding_ratio", 0)
                if market_cap > 0 and ratio > 0:
                    visible_holding_value += market_cap * ratio
        
        if visible_holding_value <= 0:
            return 0
        
        # Parent market cap (亿元)
        parent_market_cap = stock_price * panel.total_shares
        if parent_market_cap <= 0:
            return 0
        
        coverage = visible_holding_value / parent_market_cap
        
        if coverage > 1.0:
            return 3
        elif coverage >= 0.5:
            return 2
        elif coverage >= 0.2:
            return 1
        else:
            return 0


class BonusAggregator:
    """
    加分汇总器
    
    汇总规则:
      - 合计加分上限: +5 (封顶)
      - 基础评级B + 加分>=2 -> 可升级为B+
      - 基础评级C + 加分>=3 -> 可升级为B
      - 基础评级D -> 不因加分改变 (一票否决不可逆)
      - 子类型B: #20不额外加分, #21适用
    """
    
    def aggregate(self, panel: FinancialPanel, metrics: CigarButtMetrics,
                  stock_price: float, base_rating: str) -> Dict:
        """Calculate total bonus and adjusted rating. Returns dict with details."""
        
        # Calculate individual bonuses
        so_bonus = StateOwnedBonusCalculator().calculate(panel)
        
        # #20: Listed subsidiary bonus
        # SubTypeB does not get extra #20 bonus to avoid double counting with SOTP
        if metrics.subtype_b.is_valid:
            ls_bonus = 0  # Already captured in SOTP framework
            ls_detail = "子类型B有效，#20不重复计算"
        else:
            ls_bonus = ListedSubsidiaryBonusCalculator().calculate(panel, stock_price)
            ls_detail = f"上市子公司持股加分: +{ls_bonus}"
        
        # Total bonus (capped at 5)
        total = min(5, so_bonus + ls_bonus)
        
        # Apply upgrade rules
        adjusted_rating = base_rating
        upgrade_reason = ""
        
        if base_rating == "D":
            upgrade_reason = "基础评级D，一票否决不可逆"
        elif base_rating == "C" and total >= 3:
            adjusted_rating = "B"
            upgrade_reason = f"基础评级C + 加分{total}>=3 -> 升级为B"
        elif base_rating == "B" and total >= 2:
            adjusted_rating = "B+"
            upgrade_reason = f"基础评级B + 加分{total}>=2 -> 升级为B+"
        elif total > 0:
            upgrade_reason = f"加分+{total}，但不足以上升评级"
        else:
            upgrade_reason = "无加分"
        
        return {
            "state_owned_bonus_raw": so_bonus,
            "listed_subsidiary_bonus_raw": ls_bonus,
            "listed_subsidiary_detail": ls_detail,
            "total_bonus": total,
            "base_rating": base_rating,
            "adjusted_rating": adjusted_rating,
            "upgrade_reason": upgrade_reason,
        }


# ==================== Trade Engine (Phase 5) ====================

@dataclass
class EntryPlan:
    """分批建仓计划"""
    target_position_ratio: float = 0.0  # 目标仓位占总资产比例 (%)
    first_entry_ratio: float = 0.50     # 首次建仓占目标仓位的比例
    entry_price: float = 0.0            # 首次买入价
    add_10pct_price: float = 0.0        # 跌10%追加价
    add_15pct_price: float = 0.0        # 跌15%满仓价
    details: Dict = field(default_factory=dict)


@dataclass
class StopLossRule:
    """止损规则集合"""
    hard_stop_price: float = 0.0          # 硬性止损价（买入价再跌10%）
    dividend_stop_triggered: bool = False  # 股息实质性削减止损
    fundamental_stop_triggered: bool = False  # 基本面恶化止损（审计非标/管理层问题/FactCheck D）
    subtype_stop_triggered: bool = False   # 子类型特定止损
    subtype_stop_reason: str = ""          # 子类型止损原因
    details: Dict = field(default_factory=dict)


@dataclass
class TakeProfitPlan:
    """止盈/减仓计划"""
    t0_target_price: Optional[float] = None
    t1_target_price: Optional[float] = None
    t2_target_price: Optional[float] = None
    reduce_at_t0_ratio: float = 0.50    # 达到T0_NAV时减仓50%
    reduce_at_t1_ratio: float = 0.30    # 达到T1_NAV时再减仓30%
    reduce_at_t2_ratio: float = 1.00    # 达到T2_NAV时清仓
    details: Dict = field(default_factory=dict)


@dataclass
class TradePlanResult:
    """完整交易计划"""
    entry: EntryPlan = field(default_factory=EntryPlan)
    stop_loss: StopLossRule = field(default_factory=StopLossRule)
    take_profit: TakeProfitPlan = field(default_factory=TakeProfitPlan)
    position_size_pct: float = 0.0      # 建议仓位（占总资产%）
    kelly_fraction: Optional[float] = None  # Half-Kelly仓位比例
    details: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class TradeEngine:
    """
    Phase 5: 交易执行引擎
    
    功能:
      1. 仓位管理: 根据T级和子类型确定单票上限
      2. Kelly准则: Half-Kelly ≈ 17.5% 作为参考
      3. 分批建仓: 首次50% -> 跌10%至80% -> 跌15%至100%
      4. 止损规则: 硬性/股息/基本面/子类型
      5. 止盈减仓: T0减50% -> T1再减30% -> T2清仓
    """
    
    # Position size caps by type
    POSITION_CAPS = {
        "T0": 0.10,
        "T1": 0.08,
        "T2": 0.05,
        "C1": 0.08,   # 事件驱动-资产/回购 5-8%, use 8% upper bound
        "C2": 0.05,   # 事件驱动-政策 2-5%, use 5% upper bound
    }
    
    # Kelly criterion parameters
    KELLY_WIN_PROB = 0.65      # 烟蒂股胜率假设 65%
    KELLY_WIN_LOSS_RATIO = 2.5 # 平均盈利/亏损比 2.5:1
    KELLY_FRACTION = 0.5       # Half-Kelly
    
    def generate_trade_plan(self, panel: FinancialPanel, metrics: CigarButtMetrics,
                           stock_price: float) -> TradePlanResult:
        result = TradePlanResult()
        
        if not stock_price or stock_price <= 0:
            result.warnings.append("股价无效，无法生成交易计划")
            return result
        
        # === 1. 仓位管理 ===
        position_cap = self._calculate_position_cap(metrics)
        result.position_size_pct = position_cap * 100
        
        # Kelly criterion (reference only)
        kelly = self._calculate_half_kelly()
        result.kelly_fraction = kelly * 100
        
        # Use the more conservative of position cap and Kelly
        conservative_position = min(position_cap, kelly)
        result.details["position_cap"] = round(position_cap * 100, 1)
        result.details["kelly_reference"] = round(kelly * 100, 1)
        result.details["conservative_position"] = round(conservative_position * 100, 1)
        
        # === 2. 分批建仓计划 ===
        result.entry = self._calculate_entry_plan(metrics, stock_price, conservative_position)
        
        # === 3. 止损规则 ===
        result.stop_loss = self._calculate_stop_loss(panel, metrics, stock_price)
        
        # === 4. 止盈减仓计划 ===
        result.take_profit = self._calculate_take_profit(metrics, stock_price)
        
        # === 5. 高基数股息检验 ===
        dividend_check = self._check_dividend_cut(panel, metrics)
        if dividend_check["triggered"]:
            result.stop_loss.dividend_stop_triggered = True
            result.stop_loss.details["dividend_stop"] = dividend_check["reason"]
            result.warnings.append(f"[股息止损] {dividend_check['reason']}")
        
        return result
    
    def _calculate_position_cap(self, metrics: CigarButtMetrics) -> float:
        """Calculate position size cap based on T-level and subtype"""
        cap = 0.0
        
        # Base cap from T-level
        if metrics.is_t0_pass:
            cap = self.POSITION_CAPS["T0"]
        elif metrics.is_t1_pass:
            cap = self.POSITION_CAPS["T1"]
        elif metrics.is_t2_pass:
            cap = self.POSITION_CAPS["T2"]
        
        # Subtype C overrides (if no T-level passes)
        if cap == 0:
            if metrics.subtype_c.is_valid:
                if metrics.subtype_c.subtype in ("C1a", "C1b", "C1c"):
                    cap = self.POSITION_CAPS["C1"]
                elif metrics.subtype_c.subtype == "C2":
                    cap = self.POSITION_CAPS["C2"]
        
        # If still 0 but has valid redemption path, use conservative cap
        if cap == 0 and metrics.redemption_path.has_valid_path:
            cap = 0.03  # 3% conservative
        
        return cap
    
    def _calculate_half_kelly(self) -> float:
        """Half-Kelly criterion: f* = (p*b - q) / b * 0.5"""
        p = self.KELLY_WIN_PROB
        q = 1 - p
        b = self.KELLY_WIN_LOSS_RATIO
        kelly = (p * b - q) / b
        return max(0, kelly * self.KELLY_FRACTION)
    
    def _calculate_entry_plan(self, metrics: CigarButtMetrics, stock_price: float,
                              target_position: float) -> EntryPlan:
        """Calculate staged entry plan"""
        plan = EntryPlan()
        
        # Determine entry price from buy threshold
        entry_price = None
        if metrics.is_t0_pass and metrics.t0_buy_threshold:
            entry_price = metrics.t0_buy_threshold
        elif metrics.is_t1_pass and metrics.t1_buy_threshold:
            entry_price = metrics.t1_buy_threshold
        elif metrics.is_t2_pass and metrics.t2_buy_threshold:
            entry_price = metrics.t2_buy_threshold
        
        if entry_price is None:
            plan.details["error"] = "无有效买入阈值"
            return plan
        
        plan.target_position_ratio = round(target_position * 100, 1)
        plan.first_entry_ratio = 0.50
        plan.entry_price = round(entry_price, 2)
        plan.add_10pct_price = round(entry_price * 0.90, 2)
        plan.add_15pct_price = round(entry_price * 0.85, 2)
        
        plan.details = {
            "first_entry_amount": f"目标仓位的 {plan.first_entry_ratio*100:.0f}%",
            "second_entry_trigger": f"股价跌至 {plan.add_10pct_price:.2f} (再跌10%)",
            "second_entry_amount": f"加仓至目标仓位的 80%",
            "third_entry_trigger": f"股价跌至 {plan.add_15pct_price:.2f} (再跌15%)",
            "third_entry_amount": f"满仓至目标仓位的 100%",
        }
        
        return plan
    
    def _calculate_stop_loss(self, panel: FinancialPanel, metrics: CigarButtMetrics,
                            stock_price: float) -> StopLossRule:
        """Calculate comprehensive stop loss rules"""
        rule = StopLossRule()
        
        # Hard stop: entry price * 0.90 (10% below entry)
        entry_price = None
        if metrics.is_t0_pass and metrics.t0_buy_threshold:
            entry_price = metrics.t0_buy_threshold
        elif metrics.is_t1_pass and metrics.t1_buy_threshold:
            entry_price = metrics.t1_buy_threshold
        elif metrics.is_t2_pass and metrics.t2_buy_threshold:
            entry_price = metrics.t2_buy_threshold
        
        if entry_price:
            rule.hard_stop_price = round(entry_price * 0.90, 2)
            rule.details["hard_stop"] = f"买入价{entry_price:.2f}再跌10% = {rule.hard_stop_price:.2f}"
        
        # Fundamental stop: Fact Check D or audit veto or fraud
        if metrics.fact_check_rating == "D":
            rule.fundamental_stop_triggered = True
            rule.details["fundamental_stop"] = "Fact Check评级D（一票否决项触发）"
        
        fc_audit = metrics.fact_check_results.get("FC17_audit_opinion")
        if fc_audit and fc_audit.status == "VETO":
            rule.fundamental_stop_triggered = True
            rule.details["audit_stop"] = "审计意见非标 -> 一票否决"
        
        fc_mgmt = metrics.fact_check_results.get("FC18_management_integrity")
        if fc_mgmt and fc_mgmt.status == "VETO":
            rule.fundamental_stop_triggered = True
            rule.details["mgmt_stop"] = "管理层诚信问题 -> 一票否决"
        
        # Subtype-specific stops
        if metrics.subtype_b.is_valid:
            # Subtype B: discount rate converges below 15%
            if metrics.subtype_b.discount_rate is not None and metrics.subtype_b.discount_rate < 0.15:
                rule.subtype_stop_triggered = True
                rule.subtype_stop_reason = "控股折价率收敛至<15%，套利空间消失"
                rule.details["subtype_b_stop"] = rule.subtype_stop_reason
        
        if metrics.subtype_c.is_valid and metrics.subtype_c.subtype in ("C1a", "C1b", "C1c", "C2"):
            # Subtype C: catalyst not materialized by expected date
            # This is checked externally; mark as warning if pending_events exist but no execution
            pending = panel.pending_events
            if pending:
                overdue = [e for e in pending if e.get("probability", "").upper() in ("C", "D")]
                if overdue:
                    rule.subtype_stop_triggered = True
                    rule.subtype_stop_reason = f"催化剂概率降级({len(overdue)}项)，建议减仓"
                    rule.details["subtype_c_stop"] = rule.subtype_stop_reason
        
        return rule
    
    def _calculate_take_profit(self, metrics: CigarButtMetrics, stock_price: float) -> TakeProfitPlan:
        """Calculate staged take-profit / reduction plan"""
        plan = TakeProfitPlan()
        
        if metrics.t0_nav_per_share:
            plan.t0_target_price = round(metrics.t0_nav_per_share, 2)
        if metrics.t1_nav_per_share:
            plan.t1_target_price = round(metrics.t1_nav_per_share, 2)
        if metrics.t2_nav_per_share:
            plan.t2_target_price = round(metrics.t2_nav_per_share, 2)
        
        plan.details = {
            "t0_action": f"股价 ≥ T0_NAV({plan.t0_target_price or 'N/A'}) 时减仓 {plan.reduce_at_t0_ratio*100:.0f}%",
            "t1_action": f"股价 ≥ T1_NAV({plan.t1_target_price or 'N/A'}) 时再减仓 {plan.reduce_at_t1_ratio*100:.0f}%",
            "t2_action": f"股价 ≥ T2_NAV({plan.t2_target_price or 'N/A'}) 时清仓 {plan.reduce_at_t2_ratio*100:.0f}%",
            "rationale": "烟蒂股不应持有到完全估值修复，逐步兑现安全边际",
        }
        
        return plan
    
    def _check_dividend_cut(self, panel: FinancialPanel, metrics: CigarButtMetrics) -> Dict:
        """
        高基数股息检验
        
        第1步: 计算前3年（或最长连续期间）平均年化股息作为"正常化股息基准"
        第2步: 最新股息 vs 正常化基准
          < 正常化基准 × 0.85 → 实质性削减，触发止损
          ≥ 正常化基准 × 0.85 但 < 前一期 × 0.70 → 高基数回落，降级为"观察"
          ≥ 正常化基准 → 不构成削减
        """
        history = panel.dividend_history
        if not history or len(history) < 2:
            return {"triggered": False, "reason": "股息历史数据不足，无法检验"}
        
        # Latest dividend (last element)
        latest = history[-1]
        
        # Normalized baseline: average of available history (up to 3 years)
        baseline_years = min(3, len(history))
        baseline = sum(history[-baseline_years-1:-1]) / baseline_years
        
        # Previous period dividend
        previous = history[-2]
        
        result = {"triggered": False, "reason": ""}
        
        if baseline > 0:
            vs_baseline = latest / baseline
            vs_previous = latest / previous if previous > 0 else 1.0
            
            result["vs_baseline"] = round(vs_baseline, 2)
            result["vs_previous"] = round(vs_previous, 2)
            result["baseline"] = round(baseline, 2)
            
            if vs_baseline < 0.85:
                result["triggered"] = True
                result["reason"] = f"最新股息({latest}) < 正常化基准({baseline:.2f}) × 0.85，实质性削减"
            elif vs_previous < 0.70 and vs_baseline >= 0.85:
                result["triggered"] = False
                result["reason"] = f"高基数回落：环比降{((1-vs_previous)*100):.0f}%，但 vs 正常化基准 {vs_baseline:.2f} ≥ 0.85，降级为观察"
                result["watch_only"] = True
            else:
                result["reason"] = f"股息正常：vs 正常化基准 {vs_baseline:.2f}，vs 前一期 {vs_previous:.2f}"
        
        return result


# ==================== Fact Check Engine (Phase 3) ====================

class FactCheckItem:
    """Single fact check result"""
    def __init__(self, name: str, status: str, category: str = "", detail: str = "", value: Optional[float] = None):
        self.name = name
        self.status = status  # PASS / WARNING / VETO
        self.category = category  # Data / Risk
        self.detail = detail
        self.value = value
    
    def to_dict(self) -> Dict:
        return {"name": self.name, "status": self.status, "category": self.category, "detail": self.detail, "value": self.value}


class FactCheckEngine:
    """
    22项Fact Check清单引擎 (v1.8)
    优先实现[COMPUTABLE]项，[LLM-REQUIRED]项标记为待LLM补充
    """
    
    def run(self, panel: FinancialPanel, metrics: CigarButtMetrics, stock_price: float) -> Dict:
        results = {}
        
        # === 6.1 资产质量核查 ===
        results["FC01_restricted_cash"] = self._check_fc01_restricted_cash(panel, metrics)
        results["FC02_pledged_assets"] = self._check_fc02_pledged_assets(panel)
        results["FC03_goodwill_ratio"] = self._check_fc03_goodwill_ratio(panel)
        results["FC04_goodwill_impairment"] = self._check_fc04_goodwill_impairment(panel)
        results["FC05_ar_quality"] = self._check_fc05_ar_quality(panel)
        results["FC06_inventory_turnover"] = self._check_fc06_inventory_turnover(panel)
        results["FC07_intangible_assets"] = self._check_fc07_intangible_assets(panel)
        
        # === 6.2 负债隐患核查 ===
        results["FC08_off_balance_sheet"] = self._check_fc08_off_balance_sheet(panel, stock_price, metrics)
        results["FC09_capital_commitments"] = self._check_fc09_capital_commitments(panel)
        results["FC10_guarantees"] = self._check_fc10_guarantees(panel)
        results["FC11_pension_deficit"] = self._check_fc11_pension_deficit(panel, stock_price, metrics)
        results["FC12_environmental_legal"] = self._check_fc12_environmental_legal(panel)
        results["FC13_other_payables"] = self._check_fc13_other_payables(panel)
        
        # === 6.3 经营质量核查 ===
        results["FC14_related_party_transactions"] = self._check_fc14_related_party_transactions(panel)
        results["FC15_revenue_concentration"] = self._check_fc15_revenue_concentration(panel)
        results["FC16_q4_spike"] = self._check_fc16_q4_spike(panel)
        results["FC17_audit_opinion"] = self._check_fc17_audit_opinion(panel)
        results["FC18_management_integrity"] = self._check_fc18_management_integrity(panel)
        results["FC19_govt_subsidy"] = self._check_fc19_govt_subsidy(panel)
        
        # === 6.4 加分项核查 ===
        results["FC20_listed_subsidiaries"] = self._check_fc20_listed_subsidiaries(panel)
        results["FC21_state_owned"] = self._check_fc21_state_owned(panel)
        
        # === 6.5 资产结构健康度检验 ===
        results["FC22_non_current_financial_assets"] = self._check_fc22_non_current_financial_assets(panel, stock_price, metrics)
        
        return results
    
    # ---------- 6.1 资产质量核查 ----------
    
    def _check_fc01_restricted_cash(self, panel: FinancialPanel, metrics: CigarButtMetrics) -> FactCheckItem:
        """#1 受限现金占比 [COMPUTABLE]"""
        ratio_str = f"{metrics.restricted_cash_ratio*100:.1f}%" if metrics.restricted_cash_ratio is not None else "N/A"
        if metrics.restricted_cash_warning == "VETO":
            return FactCheckItem("受限现金占比", "VETO", "Risk", f"受限现金占比{ratio_str} > 20%", metrics.restricted_cash_ratio)
        elif metrics.restricted_cash_warning == "WARNING":
            return FactCheckItem("受限现金占比", "WARNING", "Risk", f"受限现金占比{ratio_str}", metrics.restricted_cash_ratio)
        return FactCheckItem("受限现金占比", "PASS", "", f"受限现金占比{ratio_str} <= 5%", metrics.restricted_cash_ratio)
    
    def _check_fc02_pledged_assets(self, panel: FinancialPanel) -> FactCheckItem:
        """#2 质押资产 [LLM-REQUIRED] - 若数据可得则计算"""
        if panel.pledged_assets is not None and panel.total_assets and panel.total_assets > 0:
            ratio = panel.pledged_assets / panel.total_assets
            if ratio > 0.5:
                return FactCheckItem("质押资产", "VETO", "Risk", f"核心资产被质押，占比{ratio*100:.1f}%", ratio)
            elif ratio > 0.2:
                return FactCheckItem("质押资产", "WARNING", "Risk", f"质押资产占比{ratio*100:.1f}%", ratio)
            return FactCheckItem("质押资产", "PASS", "", f"质押资产占比{ratio*100:.1f}%", ratio)
        return FactCheckItem("质押资产", "WARNING", "Data", "质押资产数据缺失，需查阅附注'担保/抵押'")
    
    def _check_fc03_goodwill_ratio(self, panel: FinancialPanel) -> FactCheckItem:
        """#3 商誉占比 [COMPUTABLE]"""
        if panel.goodwill is not None and panel.total_assets and panel.total_assets > 0:
            ratio = panel.goodwill / panel.total_assets
            if ratio > 0.30:
                return FactCheckItem("商誉占比", "VETO", "Risk", f"商誉/总资产 = {ratio*100:.1f}% > 30%", ratio)
            elif ratio > 0.15:
                return FactCheckItem("商誉占比", "WARNING", "Risk", f"商誉/总资产 = {ratio*100:.1f}% (15-30%)", ratio)
            return FactCheckItem("商誉占比", "PASS", "", f"商誉/总资产 = {ratio*100:.1f}% <= 15%", ratio)
        return FactCheckItem("商誉占比", "WARNING", "Data", "商誉或总资产数据缺失")
    
    def _check_fc04_goodwill_impairment(self, panel: FinancialPanel) -> FactCheckItem:
        """#4 商誉减值历史 [LLM-REQUIRED]"""
        if panel.goodwill_impairment_history:
            return FactCheckItem("商誉减值历史", "WARNING", "Risk", "过去10年存在大额商誉减值记录")
        return FactCheckItem("商誉减值历史", "PASS", "", "无重大商誉减值历史（或数据未提供）")
    
    def _check_fc05_ar_quality(self, panel: FinancialPanel) -> FactCheckItem:
        """#5 应收账款质量 [COMPUTABLE+LLM]"""
        ar = (panel.accounts_receivable or 0) + (panel.notes_receivable or 0)
        if ar <= 0:
            return FactCheckItem("应收账款质量", "PASS", "", "无应收账款")
        
        warnings = []
        # 账龄>90天占比
        if panel.ar_over_90_days is not None:
            ratio_90 = panel.ar_over_90_days / ar
            if ratio_90 > 0.30:
                warnings.append(f">90天应收占比{ratio_90*100:.1f}% > 30%")
            elif ratio_90 > 0.15:
                warnings.append(f">90天应收占比{ratio_90*100:.1f}%")
        
        # 关联方应收占比
        if panel.related_party_ar is not None:
            ratio_rp = panel.related_party_ar / ar
            if ratio_rp > 0.20:
                warnings.append(f"关联方应收占比{ratio_rp*100:.1f}% > 20%")
        
        if warnings:
            return FactCheckItem("应收账款质量", "WARNING", "Risk", "; ".join(warnings))
        return FactCheckItem("应收账款质量", "PASS", "", "应收账龄及关联方占比正常")
    
    def _check_fc06_inventory_turnover(self, panel: FinancialPanel) -> FactCheckItem:
        """#6 存货周转 [COMPUTABLE - 需行业数据]"""
        if len(panel.dio_years) >= 3:
            # Check if DIO is continuously rising
            rising = all(panel.dio_years[i] < panel.dio_years[i+1] for i in range(len(panel.dio_years)-1))
            if panel.industry_avg_dio is not None and panel.industry_avg_dio > 0:
                latest_dio = panel.dio_years[-1]
                deviation = (latest_dio - panel.industry_avg_dio) / panel.industry_avg_dio
                if rising and deviation > 0.50:
                    return FactCheckItem("存货周转", "WARNING", "Risk", f"DIO连续上升且偏离行业均值{deviation*100:.0f}%")
                return FactCheckItem("存货周转", "PASS", "", f"DIO趋势正常，偏离行业{deviation*100:.0f}%")
            return FactCheckItem("存货周转", "PASS", "", f"DIO历史: {panel.dio_years}")
        return FactCheckItem("存货周转", "WARNING", "Data", "存货周转天数历史数据不足（需至少3年）")
    
    def _check_fc07_intangible_assets(self, panel: FinancialPanel) -> FactCheckItem:
        """#7 无形资产合理性 [COMPUTABLE]"""
        if panel.unidentifiable_intangible_assets is not None and panel.total_equity and panel.total_equity > 0:
            ratio = panel.unidentifiable_intangible_assets / panel.total_equity
            if ratio > 0.40:
                return FactCheckItem("无形资产合理性", "WARNING", "Risk", f"不可辨认无形资产/净资产 = {ratio*100:.1f}% > 40%", ratio)
            return FactCheckItem("无形资产合理性", "PASS", "", f"不可辨认无形资产/净资产 = {ratio*100:.1f}% <= 40%", ratio)
        # Fallback: use total intangible assets
        if panel.intangible_assets is not None and panel.total_equity and panel.total_equity > 0:
            ratio = panel.intangible_assets / panel.total_equity
            if ratio > 0.40:
                return FactCheckItem("无形资产合理性", "WARNING", "Risk", f"无形资产/净资产 = {ratio*100:.1f}% > 40% (未区分可辨认性)", ratio)
            return FactCheckItem("无形资产合理性", "PASS", "", f"无形资产/净资产 = {ratio*100:.1f}%", ratio)
        return FactCheckItem("无形资产合理性", "WARNING", "Data", "无形资产或净资产数据缺失")
    
    # ---------- 6.2 负债隐患核查 ----------
    
    def _check_fc08_off_balance_sheet(self, panel: FinancialPanel, stock_price: float, metrics: CigarButtMetrics) -> FactCheckItem:
        """#8 表外负债 [COMPUTABLE+LLM]"""
        if panel.off_balance_sheet_liabilities is not None and stock_price > 0 and panel.total_shares and panel.total_shares > 0:
            market_cap = stock_price * panel.total_shares
            ratio = panel.off_balance_sheet_liabilities / market_cap
            if ratio > 0.15:
                return FactCheckItem("表外负债", "WARNING", "Risk", f"或有负债/市值 = {ratio*100:.1f}% > 15%", ratio)
            return FactCheckItem("表外负债", "PASS", "", f"或有负债/市值 = {ratio*100:.1f}% <= 15%", ratio)
        return FactCheckItem("表外负债", "WARNING", "Data", "表外负债数据缺失，需查阅'承诺及或有负债'附注")
    
    def _check_fc09_capital_commitments(self, panel: FinancialPanel) -> FactCheckItem:
        """#9 资本承诺 [COMPUTABLE+LLM]"""
        net_cash = (panel.cash_and_equivalents or 0) + (panel.short_term_investments or 0) + (panel.time_deposits or 0) - (panel.short_term_debt or 0) - (panel.long_term_debt or 0)
        if panel.capital_commitments is not None:
            if net_cash > 0:
                ratio = panel.capital_commitments / net_cash
                if ratio > 0.30:
                    return FactCheckItem("资本承诺", "WARNING", "Risk", f"已承诺未支出/净现金 = {ratio*100:.1f}% > 30%", ratio)
                return FactCheckItem("资本承诺", "PASS", "", f"已承诺未支出/净现金 = {ratio*100:.1f}% <= 30%", ratio)
            else:
                return FactCheckItem("资本承诺", "WARNING", "Risk", f"净现金<=0，但存在资本承诺{panel.capital_commitments}亿元")
        return FactCheckItem("资本承诺", "WARNING", "Data", "资本承诺数据缺失，需查阅附注")
    
    def _check_fc10_guarantees(self, panel: FinancialPanel) -> FactCheckItem:
        """#10 担保/互保 [LLM-REQUIRED]"""
        return FactCheckItem("担保/互保", "PASS", "", "需LLM查阅'对外担保'附注进行定性判断")
    
    def _check_fc11_pension_deficit(self, panel: FinancialPanel, stock_price: float, metrics: CigarButtMetrics) -> FactCheckItem:
        """#11 养老金缺口 [COMPUTABLE+LLM]"""
        if panel.pension_deficit is not None and stock_price > 0 and panel.total_shares and panel.total_shares > 0:
            market_cap = stock_price * panel.total_shares
            ratio = panel.pension_deficit / market_cap
            if ratio > 0.10:
                return FactCheckItem("养老金缺口", "WARNING", "Risk", f"养老金缺口/市值 = {ratio*100:.1f}% > 10%", ratio)
            return FactCheckItem("养老金缺口", "PASS", "", f"养老金缺口/市值 = {ratio*100:.1f}% <= 10%", ratio)
        return FactCheckItem("养老金缺口", "WARNING", "Data", "养老金数据缺失，需查阅退休福利附注")
    
    def _check_fc12_environmental_legal(self, panel: FinancialPanel) -> FactCheckItem:
        """#12 环境/法律负债 [LLM-REQUIRED]"""
        return FactCheckItem("环境/法律负债", "PASS", "", "需LLM查阅法律诉讼、环保合规附注进行定性判断")
    
    def _check_fc13_other_payables(self, panel: FinancialPanel) -> FactCheckItem:
        """#13 其他应付款异常 [COMPUTABLE]"""
        if panel.other_payables is not None and panel.current_liabilities and panel.current_liabilities > 0:
            ratio = panel.other_payables / panel.current_liabilities
            if ratio > 0.30:
                return FactCheckItem("其他应付款异常", "WARNING", "Risk", f"其他应付款/流动负债 = {ratio*100:.1f}% > 30%", ratio)
            return FactCheckItem("其他应付款异常", "PASS", "", f"其他应付款/流动负债 = {ratio*100:.1f}% <= 30%", ratio)
        return FactCheckItem("其他应付款异常", "WARNING", "Data", "其他应付款或流动负债数据缺失")
    
    # ---------- 6.3 经营质量核查 ----------
    
    def _check_fc14_related_party_transactions(self, panel: FinancialPanel) -> FactCheckItem:
        """#14 关联交易 [COMPUTABLE+LLM]"""
        revenue = panel.annual_revenue or panel.revenue
        if panel.related_party_revenue is not None and revenue and revenue > 0:
            ratio = panel.related_party_revenue / revenue
            if ratio > 0.30:
                return FactCheckItem("关联交易", "WARNING", "Risk", f"关联交易/营收 = {ratio*100:.1f}% > 30%", ratio)
            return FactCheckItem("关联交易", "PASS", "", f"关联交易/营收 = {ratio*100:.1f}% <= 30%", ratio)
        return FactCheckItem("关联交易", "WARNING", "Data", "关联交易数据缺失，需查阅'关联方交易'附注")
    
    def _check_fc15_revenue_concentration(self, panel: FinancialPanel) -> FactCheckItem:
        """#15 收入集中度 [COMPUTABLE+LLM]"""
        if panel.top5_customer_revenue_ratio is not None:
            if panel.top5_customer_revenue_ratio > 60 and not panel.is_state_owned:
                return FactCheckItem("收入集中度", "WARNING", "Risk", f"前5大客户占比{panel.top5_customer_revenue_ratio:.1f}% > 60%且非国企", panel.top5_customer_revenue_ratio)
            return FactCheckItem("收入集中度", "PASS", "", f"前5大客户占比{panel.top5_customer_revenue_ratio:.1f}%")
        return FactCheckItem("收入集中度", "WARNING", "Data", "前5大客户占比数据缺失")
    
    def _check_fc16_q4_spike(self, panel: FinancialPanel) -> FactCheckItem:
        """#16 Q4收入突增 [COMPUTABLE]"""
        if panel.q4_revenue is not None and panel.annual_revenue and panel.annual_revenue > 0:
            ratio = panel.q4_revenue / panel.annual_revenue
            if ratio > 0.40:
                return FactCheckItem("Q4收入突增", "WARNING", "Risk", f"Q4/全年营收 = {ratio*100:.1f}% > 40%", ratio)
            return FactCheckItem("Q4收入突增", "PASS", "", f"Q4/全年营收 = {ratio*100:.1f}% <= 40%", ratio)
        return FactCheckItem("Q4收入突增", "WARNING", "Data", "季度收入数据缺失")
    
    def _check_fc17_audit_opinion(self, panel: FinancialPanel) -> FactCheckItem:
        """#17 审计意见 [LLM-REQUIRED]"""
        opinion = panel.audit_opinion.lower()
        if "标准" in opinion or "无保留" in opinion or opinion == "":
            return FactCheckItem("审计意见", "PASS", "", f"审计意见: {panel.audit_opinion or '标准无保留'}")
        elif "否定" in opinion or "无法表示" in opinion:
            return FactCheckItem("审计意见", "VETO", "Risk", f"非标审计意见: {panel.audit_opinion} -> 一票否决")
        else:
            return FactCheckItem("审计意见", "WARNING", "Risk", f"非标准审计意见: {panel.audit_opinion}")
    
    def _check_fc18_management_integrity(self, panel: FinancialPanel) -> FactCheckItem:
        """#18 管理层诚信 [LLM-REQUIRED]"""
        if panel.management_fraud_history:
            return FactCheckItem("管理层诚信", "VETO", "Risk", "存在欺诈/内幕交易/挪用资金记录 -> 一票否决")
        return FactCheckItem("管理层诚信", "PASS", "", "无已知诚信问题（需LLM核查媒体报道）")
    
    def _check_fc19_govt_subsidy(self, panel: FinancialPanel) -> FactCheckItem:
        """#19 政府补贴依赖 [COMPUTABLE]"""
        if panel.govt_subsidy is not None and panel.net_profit and panel.net_profit != 0:
            ratio = panel.govt_subsidy / panel.net_profit
            if ratio > 0.50:
                return FactCheckItem("政府补贴依赖", "WARNING", "Risk", f"政府补贴/净利润 = {ratio*100:.1f}% > 50%", ratio)
            return FactCheckItem("政府补贴依赖", "PASS", "", f"政府补贴/净利润 = {ratio*100:.1f}% <= 50%", ratio)
        return FactCheckItem("政府补贴依赖", "WARNING", "Data", "政府补贴或净利润数据缺失")
    
    # ---------- 6.4 加分项核查 ----------
    
    def _check_fc20_listed_subsidiaries(self, panel: FinancialPanel) -> FactCheckItem:
        """#20 上市子公司持股 [COMPUTABLE]"""
        if panel.subsidiary_holdings:
            listed = [h for h in panel.subsidiary_holdings if h.get("is_listed")]
            if listed:
                return FactCheckItem("上市子公司持股", "PASS", "", f"识别到{len(listed)}家上市子公司")
            return FactCheckItem("上市子公司持股", "PASS", "", "无上市子公司")
        return FactCheckItem("上市子公司持股", "WARNING", "Data", "子公司持股数据缺失")
    
    def _check_fc21_state_owned(self, panel: FinancialPanel) -> FactCheckItem:
        """#21 国企/央企控股层级 [COMPUTABLE]"""
        if panel.is_state_owned:
            return FactCheckItem("国企控股层级", "PASS", "", f"国企层级: {panel.state_owned_level}, 持股: {panel.state_owned_ratio or 0:.1f}%")
        return FactCheckItem("国企控股层级", "PASS", "", "非国企")
    
    # ---------- 6.5 资产结构健康度检验 [COMPUTABLE] ----------
    
    def _check_fc22_non_current_financial_assets(self, panel: FinancialPanel, stock_price: float, metrics: CigarButtMetrics) -> FactCheckItem:
        """#22 非流动金融资产占比 [COMPUTABLE]"""
        if panel.non_current_financial_assets is None or not panel.total_assets or panel.total_assets <= 0:
            return FactCheckItem("非流动金融资产占比", "WARNING", "Data", "非流动金融资产或总资产数据缺失")
        
        ratio = panel.non_current_financial_assets / panel.total_assets
        
        if ratio <= 0.15:
            return FactCheckItem("非流动金融资产占比", "PASS", "", f"占比{ratio*100:.1f}% <= 15%", ratio)
        
        if ratio <= 0.30:
            return FactCheckItem("非流动金融资产占比", "WARNING", "Risk", f"占比{ratio*100:.1f}% (15-30%)", ratio)
        
        # 30% ~ 50%: 强制计算核心T级安全边际
        if ratio <= 0.50:
            core_cash = (panel.cash_and_equivalents or 0) + (panel.short_term_investments or 0) + (panel.time_deposits or 0)
            core_cash -= (panel.short_term_debt or 0) + (panel.long_term_debt or 0)
            if stock_price > 0 and panel.total_shares and panel.total_shares > 0:
                market_cap = stock_price * panel.total_shares
                core_t_ratio = core_cash / market_cap if market_cap > 0 else 0
                if core_t_ratio < 1.3:
                    return FactCheckItem("非流动金融资产占比", "WARNING", "Risk", f"占比{ratio*100:.1f}% + 核心T级{core_t_ratio:.2f} < 1.3 -> 评级上限锁定B级", ratio)
                return FactCheckItem("非流动金融资产占比", "WARNING", "Risk", f"占比{ratio*100:.1f}% + 核心T级{core_t_ratio:.2f} >= 1.3 (正常流程，WARNING计入)", ratio)
            return FactCheckItem("非流动金融资产占比", "WARNING", "Risk", f"占比{ratio*100:.1f}% (30-50%，需计算核心T级)", ratio)
        
        # > 50%
        return FactCheckItem("非流动金融资产占比", "VETO", "Risk", f"占比{ratio*100:.1f}% > 50% -> 资产垫实质空心化，一票否决", ratio)
    
    def calculate_rating(self, results: Dict[str, FactCheckItem]) -> str:
        """Calculate overall Fact Check rating: A/B/C/D"""
        veto_count = 0
        risk_warnings = 0
        data_warnings = 0
        
        for item in results.values():
            if item.status == "VETO":
                veto_count += 1
            elif item.status == "WARNING":
                if item.category == "Risk":
                    risk_warnings += 1
                else:
                    data_warnings += 1
        
        if veto_count > 0:
            return "D"
        if risk_warnings == 0:
            return "A"
        if risk_warnings <= 3:
            return "B"
        return "C"


# ==================== Main Analyzer ====================

class CigarButtAnalyzer:
    """
    Static Value Cigar Butt Stock Analyzer (v1.8 Full System).
    
    Phase 1: T0/T1/T2 NAV three-tier system
    Phase 2: Subtype A/B/C + Redemption path check
    """
    
    BUY_DISCOUNTS = {
        TLevel.T0: 0.85,
        TLevel.T1: 0.80,
        TLevel.T2: 0.70,
    }
    
    BURN_RATE_THRESHOLDS = {
        TLevel.T0: {"pass": 0.0, "warn_low": -0.05, "veto": -0.05},
        TLevel.T1: {"pass": 0.05, "warn_low": 0.0, "veto": 0.0},
        TLevel.T2: {"pass": 0.10, "warn_low": 0.05, "veto": 0.05},
    }
    
    def __init__(self, current_stock_price: Optional[float] = None,
                 inventory_type: InventoryType = InventoryType.DEFAULT):
        self.stock_price = current_stock_price
        self.inventory_type = inventory_type
        self.subtype_a_analyzer = SubTypeAAnalyzer()
        self.subtype_b_analyzer = SubTypeBAnalyzer()
        self.subtype_c_analyzer = SubTypeCAnalyzer()
        self.redemption_checker = RedemptionPathChecker()
        self.so_bonus_calc = StateOwnedBonusCalculator()
        self.ls_bonus_calc = ListedSubsidiaryBonusCalculator()
        self.bonus_aggregator = BonusAggregator()
        self.fact_check_engine = FactCheckEngine()
        self.trade_engine = TradeEngine()
    
    def analyze(self, panel: FinancialPanel, stock_price: Optional[float] = None) -> CigarButtMetrics:
        """Run full v1.8 cigar butt analysis"""
        price = stock_price or self.stock_price
        metrics = CigarButtMetrics()
        
        if not panel.total_shares or panel.total_shares <= 0:
            metrics.risk_flags.append("无法获取总股本")
            return metrics
        
        shares = panel.total_shares * 1e8
        unit_scale = 1e8
        
        # === Phase 1: T0/T1/T2 NAV ===
        metrics.restricted_cash_ratio, metrics.restricted_cash_warning = \
            self._check_restricted_cash(panel)
        
        t0_nav = self._calculate_t0_nav(panel)
        t1_nav = self._calculate_t1_nav(panel)
        t2_nav = self._calculate_t2_nav(panel)
        
        if t0_nav is not None:
            metrics.t0_nav_per_share = (t0_nav * unit_scale) / shares
            metrics.t0_buy_threshold = metrics.t0_nav_per_share * self.BUY_DISCOUNTS[TLevel.T0]
        if t1_nav is not None:
            metrics.t1_nav_per_share = (t1_nav * unit_scale) / shares
            metrics.t1_buy_threshold = metrics.t1_nav_per_share * self.BUY_DISCOUNTS[TLevel.T1]
        if t2_nav is not None:
            metrics.t2_nav_per_share = (t2_nav * unit_scale) / shares
            metrics.t2_buy_threshold = metrics.t2_nav_per_share * self.BUY_DISCOUNTS[TLevel.T2]
        
        if price:
            if metrics.t0_nav_per_share is not None and metrics.t0_nav_per_share > 0:
                metrics.t0_ratio = price / metrics.t0_nav_per_share
                metrics.t0_safety_margin = (metrics.t0_nav_per_share - price) / metrics.t0_nav_per_share
                metrics.is_t0_pass = price < metrics.t0_buy_threshold
            
            if metrics.t1_nav_per_share is not None and metrics.t1_nav_per_share > 0:
                metrics.t1_ratio = price / metrics.t1_nav_per_share
                metrics.t1_safety_margin = (metrics.t1_nav_per_share - price) / metrics.t1_nav_per_share
                metrics.is_t1_pass = price < metrics.t1_buy_threshold
            
            if metrics.t2_nav_per_share is not None and metrics.t2_nav_per_share > 0:
                metrics.t2_ratio = price / metrics.t2_nav_per_share
                metrics.t2_safety_margin = (metrics.t2_nav_per_share - price) / metrics.t2_nav_per_share
                metrics.is_t2_pass = price < metrics.t2_buy_threshold
            
            if metrics.is_t0_pass:
                metrics.best_t_level = "T0"
            elif metrics.is_t1_pass:
                metrics.best_t_level = "T1"
            elif metrics.is_t2_pass:
                metrics.best_t_level = "T2"
            else:
                metrics.best_t_level = "NONE"
        
        # Legacy NCAV & Liquidation
        if panel.current_assets is not None and panel.total_liabilities is not None:
            ncav = panel.current_assets - panel.total_liabilities
            metrics.ncav_per_share = (ncav * unit_scale) / shares
            if price:
                metrics.ncav_ratio = price / metrics.ncav_per_share if metrics.ncav_per_share > 0 else float('inf')
                metrics.safety_margin_ncav = (metrics.ncav_per_share - price) / metrics.ncav_per_share if metrics.ncav_per_share > 0 else None
        
        liq_value = self._calculate_liquidation_value(panel)
        if liq_value is not None:
            metrics.liquidation_value_per_share = (liq_value * unit_scale) / shares
            if price:
                metrics.liquidation_ratio = price / metrics.liquidation_value_per_share if metrics.liquidation_value_per_share > 0 else float('inf')
                metrics.safety_margin_liquidation = (metrics.liquidation_value_per_share - price) / metrics.liquidation_value_per_share if metrics.liquidation_value_per_share > 0 else None
        
        if panel.total_equity is not None:
            metrics.bvps = (panel.total_equity * unit_scale) / shares
            if price:
                metrics.pb_ratio = price / metrics.bvps if metrics.bvps > 0 else float('inf')
                metrics.safety_margin_book = (metrics.bvps - price) / metrics.bvps if metrics.bvps > 0 else None
        
        tangible_equity = self._calculate_tangible_equity(panel)
        if tangible_equity is not None:
            metrics.tangible_bvps = (tangible_equity * unit_scale) / shares
            if price:
                metrics.tangible_pb_ratio = price / metrics.tangible_bvps if metrics.tangible_bvps > 0 else float('inf')
        
        # Financial Health
        if panel.total_liabilities is not None and panel.total_equity is not None and panel.total_equity > 0:
            metrics.debt_to_equity = panel.total_liabilities / panel.total_equity
        
        if panel.current_assets is not None and panel.current_liabilities is not None and panel.current_liabilities > 0:
            metrics.current_ratio = panel.current_assets / panel.current_liabilities
        
        if panel.cash_and_equivalents is not None and panel.total_liabilities is not None and panel.total_liabilities > 0:
            metrics.cash_to_debt = panel.cash_and_equivalents / panel.total_liabilities
        
        # Earnings
        if panel.net_profit_parent is not None and panel.net_profit_parent > 0:
            eps = panel.net_profit_parent / panel.total_shares
            if price and eps > 0:
                metrics.pe_ratio = price / eps
        
        if panel.operating_cash_flow is not None:
            cf_per_share = panel.operating_cash_flow / panel.total_shares
            if price and cf_per_share > 0:
                metrics.pc_ratio = price / cf_per_share
                metrics.fcf_yield = cf_per_share / price
        
        # Asset Burn Rate
        metrics.asset_burn_rate = self._calculate_asset_burn_rate(panel, metrics)
        
        if panel.free_cash_flow is not None and panel.net_profit is not None and panel.net_profit != 0:
            metrics.fcf_conversion_rate = panel.free_cash_flow / panel.net_profit
        
        # Legacy Verdict
        metrics.is_net_net = metrics.ncav_ratio is not None and metrics.ncav_ratio < 1.0
        metrics.is_liquidation_candidate = metrics.liquidation_ratio is not None and metrics.liquidation_ratio < 1.0
        metrics.is_deep_value = (
            (metrics.pb_ratio is not None and metrics.pb_ratio < 1.0) or
            metrics.is_net_net or
            metrics.is_liquidation_candidate
        )
        
        # === Phase 2: Subtype Analysis ===
        if price:
            metrics.subtype_a = self.subtype_a_analyzer.analyze(panel, metrics, price)
            metrics.subtype_b = self.subtype_b_analyzer.analyze(panel, metrics)
            metrics.subtype_b = self.subtype_b_analyzer.calculate_discount(
                metrics.subtype_b, price, panel.total_shares)
            metrics.subtype_c = self.subtype_c_analyzer.analyze(panel, metrics, price)
            
            # Redemption path check
            metrics.redemption_path = self.redemption_checker.check(panel, metrics)
            
            # State-owned bonus (#21 raw)
            metrics.state_owned_bonus = self.so_bonus_calc.calculate(panel)
        
        # === Phase 3: Fact Check 22项 ===
        if price:
            metrics.fact_check_results = self.fact_check_engine.run(panel, metrics, price)
            metrics.fact_check_rating = self.fact_check_engine.calculate_rating(metrics.fact_check_results)
            
            # Phase 4: Bonus aggregation (#20 + #21) with final base rating
            bonus_result = self.bonus_aggregator.aggregate(
                panel, metrics, price, metrics.fact_check_rating)
            metrics.listed_subsidiary_bonus = bonus_result["listed_subsidiary_bonus_raw"]
            metrics.total_bonus = bonus_result["total_bonus"]
            metrics.bonus_adjusted_rating = bonus_result["adjusted_rating"]
            
            # Phase 5: Trading plan (entry, stop-loss, take-profit, position sizing)
            metrics.trade_plan = self.trade_engine.generate_trade_plan(panel, metrics, price)
        
        # === Risk Flags ===
        metrics.risk_flags = self._check_risk_flags(panel, metrics)
        
        # === Quality Score ===
        metrics.quality_score = self._calculate_quality_score(panel, metrics)
        
        return metrics
    
    # ==================== NAV Calculations ====================
    
    def _calculate_t0_nav(self, panel: FinancialPanel) -> Optional[float]:
        cash_pool = self._get_cash_pool(panel)
        if cash_pool is None or panel.total_liabilities is None:
            return None
        contract_liab = panel.contract_liabilities or 0
        return cash_pool + contract_liab - panel.total_liabilities
    
    def _calculate_t1_nav(self, panel: FinancialPanel) -> Optional[float]:
        cash_pool = self._get_cash_pool(panel)
        if cash_pool is None:
            return None
        interest_debt = self._get_interest_bearing_debt(panel)
        if interest_debt is None:
            return None
        contract_liab = panel.contract_liabilities or 0
        return cash_pool + contract_liab - interest_debt
    
    def _calculate_t2_nav(self, panel: FinancialPanel) -> Optional[float]:
        if panel.total_liabilities is None:
            return None
        cash_pool = self._get_cash_pool(panel) or 0
        receivables = (panel.accounts_receivable or 0) + (panel.notes_receivable or 0)
        receivables_value = receivables * 0.85
        inventory = panel.inventory or 0
        inventory_value = inventory * self.inventory_type.value
        other_current = panel.other_current_assets or 0
        other_current_value = other_current * 0.5
        prepaid = panel.prepaid_expenses or 0
        prepaid_value = prepaid * 0.0
        contract_liab = panel.contract_liabilities or 0
        total_liquid = cash_pool + receivables_value + inventory_value + other_current_value + prepaid_value
        return total_liquid - panel.total_liabilities - contract_liab
    
    def _get_cash_pool(self, panel: FinancialPanel) -> Optional[float]:
        if panel.cash_and_equivalents is None:
            return None
        return panel.cash_and_equivalents + (panel.short_term_investments or 0) + (panel.time_deposits or 0)
    
    def _get_interest_bearing_debt(self, panel: FinancialPanel) -> Optional[float]:
        # If both are None, we can't determine interest-bearing debt → return None
        # But if we have cash_pool data and at least one debt field, return sum
        # For companies with no debt at all, return 0 (this is valid info)
        has_debt_data = panel.short_term_debt is not None or panel.long_term_debt is not None
        if not has_debt_data and panel.total_liabilities is None:
            return None
        # If we have total_liabilities but no specific debt breakdown, 
        # assume interest-bearing debt = 0 (conservative for T1 calc)
        return (panel.short_term_debt or 0) + (panel.long_term_debt or 0)
    
    def _check_restricted_cash(self, panel: FinancialPanel) -> Tuple[Optional[float], str]:
        if panel.cash_and_equivalents is None or panel.cash_and_equivalents <= 0:
            return None, "PASS"
        restricted = panel.restricted_cash or 0
        ratio = restricted / panel.cash_and_equivalents
        if ratio > 0.20:
            return ratio, "VETO"
        elif ratio > 0.05:
            return ratio, "WARNING"
        else:
            return ratio, "PASS"
    
    def _calculate_asset_burn_rate(self, panel: FinancialPanel, metrics: CigarButtMetrics) -> Optional[float]:
        if panel.free_cash_flow is None:
            return None
        nav_ps = metrics.t0_nav_per_share or metrics.t1_nav_per_share or metrics.t2_nav_per_share
        if nav_ps is None or nav_ps <= 0:
            return None
        fcf_ps = panel.free_cash_flow / panel.total_shares
        return fcf_ps / nav_ps
    
    def _calculate_liquidation_value(self, panel: FinancialPanel) -> Optional[float]:
        if panel.current_assets is None or panel.total_liabilities is None:
            return None
        cash = panel.cash_and_equivalents or 0
        receivables = panel.accounts_receivable or 0
        inventory = panel.inventory or 0
        other_current = max(0, panel.current_assets - cash - receivables - inventory)
        liq_current = cash * 1.0 + receivables * 0.75 + inventory * 0.5 + other_current * 0.5
        liq_fixed = panel.fixed_assets * 0.2 if panel.fixed_assets else 0
        return liq_current + liq_fixed - panel.total_liabilities
    
    def _calculate_tangible_equity(self, panel: FinancialPanel) -> Optional[float]:
        if panel.total_equity is None:
            return None
        deductions = (panel.goodwill or 0) + (panel.intangible_assets or 0)
        return panel.total_equity - deductions
    
    def _check_risk_flags(self, panel: FinancialPanel, metrics: CigarButtMetrics) -> List[str]:
        flags = []
        
        if panel.net_profit is not None and panel.net_profit < 0:
            flags.append("净利润为负")
        if panel.operating_cash_flow is not None and panel.operating_cash_flow < 0:
            flags.append("经营现金流为负")
        
        if metrics.debt_to_equity is not None and metrics.debt_to_equity > 1.5:
            flags.append("负债权益比过高(>1.5)")
        if metrics.current_ratio is not None and metrics.current_ratio < 1.0:
            flags.append("流动比率<1，短期偿债压力大")
        
        if panel.cash_and_equivalents is not None and panel.short_term_debt is not None:
            if panel.cash_and_equivalents < panel.short_term_debt:
                flags.append("现金不足以覆盖短期债务")
        
        if metrics.restricted_cash_warning == "VETO":
            flags.append(f"受限现金占比过高({metrics.restricted_cash_ratio*100:.1f}%)，现金质量存疑")
        elif metrics.restricted_cash_warning == "WARNING":
            flags.append(f"受限现金占比{metrics.restricted_cash_ratio*100:.1f}%，T0/T1现金池已剔除")
        
        if metrics.best_t_level != "NONE" and metrics.asset_burn_rate is not None:
            t_level = TLevel(metrics.best_t_level)
            thresholds = self.BURN_RATE_THRESHOLDS.get(t_level, {})
            veto_line = thresholds.get("veto", -999)
            if metrics.asset_burn_rate < veto_line:
                flags.append(f"资产烧损率{metrics.asset_burn_rate*100:.1f}%低于{t_level.value}级否决线")
        
        # Redemption path warning
        if metrics.redemption_path.rating_cap == "C":
            flags.append("⚠ 价值陷阱风险：三条兑现路径（高股息/控股套利/事件驱动）均不满足核心条件")
        
        # Hold return warning
        if metrics.redemption_path.hold_return_warning:
            flags.append(f"持有回报为负：股息率({panel.dividend_yield or 0:.1f}%)低于无风险利率({metrics.redemption_path.risk_free_rate:.1f}%)")
        
        # Phase 3: Fact Check VETO items
        if metrics.fact_check_results:
            for key, item in metrics.fact_check_results.items():
                if item.status == "VETO":
                    flags.append(f"[Fact Check {item.name}] 一票否决: {item.detail}")
        
        return flags
    
    def _calculate_quality_score(self, panel: FinancialPanel, metrics: CigarButtMetrics) -> int:
        score = 50
        
        # T-level bonuses
        if metrics.is_t0_pass:
            score += 30
        elif metrics.is_t1_pass:
            score += 25
        elif metrics.is_t2_pass:
            score += 15
        elif metrics.t0_ratio is not None and metrics.t0_ratio < 1.5:
            score += 5
        
        # Subtype bonuses
        if metrics.subtype_a.is_valid:
            score += 5
        if metrics.subtype_b.is_valid:
            score += 5
        if metrics.subtype_c.is_valid:
            score += 5
        
        # Phase 4: Total bonus (#20 + #21, capped at +5)
        score += metrics.total_bonus
        
        if metrics.is_liquidation_candidate:
            score += 10
        
        if metrics.current_ratio is not None and metrics.current_ratio > 2.0:
            score += 5
        if metrics.cash_to_debt is not None and metrics.cash_to_debt > 0.5:
            score += 5
        if panel.operating_cash_flow is not None and panel.operating_cash_flow > 0:
            score += 5
        if metrics.pe_ratio is not None and metrics.pe_ratio < 10:
            score += 3
        if metrics.fcf_conversion_rate is not None and metrics.fcf_conversion_rate > 0.8:
            score += 5
        
        # Negative factors
        if metrics.risk_flags:
            score -= len(metrics.risk_flags) * 6
        if metrics.debt_to_equity is not None and metrics.debt_to_equity > 2.0:
            score -= 10
        if panel.net_profit is not None and panel.net_profit < 0:
            score -= 5
        if metrics.restricted_cash_warning == "VETO":
            score -= 20
        if metrics.redemption_path.rating_cap == "C":
            score -= 15  # No redemption path is serious
        
        # Phase 3: Fact Check rating impact
        if metrics.fact_check_rating == "D":
            score -= 30  # Any veto is extremely serious
        elif metrics.fact_check_rating == "C":
            score -= 15
        elif metrics.fact_check_rating == "B":
            score -= 5
        
        return max(0, min(100, score))

    # ==================== Report Generation ====================
    
    def generate_report(self, panel: FinancialPanel, metrics: CigarButtMetrics,
                        stock_price: float) -> str:
        """Generate v1.8 full analysis report with subtypes"""
        lines = [
            f"{'='*70}",
            f"烟蒂股深度价值分析报告（v1.8 三级NAV + 子类型判定）",
            f"标的：{panel.stock_name} ({panel.stock_code}) | 市场：{panel.market}",
            f"报告期：{panel.report_period} | 当前股价：{stock_price:.2f}元",
            f"{'='*70}",
            "",
            "【支柱一：存量资产垫 — T0/T1/T2 三级NAV检验】",
            "",
        ]
        
        def _fmt_ratio(ratio):
            return f"{ratio:.2f}" if ratio is not None else "N/A"
        
        def _fmt_margin(margin):
            return f"{(margin or 0)*100:.1f}%"
        
        # T0 Section
        if metrics.t0_nav_per_share is not None:
            lines.extend([
                f"[T0级] 净现金安全边际（最严格）",
                f"  现金池 = 货币资金({panel.cash_and_equivalents or 0:.2f}) + 短期理财({panel.short_term_investments or 0:.2f}) + 定期存款({panel.time_deposits or 0:.2f})",
                f"  合同负债加成：+{panel.contract_liabilities or 0:.2f}（视为准现金）",
                f"  减：总负债 = {panel.total_liabilities or 0:.2f}",
                f"  T0_NAV = {metrics.t0_nav_per_share:.2f}元/股 | 买入阈值（85折）= {metrics.t0_buy_threshold:.2f}元" if metrics.t0_buy_threshold else f"  T0_NAV = {metrics.t0_nav_per_share:.2f}元/股",
                f"  股价/T0_NAV = {_fmt_ratio(metrics.t0_ratio)} | 安全边际 = {_fmt_margin(metrics.t0_safety_margin)} | 通过：{'✅' if metrics.is_t0_pass else '❌'}",
                "",
            ])
        else:
            lines.append("[T0级] 数据不足\n")
        
        # T1 Section
        if metrics.t1_nav_per_share is not None:
            interest_debt = (panel.short_term_debt or 0) + (panel.long_term_debt or 0)
            lines.extend([
                f"[T1级] 现金vs有息负债（中等严格）",
                f"  现金池同上，减：有息负债 = 短借({panel.short_term_debt or 0:.2f}) + 长借({panel.long_term_debt or 0:.2f}) = {interest_debt:.2f}",
                f"  T1_NAV = {metrics.t1_nav_per_share:.2f}元/股 | 买入阈值（80折）= {metrics.t1_buy_threshold:.2f}元" if metrics.t1_buy_threshold else f"  T1_NAV = {metrics.t1_nav_per_share:.2f}元/股",
                f"  股价/T1_NAV = {_fmt_ratio(metrics.t1_ratio)} | 安全边际 = {_fmt_margin(metrics.t1_safety_margin)} | 通过：{'✅' if metrics.is_t1_pass else '❌'}",
                "",
            ])
        else:
            lines.append("[T1级] 数据不足\n")
        
        # T2 Section
        if metrics.t2_nav_per_share is not None:
            inv_discount = self.inventory_type.value
            lines.extend([
                f"[T2级] 流动资产变现（最宽松，存货折扣={inv_discount}）",
                f"  现金类×1.0 + 应收×0.85 + 存货×{inv_discount} + 其他流动资产×0.5 − 总负债 − 合同负债",
                f"  T2_NAV = {metrics.t2_nav_per_share:.2f}元/股 | 买入阈值（70折）= {metrics.t2_buy_threshold:.2f}元" if metrics.t2_buy_threshold else f"  T2_NAV = {metrics.t2_nav_per_share:.2f}元/股",
                f"  股价/T2_NAV = {_fmt_ratio(metrics.t2_ratio)} | 安全边际 = {_fmt_margin(metrics.t2_safety_margin)} | 通过：{'✅' if metrics.is_t2_pass else '❌'}",
                "",
            ])
        else:
            lines.append("[T2级] 数据不足\n")
        
        lines.extend([
            f"【最佳T级判定】{metrics.best_t_level}",
            "",
        ])
        
        if metrics.restricted_cash_ratio is not None:
            lines.extend([
                f"【受限现金检验】占比 {metrics.restricted_cash_ratio*100:.1f}% → {metrics.restricted_cash_warning}",
                "",
            ])
        
        # Pillar 2
        lines.append("【支柱二：低维持运营开支】")
        if metrics.asset_burn_rate is not None:
            lines.append(f"  资产烧损率（FCF/资产垫）= {metrics.asset_burn_rate*100:.1f}%")
        else:
            lines.append("  资产烧损率：数据不足")
        if metrics.fcf_conversion_rate is not None:
            lines.append(f"  FCF转换率（FCF/净利润）= {metrics.fcf_conversion_rate:.2f}")
        lines.append("")
        
        # ==================== Phase 2: Subtype Analysis ====================
        lines.extend([
            "【支柱三：资产兑现逻辑 — 子类型判定】",
            "",
        ])
        
        # Subtype A
        a = metrics.subtype_a
        lines.extend([
            f"[子类型A] 高股息破净型",
            f"  核心条件：",
            f"    1. 股息率 ≥ 门槛({a.dividend_yield_threshold:.1f}%)：{'✅' if a.dividend_yield_pass else '❌'} (当前{panel.dividend_yield or 0:.2f}%)",
            f"    2. PB ≤ 0.5：{'✅' if a.pb_pass else '❌'} (当前{metrics.pb_ratio or 0:.2f})",
            f"    3. 连续派息 ≥ 5年：{'✅' if a.consecutive_dividend_pass else '❌'} (当前{panel.consecutive_dividend_years or 0}年)",
            f"  安全条件：派息率<80%={'✅' if a.payout_ratio_pass else '❌'} | FCF覆盖>0.8={'✅' if a.fcf_coverage_pass else '❌'} | 有息负债率<30%={'✅' if a.interest_debt_ratio_pass else '❌'}",
            f"  股息可持续性评分：{a.sustainability_score:.0f}/10 {'(≥8强烈推荐)' if a.sustainability_score >= 8 else '(≥6可投资)' if a.sustainability_score >= 6 else '(≤5谨慎)'}",
        ])
        if a.recovery_years is not None:
            lines.append(f"  理论回收年限：{a.recovery_years:.1f}年")
        lines.append(f"  子类型A判定：{'✅ 有效兑现路径' if a.is_valid else '❌ 核心条件未全部满足'}")
        if a.warnings:
            for w in a.warnings:
                lines.append(f"    ⚠ {w}")
        lines.append("")
        
        # Subtype B
        b = metrics.subtype_b
        lines.extend([
            f"[子类型B] 控股套利型（SOTP折价）",
            f"  SOTP估值 = {b.sotp_value:.2f}亿元" if b.sotp_value else "  SOTP估值：数据不足",
        ])
        if b.discount_rate is not None:
            lines.append(f"  控股折价率 = {b.discount_rate*100:.1f}% (门槛≥30%)")
        if b.coverage_ratio is not None:
            lines.append(f"  持股价值覆盖率 = {b.coverage_ratio*100:.1f}% (门槛≥30%)")
        lines.extend([
            f"  核心条件：",
            f"    1. 折价率≥30%：{'✅' if b.discount_rate_pass else '❌'}",
            f"    2. 最大子公司持股≥10%：{'✅' if b.min_holding_ratio_pass else '❌'}",
            f"    3. 覆盖率≥30%：{'✅' if b.coverage_pass else '❌'}",
            f"    4. 母公司净现金>0：{'✅' if b.parent_net_cash_pass else '❌'}",
            f"  子类型B判定：{'✅ 有效兑现路径' if b.is_valid else '❌ 核心条件未全部满足'}",
        ])
        if b.warnings:
            for w in b.warnings:
                lines.append(f"    ⚠ {w}")
        lines.append("")
        
        # Subtype C
        c = metrics.subtype_c
        lines.extend([
            f"[子类型C] 事件驱动型",
            f"  C1a(资产处置)：{'✅' if c.c1a_valid else '❌'} | C1b(股份回购)：{'✅' if c.c1b_valid else '❌'} | C1c(清算/私有化)：{'✅' if c.c1c_valid else '❌'} | C2(政策修复)：{'✅' if c.c2_valid else '❌'} (评分{c.c2_score:.0f}/10)",
            f"  事件概率：{c.event_probability}" if c.event_probability else "",
            f"  子类型C判定：{'✅ 有效兑现路径 (' + c.subtype + ')' if c.is_valid else '❌ 无有效事件催化剂'}",
        ])
        if c.warnings:
            for w in c.warnings:
                lines.append(f"    ⚠ {w}")
        lines.append("")
        
        # Redemption Path Check
        rp = metrics.redemption_path
        lines.extend([
            f"【兑现路径完整性检验】",
            f"  有效子类型数量：{rp.valid_path_count} 个",
            f"  有效路径：{'✅ 通过 (≥1条)' if rp.has_valid_path else '❌ 无兑现路径 — 评级上限锁定为C级'}",
        ])
        if rp.details:
            for d in rp.details:
                lines.append(f"    • {d}")
        lines.extend([
            f"  持有回报底线：股息率({panel.dividend_yield or 0:.2f}%) vs 无风险利率({rp.risk_free_rate:.1f}%)",
            f"  机会成本：{'⚠ 负回报' if rp.hold_return_warning else '✅ 可接受'}",
            "",
        ])
        
        # State-owned bonus
        if panel.is_state_owned:
            lines.extend([
                f"【国企属性加分】层级={panel.state_owned_level} | 持股={panel.state_owned_ratio or 0:.1f}% | 加分=+{metrics.state_owned_bonus}",
                "",
            ])
        
        # Legacy sections
        lines.extend([
            "【格雷厄姆经典指标（参考）】",
            f"  每股NCAV：{metrics.ncav_per_share:.2f}元" if metrics.ncav_per_share else "  NCAV：数据不足",
            f"  每股清算价值：{metrics.liquidation_value_per_share:.2f}元" if metrics.liquidation_value_per_share else "  清算价值：数据不足",
            f"  每股净资产(BVPS)：{metrics.bvps:.2f}元" if metrics.bvps else "  BVPS：数据不足",
            f"  市净率(PB)：{metrics.pb_ratio:.2f}" if metrics.pb_ratio else "  PB：数据不足",
            "",
            "【财务健康度】",
            f"  负债权益比：{metrics.debt_to_equity:.2f}" if metrics.debt_to_equity else "  负债权益比：N/A",
            f"  流动比率：{metrics.current_ratio:.2f}" if metrics.current_ratio else "  流动比率：N/A",
            f"  现金/总负债：{metrics.cash_to_debt:.2f}" if metrics.cash_to_debt else "",
            "",
            "【盈利能力】",
            f"  市盈率(PE)：{metrics.pe_ratio:.1f}" if metrics.pe_ratio else "  PE：亏损/数据不足",
            "",
            "【Phase 3: 22项Fact Check验证清单】",
            f"  基础评级: {metrics.fact_check_rating if metrics.fact_check_rating else 'N/A'}",
            "",
        ])
        
        if metrics.fact_check_results:
            for key, item in metrics.fact_check_results.items():
                status_icon = {"PASS": "✅", "WARNING": "⚠️", "VETO": "🔴"}.get(item.status, "❓")
                cat_label = f"[{item.category}]" if item.category else ""
                lines.append(f"  {status_icon} {item.name}: {item.status} {cat_label}")
                if item.detail:
                    lines.append(f"      {item.detail}")
        else:
            lines.append("  未执行Fact Check（无股价数据）")
        
        lines.extend([
            "",
            "【风险提示】",
        ])
        
        if metrics.risk_flags:
            for flag in metrics.risk_flags:
                lines.append(f"  ⚠️ {flag}")
        else:
            lines.append("  ✅ 未发现重大风险信号")
        
        lines.extend([
            "",
            "【Phase 4: 加分体系】",
            f"  加分项#20（上市子公司持股）: +{metrics.listed_subsidiary_bonus}",
            f"  加分项#21（国企层级）: +{metrics.state_owned_bonus}",
            f"  合计加分（封顶+5）: +{metrics.total_bonus}",
            f"  Fact Check基础评级: {metrics.fact_check_rating}",
            f"  加分调整后评级: {metrics.bonus_adjusted_rating}",
            "",
            "【Phase 5: 交易执行计划】",
        ])
        
        if metrics.trade_plan:
            tp = metrics.trade_plan
            ep = tp.entry
            sl = tp.stop_loss
            tf = tp.take_profit
            
            lines.extend([
                f"  [仓位管理]",
                f"    建议仓位上限: {tp.position_size_pct:.1f}% (占总资产)",
                f"    Half-Kelly参考: {tp.kelly_fraction:.1f}%",
                f"    保守仓位: {tp.details.get('conservative_position', 'N/A')}%",
                "",
                f"  [分批建仓计划]",
                f"    首次买入价: {ep.entry_price:.2f}元 (买入阈值)",
                f"    首次建仓: 目标仓位的 {ep.first_entry_ratio*100:.0f}%",
                f"    二次加仓价: {ep.add_10pct_price:.2f}元 (跌10%)",
                f"    二次加仓: 加仓至目标仓位的 80%",
                f"    满仓价: {ep.add_15pct_price:.2f}元 (跌15%)",
                f"    满仓: 建仓至目标仓位的 100%",
                "",
                f"  [止损规则]",
                f"    硬性止损价: {sl.hard_stop_price:.2f}元 (买入价再跌10%)",
            ])
            if sl.dividend_stop_triggered:
                lines.append(f"    ⚠ 股息止损: {sl.details.get('dividend_stop', '股息实质性削减')}")
            if sl.fundamental_stop_triggered:
                for key in ["fundamental_stop", "audit_stop", "mgmt_stop"]:
                    if key in sl.details:
                        lines.append(f"    ⚠ 基本面止损: {sl.details[key]}")
            if sl.subtype_stop_triggered:
                lines.append(f"    ⚠ 子类型止损: {sl.subtype_stop_reason}")
            if not any([sl.dividend_stop_triggered, sl.fundamental_stop_triggered, sl.subtype_stop_triggered]):
                lines.append(f"    ✅ 当前无额外止损触发")
            
            lines.extend([
                "",
                f"  [止盈/减仓计划]",
                f"    T0_NAV价({tf.t0_target_price or 'N/A'}): 减仓 {tf.reduce_at_t0_ratio*100:.0f}%",
                f"    T1_NAV价({tf.t1_target_price or 'N/A'}): 再减仓 {tf.reduce_at_t1_ratio*100:.0f}%",
                f"    T2_NAV价({tf.t2_target_price or 'N/A'}): 清仓 {tf.reduce_at_t2_ratio*100:.0f}%",
                f"    逻辑: 烟蒂股不应持有到完全估值修复，逐步兑现安全边际",
                "",
            ])
        else:
            lines.append("  未生成交易计划（无股价数据或不符合买入条件）")
            lines.append("")
        
        lines.extend([
            f"【综合评分】{metrics.quality_score}/100",
            f"【深度价值判定】{'✅ 是' if metrics.is_deep_value else '❌ 否'}",
            "",
            "【投资建议】",
        ])
        
        # Enhanced recommendation logic
        has_valid_path = metrics.redemption_path.has_valid_path
        
        if not has_valid_path:
            lines.append("  🔴 价值陷阱风险：T级可能通过，但无有效兑现路径（A/B/C均不满足）。")
            lines.append("     这是典型的'账面价值高但无法变现'情形，建议排除。")
        elif metrics.is_t0_pass and metrics.quality_score >= 70:
            lines.append("  🟢 强烈关注：T0级通过 + 有兑现路径 + 财务健康。优先配置，仓位上限10%。")
        elif metrics.is_t0_pass:
            lines.append("  🟡 T0级通过但质量评分一般，建议深入研究受限现金和资产质量后再决策。")
        elif metrics.is_t1_pass and metrics.quality_score >= 60:
            lines.append("  🟢 关注：T1级通过 + 有兑现路径。中高安全边际，仓位上限8%。")
        elif metrics.is_t1_pass:
            lines.append("  🟡 T1级通过但存在财务瑕疵，需权衡风险收益比。")
        elif metrics.is_t2_pass and metrics.quality_score >= 60:
            lines.append("  🟡 适度关注：T2级通过 + 有兑现路径。不确定性较高，仓位上限5%。")
        elif metrics.is_t2_pass:
            lines.append("  🔴 谨慎对待：T2级通过但财务风险较高，安全边际有限。")
        else:
            lines.append("  ❌ 不符合：当前股价未达任何T级买入阈值，不满足烟蒂股安全标准。")
            if metrics.t0_buy_threshold:
                lines.append(f"     参考：股价需跌至 {metrics.t0_buy_threshold:.2f}元以下才满足T0买入条件")
        
        lines.append(f"{'='*70}")
        
        return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Cigar Butt Stock Analyzer v1.8 - Generate deep value analysis report")
    parser.add_argument("--panel", required=True, help="Path to financial panel JSON")
    parser.add_argument("--price", type=float, required=True, help="Current stock price")
    parser.add_argument("--inventory-type", choices=[t.name for t in InventoryType],
                        default="DEFAULT", help="Inventory discount type")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory for reports (default: same dir as panel JSON)")
    args = parser.parse_args()
    
    with open(args.panel, "r", encoding="utf-8") as f:
        data = json.load(f)
    panel = FinancialPanel(**data)
    
    inv_type = InventoryType[args.inventory_type]
    analyzer = CigarButtAnalyzer(inventory_type=inv_type)
    metrics = analyzer.analyze(panel, args.price)
    report = analyzer.generate_report(panel, metrics, args.price)
    
    try:
        print(report)
    except UnicodeEncodeError:
        print("[Report contains Unicode characters not supported by this terminal.")
        print(" Please view the saved .md or .html file below.]")
    
    # Determine output directory
    output_dir = Path(args.output_dir) if args.output_dir else Path(args.panel).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save metrics JSON
    metrics_path = output_dir / f"{panel.stock_code}_cigarbutt_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        def serialize(obj):
            if isinstance(obj, (SubTypeAResult, SubTypeBResult, SubTypeCResult, RedemptionPathResult,
                                 CigarButtMetrics, FactCheckItem, TradePlanResult, EntryPlan,
                                 StopLossRule, TakeProfitPlan)):
                return obj.__dict__
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        json.dump(metrics.__dict__, f, ensure_ascii=False, indent=2, default=serialize)
    print(f"\nMetrics JSON saved to {metrics_path}")
    
    # Export reports (.md + .html)
    try:
        from utils.report_exporter import export_md, export_html
        
        md_path = output_dir / f"{panel.stock_code}_report.md"
        export_md(report, md_path)
        print(f"Markdown report saved to {md_path}")
        
        html_path = output_dir / f"{panel.stock_code}_report.html"
        export_html(report, html_path, title=f"{panel.stock_code} {panel.stock_name} 烟蒂股分析报告")
        print(f"HTML report saved to {html_path}")
        
    except ImportError as e:
        print(f"Report export skipped (missing dependencies): {e}")


if __name__ == "__main__":
    main()
