"""
Auth endpoints.

POST /auth/telegram is special: it's meant to be called by your Telegram
bot, not end users directly (the bot is the thing that knows a request
really came from a given telegram_id). That's why it requires a shared
secret header - without it, anyone could mint an account for any
telegram_id they want.
"""

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.base import get_db
from db.models import User
from core.auth.service import get_or_create_user
from core.auth.security import create_access_token
from core.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

BOT_SHARED_SECRET = os.environ.get("BOT_SHARED_SECRET", "dev-bot-secret-change-me")


class TelegramLogin(BaseModel):
    telegram_id: str
    display_name: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int


class UserOut(BaseModel):
    id: int
    display_name: str | None
    is_admin: bool

    class Config:
        from_attributes = True


@router.post("/telegram", response_model=TokenOut)
def login_via_telegram(
    login: TelegramLogin,
    db: Session = Depends(get_db),
    x_bot_secret: str = Header(...),
):
    if x_bot_secret != BOT_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid bot secret")

    user = get_or_create_user(
        db, channel="telegram", external_id=login.telegram_id, display_name=login.display_name
    )
    token = create_access_token(user.id)
    return TokenOut(access_token=token, user_id=user.id)


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user