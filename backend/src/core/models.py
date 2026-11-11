"""
Core Data Models (Pure Python - No AWS Dependencies)
Used across parser, categorizer, score engine, and API responses.
"""
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class TransactionCategory(str, Enum):
    SALES = "SALES"
    INVENTORY = "INVENTORY"
    UTILITIES = "UTILITIES"
    RENT = "RENT"
    DEBT_RECOVERY = "DEBT_RECOVERY"
    OWNER_DRAW = "OWNER_DRAW"
    AIRTIME = "AIRTIME"
    UNCATEGORIZED = "UNCATEGORIZED"


class TransactionDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"


class DebtStatus(str, Enum):
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"
    CLEARED = "CLEARED"


@dataclass
class Transaction:
    receipt_number: str
    completion_time: str
    details: str
    amount: float
    direction: TransactionDirection
    running_balance: float
    status: str = "Completed"
    category: TransactionCategory = TransactionCategory.UNCATEGORIZED
    counterparty: Optional[str] = None
    categorization_method: str = "PENDING"
    debt_matched_id: Optional[str] = None


@dataclass
class DebtRecord:
    debt_id: str
    business_id: str
    debtor_name: str
    debtor_phone: str
    amount_owed: float
    amount_cleared: float = 0.0
    balance_remaining: float = 0.0
    status: DebtStatus = DebtStatus.UNPAID
    items_summary: str = ""
    created_at: str = ""
    due_date: str = ""
    repayment_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BiasharaScoreResult:
    business_id: str
    total_score: int  # 0 to 100
    tier: str  # e.g., 'Gold', 'Silver', 'Bronze', 'Needs Improvement'
    consistency_score: int  # max 30
    growth_score: int  # max 25
    expense_ratio_score: int  # max 25
    debt_recovery_score: int  # max 20
    weekly_turnover_avg: float
    weekly_profit_avg: float
    debt_recovery_rate: float
    computed_at: str
    actionable_tips: List[str] = field(default_factory=list)
