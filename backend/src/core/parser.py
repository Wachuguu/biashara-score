"""
M-Pesa Statement & SMS Parser (Pure Python)
No AWS dependencies. Can be executed and tested locally on any machine.
"""
from typing import List
from .models import Transaction


def parse_csv_statement(csv_content: str) -> List[Transaction]:
    """
    Parses a raw Safaricom M-Pesa CSV statement string into a list of Transaction models.
    Handles standard M-Pesa CSV headers:
    ['Receipt No.', 'Completion Time', 'Details', 'Transaction Status', 'Paid In', 'Withdrawn', 'Balance']
    """
    raise NotImplementedError("Dev 1: Implement CSV parsing logic in Sprint Phase 2")


def parse_sms_message(sms_text: str) -> Transaction:
    """
    Parses an incoming M-Pesa SMS message string into a Transaction model.
    Example: 'SK01YUUM7K Confirmed. You have received Ksh1,600.00 from John Otieno 254731829405 on 1/9/26 at 12:49 PM...'
    """
    raise NotImplementedError("Dev 1: Implement SMS regex parsing logic in Sprint Phase 2")
