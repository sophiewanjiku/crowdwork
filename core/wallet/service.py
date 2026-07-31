"""
Wallet service: the only code allowed to change a wallet's balance.

Every credit or debit goes through here, and every one writes a
Transaction row first - balance is a derived cache, Transaction is the
source of truth. If you ever need to answer "why is this balance what it
is," this table has the answer.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from db.models import Wallet, Transaction, TransactionType


def credit(db: Session, wallet: Wallet, amount: Decimal, tx_type: TransactionType, reference_id: int | None = None) -> Transaction:
    if amount <= 0:
        raise ValueError("Credit amount must be positive.")

    transaction = Transaction(
        wallet_id=wallet.id,
        amount=amount,
        type=tx_type,
        reference_id=reference_id,
    )
    wallet.balance = wallet.balance + amount

    db.add(transaction)
    db.add(wallet)
    db.commit()
    db.refresh(transaction)
    return transaction


def debit(db: Session, wallet: Wallet, amount: Decimal, tx_type: TransactionType, reference_id: int | None = None) -> Transaction:
    if amount <= 0:
        raise ValueError("Debit amount must be positive.")
    if wallet.balance < amount:
        raise ValueError("Insufficient balance.")

    transaction = Transaction(
        wallet_id=wallet.id,
        amount=-amount,
        type=tx_type,
        reference_id=reference_id,
    )
    wallet.balance = wallet.balance - amount

    db.add(transaction)
    db.add(wallet)
    db.commit()
    db.refresh(transaction)
    return transaction