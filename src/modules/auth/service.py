# src/modules/auth/service.py

from sqlalchemy.orm import Session
from src.modules.users import repository
from src.modules.users.model import User
from src.core.security import create_access_token, verify_password
from fastapi import HTTPException, status


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Authenticate user with email and password"""
    user = repository.get_user_by_email(db, email)

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def create_user_token(user: User) -> str:
    """Create JWT access token for user"""
    return create_access_token(data={"sub": str(user.uuid)})
