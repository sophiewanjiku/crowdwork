"""
Identity resolution: turning "channel X says this is external id Y" into a
real User in our system. Every client calls this same function to log
someone in - Telegram today, web/WhatsApp later.
"""

from sqlalchemy.orm import Session

from db.models import User, Identity, Wallet


def get_or_create_user(db: Session, channel: str, external_id: str, display_name: str | None = None) -> User:
    identity = (
        db.query(Identity)
        .filter(Identity.channel == channel, Identity.external_id == external_id)
        .first()
    )
    if identity:
        return identity.user

    # First time we've seen this channel/external_id - create everything a
    # new account needs: the User, the Identity linking them to this
    # channel, and an empty Wallet (every user gets exactly one).
    user = User(display_name=display_name)
    db.add(user)
    db.flush()  # assigns user.id without fully committing yet

    identity = Identity(user_id=user.id, channel=channel, external_id=external_id)
    wallet = Wallet(user_id=user.id, balance=0)
    db.add_all([identity, wallet])
    db.commit()
    db.refresh(user)
    return user