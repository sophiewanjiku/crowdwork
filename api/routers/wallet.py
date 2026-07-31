"""
Wallet endpoints - a worker checking their own balance and transaction history.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime

from sqlalchemy.orm import Session

from db.base import get_db
from db.models import User, Transaction
from core.auth.dependencies import get_current_user

router = APIRouter(prefix="/wallet", tags=["wallet"])


class TransactionOut(BaseModel):
    id: int
    amount: Decimal
    type: str
    reference_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class WalletOut(BaseModel):
    balance: Decimal
    transactions: list[TransactionOut]


@router.get("/me", response_model=WalletOut)
def my_wallet(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wallet = current_user.wallet
    transactions = (
        db.query(Transaction)
        .filter(Transaction.wallet_id == wallet.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return WalletOut(balance=wallet.balance, transactions=transactions)