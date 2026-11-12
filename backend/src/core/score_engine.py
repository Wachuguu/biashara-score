"""
Biashara Score Algorithm (Pure Python - Zero AWS Dependencies)
Evaluates 4 pillars (0 - 100):
1. Income Consistency & Frequency (30 pts)
2. Revenue Volume & Growth (25 pts)
3. Operating Margin & Expense Ratio (25 pts)
4. Debt Recovery Discipline (20 pts)
"""
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from .models import (
    Transaction,
    DebtRecord,
    DebtStatus,
    TransactionDirection,
    TransactionCategory,
    WeeklySummary,
    BiasharaScoreResult,
)
from .summary import calculate_multi_week_series, _parse_completion_time


def _get_summary_val(summary: Union[WeeklySummary, Dict[str, Any]], key: str, default: Any = 0.0) -> Any:
    """Helper to extract attribute from WeeklySummary dataclass or dict."""
    if hasattr(summary, key):
        return getattr(summary, key)
    elif isinstance(summary, dict):
        return summary.get(key, default)
    return default


def compute_consistency_score(transactions: List[Transaction]) -> int:
    """
    Pillar 1 (Max 30 pts): Income Consistency & Frequency.
    Evaluates:
    - Trading days per week (>5 days/week = full points).
    - Regularity of daily deposits.
    """
    if not transactions:
        return 0

    sales_categories = {
        TransactionCategory.SALES,
        TransactionCategory.DEBT_RECOVERY,
        "SALES",
        "DEBT_RECOVERY",
    }

    sales_txs: List[Transaction] = []
    tx_dates: List[datetime] = []
    active_dates = set()

    for tx in transactions:
        direction = tx.direction.value if hasattr(tx.direction, "value") else tx.direction
        cat = tx.category.value if hasattr(tx.category, "value") else tx.category

        dt = _parse_completion_time(tx.completion_time)
        if dt:
            tx_dates.append(dt)

        if (direction == TransactionDirection.IN.value or direction == "IN") and cat in sales_categories:
            sales_txs.append(tx)
            if dt:
                active_dates.add(dt.strftime("%Y-%m-%d"))

    if not sales_txs or not tx_dates:
        return 0

    min_date = min(tx_dates).date()
    max_date = max(tx_dates).date()
    span_days = max(1, (max_date - min_date).days + 1)
    span_weeks = max(1.0, span_days / 7.0)

    # Trading days per week (up to 20 pts)
    trading_days_per_week = len(active_dates) / span_weeks
    if trading_days_per_week >= 5.5:
        frequency_pts = 20
    elif trading_days_per_week >= 4.5:
        frequency_pts = 17
    elif trading_days_per_week >= 3.5:
        frequency_pts = 13
    elif trading_days_per_week >= 2.5:
        frequency_pts = 9
    elif trading_days_per_week >= 1.0:
        frequency_pts = 5
    else:
        frequency_pts = 2

    # Regularity of daily deposits (up to 10 pts)
    tx_per_day = len(sales_txs) / max(1, len(active_dates))
    if tx_per_day >= 4.0:
        regularity_pts = 10
    elif tx_per_day >= 2.5:
        regularity_pts = 8
    elif tx_per_day >= 1.5:
        regularity_pts = 6
    else:
        regularity_pts = 4

    return min(30, max(0, frequency_pts + regularity_pts))


