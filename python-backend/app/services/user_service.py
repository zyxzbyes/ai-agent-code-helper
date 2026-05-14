from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User


def _normalize_username(username: str) -> str:
    return username.strip()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == _normalize_username(username)).first()


def create_user(db: Session, username: str, password: str) -> User:
    normalized_username = _normalize_username(username)
    if not normalized_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名不能为空")
    if len(password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码长度至少 6 位")
    if get_user_by_username(db, normalized_username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    user = User(username=normalized_username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = get_user_by_username(db, username)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return user


def build_auth_data(user: User) -> dict:
    return {
        "token": create_access_token(user),
        "user": {
            "id": user.id,
            "username": user.username,
        },
    }
