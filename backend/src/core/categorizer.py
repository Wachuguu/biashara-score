"""
Transaction Categorizer (Rule-Based + Bedrock Fallback Interface)
Pure Python business logic. Zero AWS dependencies.
"""
import re
from enum import Enum
from typing import Optional, Callable, List, Any, Union
from .models import Transaction, TransactionCategory, TransactionDirection


def match_rule_based_category(details: str, direction: str) -> Optional[TransactionCategory]:
    """
    Pure regex & keyword dictionary matcher against Kenyan commercial keywords:
    - SALES: Till receipts, Paybill inbound, customer deposits.
    - INVENTORY: Brookside, Pembe, Unga, Bidco, Kapa, Farmer's Choice, Devki, wholesale depots.
    - UTILITIES: KPLC PREPAID, Nairobi Water (NWSC), WiFi, internet.
    - RENT: Landlord transfers, shop rent keywords.
    - OWNER_DRAW: 'Personal Draw', transfers to owner's private numbers.
    - AIRTIME: Airtime Purchase, Safaricom data bundles.
    - DEBT_RECOVERY: 'debt repayment', 'deni', 'debt settled', 'credit pay', 'loan cleared'.
    Returns None if no rule matches with high confidence.
    """
    if not details:
        return None

    d = details.strip().lower()
    dir_clean = direction.upper().strip() if direction else ""

    # 1. DEBT_RECOVERY (Highest precedence: customer debt settlements and repayments)
    debt_patterns = [
        r"\bdebt\b",
        r"\bdeni\b",
        r"\bsettled\b",
        r"\bcleared\b",
        r"\bduka\s+loan\b",
        r"\bcredit\s+pay\b",
        r"\bcredit\s+payment\b",
        r"\bdebt\s+clearance\b",
        r"\bloan\s+cleared\b",
        r"\brepayment\b",
    ]
    if any(re.search(pat, d) for pat in debt_patterns):
        return TransactionCategory.DEBT_RECOVERY

    # 2. INBOUND TILL / RETAIL PAYMENTS (Rule: Inbound to Till is always SALES unless debt recovery)
    # Prevents counterparty names like "Farmer's Choice" or "Grace Airtime" paying the till from triggering wrong category
    if dir_clean == "IN":
        till_inbound_patterns = [
            r"\btill\b",
            r"\bpayment\s+to\s+till\b",
            r"\btill\s+payment\b",
            r"\bcustomer\s+payment\b",
            r"\breceived\b",
            r"\bsukuma\s+wiki\b",
            r"\bcash\s+sale\b",
            r"\bpayment\s+from\b",
        ]
        if any(re.search(pat, d) for pat in till_inbound_patterns):
            return TransactionCategory.SALES

    # 3. RENT
    rent_patterns = [
        r"\brent\b",
        r"\blandlord\b",
        r"\bduka\s+rent\b",
        r"\bshop\s+rent\b",
        r"\bhouse\s+rent\b",
    ]
    if any(re.search(pat, d) for pat in rent_patterns):
        return TransactionCategory.RENT

    # 4. UTILITIES
    utility_patterns = [
        r"\bkplc\b",
        r"\bkplc\s+prepaid\b",
        r"\bnairobi\s+(?:city\s+)?water\b",
        r"\bnwsc\b",
        r"\bsewerage\b",
        r"\bwater\s+and\s+sewerage\b",
        r"\bwifi\b",
        r"\binternet\b",
        r"\btokens?\b",
        r"\belectricity\b",
        r"\bpower\b",
    ]
    if any(re.search(pat, d) for pat in utility_patterns):
        return TransactionCategory.UTILITIES

    # 5. AIRTIME (Only purchase/bundles, or OUT transactions with 'airtime')
    airtime_patterns = [
        r"\bairtime\s+purchase\b",
        r"\bairtime\s+bought\b",
        r"\bbought\b.*\bairtime\b",
        r"\bof\s+airtime\b",
        r"\bsafaricom\s+airtime\b",
        r"\bdata\s+bundles?\b",
        r"\binternet\s+bundles?\b",
    ]
    if any(re.search(pat, d) for pat in airtime_patterns) or (dir_clean == "OUT" and re.search(r"\bairtime\b", d)):
        return TransactionCategory.AIRTIME

    # 6. OWNER_DRAW
    owner_patterns = [
        r"\bpersonal\s+draw\b",
        r"\bowner\s+draw\b",
        r"\bsent\s+to\s+self\b",
        r"\btransfer\s+to\s+self\b",
        r"\bpersonal\s+withdrawal\b",
        r"\bself\s*/\s*personal\b",
    ]
    if any(re.search(pat, d) for pat in owner_patterns):
        return TransactionCategory.OWNER_DRAW

    # 7. INVENTORY (Supplier / wholesale goods purchases)
    inventory_patterns = [
        r"\bbrookside\b",
        r"\bpembe\b",
        r"\bunga\b",
        r"\bbidco\b",
        r"\bkapa\b",
        r"\bfarmer'?s\s+choice\b",
        r"\bdevki\b",
        r"\bkevian\b",
        r"\bwholesale\b",
        r"\bdistributors?\b",
        r"\bflour\s+mills?\b",
        r"\bsupplies\b",
        r"\bdairies\b",
        r"\bbakeries\b",
        r"\boil\s+refineries\b",
        r"\bdepot\b",
        r"\bfarm\s+care\b",
        r"\bbutchery\b",
        r"\bcereals?\b",
        r"\bbeverages?\b",
        r"\bbread\b",
    ]
    if any(re.search(pat, d) for pat in inventory_patterns):
        return TransactionCategory.INVENTORY

    # 8. GENERAL SALES (Fallback for any remaining inbound transactions)
    if dir_clean == "IN":
        return TransactionCategory.SALES

    return None