def compute_growth_score(weekly_summaries: List[Union[WeeklySummary, Dict[str, Any]]]) -> int:
    """
    Pillar 2 (Max 25 pts): Revenue Volume & Growth.
    Evaluates:
    - Average monthly turnover (>KSh 40,000 for typical duka).
    - Week-over-week growth trajectory.
    """
    if not weekly_summaries:
        return 0

    total_sales = sum(_get_summary_val(s, "gross_sales", 0.0) for s in weekly_summaries)
    if total_sales <= 0:
        return 0

    # Consider only weeks with sales or all weeks in the trailing window
    weeks_with_sales = [s for s in weekly_summaries if _get_summary_val(s, "gross_sales", 0.0) > 0]
    eval_count = len(weekly_summaries)

    avg_weekly_sales = total_sales / max(1, eval_count)
    monthly_turnover = avg_weekly_sales * 4.0

    # Volume points (max 15 pts)
    if monthly_turnover >= 60000:
        volume_pts = 15
    elif monthly_turnover >= 40000:
        volume_pts = 13
    elif monthly_turnover >= 25000:
        volume_pts = 10
    elif monthly_turnover >= 15000:
        volume_pts = 7
    elif monthly_turnover >= 5000:
        volume_pts = 4
    else:
        volume_pts = 1

    # Growth trajectory points (max 10 pts)
    # If only one week with data, assign neutral baseline (6 pts)
    if len(weeks_with_sales) <= 1:
        trajectory_pts = 6
    elif len(weekly_summaries) >= 2:
        midpoint = len(weekly_summaries) // 2
        first_half = weekly_summaries[:midpoint]
        second_half = weekly_summaries[midpoint:]

        s1 = sum(_get_summary_val(s, "gross_sales", 0.0) for s in first_half) / max(1, len(first_half))
        s2 = sum(_get_summary_val(s, "gross_sales", 0.0) for s in second_half) / max(1, len(second_half))

        if s1 > 0:
            growth_rate = (s2 - s1) / s1
            if growth_rate >= 0.10:
                trajectory_pts = 10
            elif growth_rate >= 0.0:
                trajectory_pts = 7
            elif growth_rate >= -0.10:
                trajectory_pts = 5
            else:
                trajectory_pts = 2
        else:
            trajectory_pts = 7 if s2 > 0 else 0
    else:
        trajectory_pts = 6

    return min(25, max(0, volume_pts + trajectory_pts))


def compute_margin_score(weekly_summaries: List[Union[WeeklySummary, Dict[str, Any]]]) -> int:
    """
    Pillar 3 (Max 25 pts): Operating Margin & Expense Ratio.
    Evaluates net operating margin: (Sales - Operating Expenses) / Sales.
    - 15% to 35% margin = 25 pts.
    - 5% to 14% margin = 15 pts.
    - Negative margin = 0 pts.
    """
    if not weekly_summaries:
        return 0

    total_sales = sum(_get_summary_val(s, "gross_sales", 0.0) for s in weekly_summaries)
    total_expenses = sum(_get_summary_val(s, "operating_expenses", 0.0) for s in weekly_summaries)

    if total_sales <= 0:
        return 0

    margin_pct = ((total_sales - total_expenses) / total_sales) * 100.0

    if margin_pct < 0.0:
        return 0
    elif 15.0 <= margin_pct <= 35.0:
        return 25
    elif margin_pct > 35.0:
        return 22
    elif 5.0 <= margin_pct < 15.0:
        return 15
    elif 0.0 <= margin_pct < 5.0:
        return 8
    else:
        return 0


def compute_debt_recovery_score(debts: List[DebtRecord]) -> int:
    """
    Pillar 4 (Max 20 pts): Debt Discipline & Recovery.
    Evaluates:
    - Total recovered / total credit extended (>80% recovery = full points).
    - Presence of delinquent debts older than 30 days.
    - If no debts extended (zero credit shop), returns 15/20 neutral baseline.
    """
    if not debts:
        return 15

    total_owed = sum(float(d.amount_owed) for d in debts)
    if total_owed <= 0:
        return 15

    total_cleared = sum(float(d.amount_cleared) for d in debts)
    recovery_rate = total_cleared / total_owed

    if recovery_rate >= 0.80:
        base_score = 20
    elif recovery_rate >= 0.65:
        base_score = 17
    elif recovery_rate >= 0.50:
        base_score = 14
    elif recovery_rate >= 0.35:
        base_score = 10
    elif recovery_rate >= 0.15:
        base_score = 6
    elif recovery_rate > 0.0:
        base_score = 3
    else:
        base_score = 1  # 0% recovered

    # Check for delinquent debts (>30 days overdue or created >30 days ago and not cleared)
    delinquent_count = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for d in debts:
        status_val = d.status.value if hasattr(d.status, "value") else d.status
        is_cleared = (status_val == DebtStatus.CLEARED.value or status_val == "CLEARED" or d.balance_remaining <= 0)
        if not is_cleared:
            ref_str = d.due_date or d.created_at
            ref_dt = _parse_completion_time(ref_str)
            if ref_dt and (now - ref_dt).days > 30:
                delinquent_count += 1

    deduction = min(6, delinquent_count * 2)
    return min(20, max(0, base_score - deduction))


