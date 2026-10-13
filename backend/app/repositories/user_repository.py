from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_by_name(db: Session, name: str) -> User | None:
    return db.execute(select(User).where(User.name == name)).scalar_one_or_none()


def get_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def create(db: Session, *, user_id: str, name: str, password_hash: str) -> User:
    user = User(user_id=user_id, name=name, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
