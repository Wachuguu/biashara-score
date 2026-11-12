"""
Weekly Financial Summary Engine (Pure Python - Zero AWS Dependencies)
Calculates weekly revenue, operating expenses, estimated net profit, and multi-week series.
Returns WeeklySummary dataclass models.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from .models import Transaction, TransactionDirection, TransactionCategory, WeeklySummary


def _parse_completion_time(time_str: str) -> Optional[datetime]:
    """Robust parser for M-Pesa CSV and ISO-8601 timestamps."""
    if not time_str:
        return None
    cleaned = time_str.strip().rstrip("Z").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def calculate_weekly_summary(
    transactions: List[Transaction],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    business_id: Optional[str] = None,
) -> WeeklySummary:
    """
    Computes weekly totals from a list of transactions:
    - gross_sales: Sum of 'IN' transactions categorized as SALES or DEBT_RECOVERY.
    - operating_expenses: Sum of 'OUT' transactions categorized as INVENTORY, UTILITIES, RENT, AIRTIME.
    - estimated_profit: gross_sales - operating_expenses.
    - profit_margin_pct: (estimated_profit / gross_sales) * 100 (0.0 if gross_sales == 0).
    - active_trading_days: Distinct calendar dates with at least 1 sales transaction.
    - expense_breakdown: Dict mapping category to total spend.
    - pulse_message: Formatted summary string ("You made KSh 14,200 this week, profit KSh 3,100.").
    Returns a WeeklySummary model instance.
    """
    start_dt = _parse_completion_time(start_date) if start_date else None
    end_dt = _parse_completion_time(end_date) if end_date else None
    if end_dt and len(end_date.strip()) <= 10:
        # If just YYYY-MM-DD, set to end of that calendar day
        end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    filtered_txs: List[Transaction] = []
    tx_datetimes: List[datetime] = []
    resolved_biz_id = business_id or ""

    for tx in transactions:
        if not resolved_biz_id and getattr(tx, "business_id", None):
            resolved_biz_id = tx.business_id

        tx_dt = _parse_completion_time(tx.completion_time)
        if tx_dt:
            if start_dt and tx_dt < start_dt:
                continue
            if end_dt and tx_dt > end_dt:
                continue
            filtered_txs.append(tx)
            tx_datetimes.append(tx_dt)
        else:
            # If no valid completion_time and no date filters, keep it
            if not start_dt and not end_dt:
                filtered_txs.append(tx)

    # Determine date boundaries & week label
    if start_date:
        resolved_start = start_date[:10]
    elif tx_datetimes:
        resolved_start = min(tx_datetimes).strftime("%Y-%m-%d")
    else:
        resolved_start = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if end_date:
        resolved_end = end_date[:10]
    elif tx_datetimes:
        resolved_end = max(tx_datetimes).strftime("%Y-%m-%d")
    else:
        resolved_end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if start_dt:
        iso_year, iso_week, _ = start_dt.isocalendar()
        week_label = f"{iso_year}-W{iso_week:02d}"
    elif tx_datetimes:
        earliest_dt = min(tx_datetimes)
        iso_year, iso_week, _ = earliest_dt.isocalendar()
        week_label = f"{iso_year}-W{iso_week:02d}"
    else:
        week_label = "N/A"

    # Sales categories: SALES and DEBT_RECOVERY (inbound revenue)
    sales_categories = {
        TransactionCategory.SALES,
        TransactionCategory.DEBT_RECOVERY,
        "SALES",
        "DEBT_RECOVERY",
    }
    # Operating expense categories: INVENTORY, UTILITIES, RENT, AIRTIME
    operating_categories = {
        TransactionCategory.INVENTORY: "INVENTORY",
        TransactionCategory.UTILITIES: "UTILITIES",
        TransactionCategory.RENT: "RENT",
        TransactionCategory.AIRTIME: "AIRTIME",
        "INVENTORY": "INVENTORY",
        "UTILITIES": "UTILITIES",
        "RENT": "RENT",
        "AIRTIME": "AIRTIME",
    }

    gross_sales = 0.0
    operating_expenses = 0.0
    active_dates = set()
    expense_breakdown: Dict[str, float] = {
        "INVENTORY": 0.0,
        "RENT": 0.0,
        "UTILITIES": 0.0,
        "AIRTIME": 0.0,
    }

    for tx in filtered_txs:
        direction = tx.direction.value if hasattr(tx.direction, "value") else tx.direction
        cat = tx.category.value if hasattr(tx.category, "value") else tx.category
        amount = float(tx.amount) if tx.amount is not None else 0.0

        if direction == TransactionDirection.IN.value or direction == "IN":
            if cat in sales_categories:
                gross_sales += amount
                tx_dt = _parse_completion_time(tx.completion_time)
                if tx_dt:
                    active_dates.add(tx_dt.strftime("%Y-%m-%d"))

        elif direction == TransactionDirection.OUT.value or direction == "OUT":
            if cat in operating_categories:
                cat_key = operating_categories[cat]
                operating_expenses += amount
                expense_breakdown[cat_key] = round(expense_breakdown[cat_key] + amount, 2)

    gross_sales = round(gross_sales, 2)
    operating_expenses = round(operating_expenses, 2)
    estimated_profit = round(gross_sales - operating_expenses, 2)

    if gross_sales > 0:
        profit_margin_pct = round((estimated_profit / gross_sales) * 100, 1)
    else:
        profit_margin_pct = 0.0

    active_trading_days = len(active_dates)
    transaction_count = len(filtered_txs)

    if estimated_profit >= 0:
        pulse_message = f"You made KSh {gross_sales:,.0f} this week, profit KSh {estimated_profit:,.0f}."
    else:
        pulse_message = f"You made KSh {gross_sales:,.0f} this week, operating deficit KSh {abs(estimated_profit):,.0f}."

    return WeeklySummary(
        business_id=resolved_biz_id,
        week_label=week_label,
        start_date=resolved_start,
        end_date=resolved_end,
        gross_sales=gross_sales,
        operating_expenses=operating_expenses,
        estimated_profit=estimated_profit,
        profit_margin_pct=profit_margin_pct,
        active_trading_days=active_trading_days,
        transaction_count=transaction_count,
        expense_breakdown=expense_breakdown,
        pulse_message=pulse_message,
    )


def calculate_multi_week_series(
    transactions: List[Transaction],
    num_weeks: int = 4,
    reference_date: Optional[str] = None,
    business_id: Optional[str] = None,
) -> List[WeeklySummary]:
    """
    Groups transactions into calendar weeks (ISO week numbering) for the trailing num_weeks.
    Returns chronological list of WeeklySummary models for trend visualization.
    """
    if num_weeks < 1:
        num_weeks = 4

    valid_times = []
    for tx in transactions:
        dt = _parse_completion_time(tx.completion_time)
        if dt:
            valid_times.append(dt)

    if reference_date:
        ref_dt = _parse_completion_time(reference_date) or datetime.now(timezone.utc).replace(tzinfo=None)
    elif valid_times:
        ref_dt = max(valid_times)
    else:
        ref_dt = datetime.now(timezone.utc).replace(tzinfo=None)

    # Find the Monday of ref_dt's ISO week
    iso_year, iso_week, _ = ref_dt.isocalendar()
    ref_monday = datetime.fromisocalendar(iso_year, iso_week, 1)

    series: List[WeeklySummary] = []

    # Generate weeks in chronological order: [W_{n-1}, ..., W_0]
    for i in range(num_weeks - 1, -1, -1):
        week_monday = ref_monday - timedelta(days=7 * i)
        week_sunday = week_monday + timedelta(days=6)
        start_str = week_monday.strftime("%Y-%m-%d")
        end_str = week_sunday.strftime("%Y-%m-%d")
        w_year, w_week, _ = week_monday.isocalendar()
        target_week_label = f"{w_year}-W{w_week:02d}"

        summary = calculate_weekly_summary(
            transactions=transactions,
            start_date=start_str,
            end_date=end_str,
            business_id=business_id,
        )
        summary.week_label = target_week_label
        summary.start_date = start_str
        summary.end_date = end_str
        series.append(summary)

    return series