def categorize_transaction(
    tx: Transaction,
    llm_fallback_fn: Optional[Union[Callable[[str, str, float], Any], Callable[[Transaction], Any]]] = None,
) -> Transaction:
    """
    Categorizes a transaction.
    1. Runs match_rule_based_category. Sets categorization_method = 'RULE_BASED' on match.
    2. If unmatched and llm_fallback_fn is provided, invokes fallback and sets categorization_method = 'BEDROCK_HAIKU'.
    3. If still unmatched, assigns TransactionCategory.UNCATEGORIZED.
    """
    dir_str = tx.direction.value if isinstance(tx.direction, Enum) else str(tx.direction)
    rule_category = match_rule_based_category(tx.details, dir_str)

    if rule_category is not None:
        tx.category = rule_category
        tx.categorization_method = "RULE_BASED"
        return tx

    # Step 2: Bedrock LLM Fallback
    if llm_fallback_fn is not None:
        try:
            try:
                result = llm_fallback_fn(tx.details, dir_str, tx.amount)
            except TypeError:
                result = llm_fallback_fn(tx)

            cat_str = None
            if isinstance(result, dict):
                cat_str = result.get("category")
            elif isinstance(result, str):
                cat_str = result
            elif hasattr(result, "value"):
                cat_str = str(result.value)

            if cat_str:
                clean_cat = cat_str.upper().strip()
                try:
                    tx.category = TransactionCategory(clean_cat)
                except ValueError:
                    tx.category = TransactionCategory.UNCATEGORIZED
                tx.categorization_method = "BEDROCK_HAIKU"
                return tx
        except Exception:
            pass

    # Step 3: Default Uncategorized
    tx.category = TransactionCategory.UNCATEGORIZED
    tx.categorization_method = "UNMATCHED"
    return tx


def categorize_batch(
    transactions: List[Transaction],
    llm_fallback_fn: Optional[Union[Callable[[str, str, float], Any], Callable[[Transaction], Any]]] = None,
) -> List[Transaction]:
    """
    Applies categorization across a list of transactions efficiently.
    """
    return [categorize_transaction(tx, llm_fallback_fn=llm_fallback_fn) for tx in transactions]