def generate_actionable_tips(
    consistency: int,
    growth: int,
    margin: int,
    debt: int,
    debts: List[DebtRecord],
) -> List[str]:
    """
    Produces 2-4 concrete, contextual tips in plain Kenyan English to help the shopkeeper improve their score.
    """
    tips: List[str] = []

    unpaid_debts = [d for d in debts if (d.status != DebtStatus.CLEARED and d.status != "CLEARED" and d.balance_remaining > 0)]
    unpaid_count = len(unpaid_debts)

    if debt < 18:
        if unpaid_count > 0:
            tips.append(
                f"Follow up with {unpaid_count} customer(s) with pending debts to boost your Debt Recovery pillar to Gold tier."
            )
        else:
            tips.append(
                "Encourage prompt customer settlements within 14 days to maximize your Debt Recovery score."
            )

    if consistency < 26:
        tips.append(
            "Maintain active customer deposits on weekends to achieve full marks on Cashflow Consistency."
        )

    if margin < 22:
        tips.append(
            "Keep operating expenses under 75% of gross sales to improve your net operating profit margin."
        )

    if growth < 20:
        tips.append(
            "Increase weekly turnover toward KSh 40,000 by stocking fast-moving household essentials (unga, milk, cooking oil)."
        )

    # Ensure at least 2 tips are returned
    if len(tips) < 2:
        tips.append(
            "Maintain daily sales recording via M-Pesa to preserve your Gold tier standing with lenders."
        )
    if len(tips) < 2:
        tips.append(
            "Consider negotiating bulk supplier discounts with key distributors to further optimize operating margins."
        )

    return tips[:4]


def calculate_biashara_score(
    business_id: str,
    transactions: List[Transaction],
    debts: List[DebtRecord],
) -> BiasharaScoreResult:
    """
    Computes total score (0 to 100) = consistency + growth + margin + debt.
    Assigns tier ('Gold', 'Silver', 'Bronze', 'Needs Improvement').
    """
    weekly_summaries = calculate_multi_week_series(transactions)

    consistency_score = compute_consistency_score(transactions)
    growth_score = compute_growth_score(weekly_summaries)
    expense_ratio_score = compute_margin_score(weekly_summaries)
    debt_recovery_score = compute_debt_recovery_score(debts)

    total_score = consistency_score + growth_score + expense_ratio_score + debt_recovery_score
    total_score = min(100, max(0, total_score))

    if total_score >= 80:
        tier = "Gold"
    elif total_score >= 65:
        tier = "Silver"
    elif total_score >= 50:
        tier = "Bronze"
    else:
        tier = "Needs Improvement"

    if weekly_summaries:
        weekly_turnover_avg = round(
            sum(_get_summary_val(s, "gross_sales", 0.0) for s in weekly_summaries) / len(weekly_summaries), 2
        )
        weekly_profit_avg = round(
            sum(_get_summary_val(s, "estimated_profit", 0.0) for s in weekly_summaries) / len(weekly_summaries), 2
        )
    else:
        weekly_turnover_avg = 0.0
        weekly_profit_avg = 0.0

    total_owed = sum(float(d.amount_owed) for d in debts)
    total_cleared = sum(float(d.amount_cleared) for d in debts)
    if total_owed > 0:
        debt_recovery_rate = round((total_cleared / total_owed) * 100.0, 1)
    else:
        debt_recovery_rate = 100.0 if not debts else 0.0

    computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    tips = generate_actionable_tips(
        consistency=consistency_score,
        growth=growth_score,
        margin=expense_ratio_score,
        debt=debt_recovery_score,
        debts=debts,
    )

    return BiasharaScoreResult(
        business_id=business_id,
        total_score=total_score,
        tier=tier,
        consistency_score=consistency_score,
        growth_score=growth_score,
        expense_ratio_score=expense_ratio_score,
        debt_recovery_score=debt_recovery_score,
        weekly_turnover_avg=weekly_turnover_avg,
        weekly_profit_avg=weekly_profit_avg,
        debt_recovery_rate=debt_recovery_rate,
        computed_at=computed_at,
        actionable_tips=tips,
    )
