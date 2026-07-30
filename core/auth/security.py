"""
JWT-based session tokens.

Any client (Telegram bot, future web app, whatever) authenticates through
the same core/auth logic and gets back the same kind of token. The token
itself doesn't know or care which channel it came from - it just certifies
"this is User #7" for a limited time.
"""

import os
from datetime import datetime, timedelta, timezone

from jose import jwt

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

if SECRET_KEY == "dev-secret-change-me":
    print("WARNING: using default JWT_SECRET_KEY - set a real one before deploying.")


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """Returns the user_id encoded in the token. Raises jose.JWTError if invalid/expired."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return int(payload["sub"])