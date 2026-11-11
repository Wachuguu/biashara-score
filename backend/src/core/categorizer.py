"""
Transaction Categorizer (Rule-Based + Bedrock Fallback Interface)
Pure Python business logic.
"""
from typing import Optional, Callable
from .models import Transaction, TransactionCategory


def categorize_transaction(
    tx: Transaction,
    llm_fallback_fn: Optional[Callable[[Transaction], TransactionCategory]] = None,
) -> Transaction:
    """
    Categorizes a transaction into:
    - SALES
    - INVENTORY
    - UTILITIES
    - RENT
    - DEBT_RECOVERY
    - OWNER_DRAW
    - AIRTIME

    Strategy:
    1. Try fast local regex / dictionary keyword match.
    2. If match is ambiguous and llm_fallback_fn is provided, invoke LLM fallback.
    """
    raise NotImplementedError("Dev 1: Implement rule-based categorization in Sprint Phase 2")
