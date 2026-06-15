# src/modules/auth/router.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from src.core.auth import get_current_user
from src.core.database import get_db
from src.modules.users.model import User
from src.modules.auth import service, schemas

router = APIRouter()


@router.post("/login", response_model=schemas.Token)
def login(
    credentials: schemas.LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate user with email and password, return JWT token"""
    user = service.authenticate_user(db, credentials.email, credentials.password)
    access_token = service.create_user_token(user)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/logout", response_model=schemas.LogoutResponse)
def logout(
    current_user: User = Depends(get_current_user),
):
    """Logout the current authenticated user"""
    return {
        "message": f"User {current_user.email} logged out successfully",
        "status": "success",
    }
