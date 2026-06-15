# src/modules/users/router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from src.core.auth import get_current_user
from src.core.database import get_db
from src.modules.users.model import User
from src.modules.users import service, schemas

router = APIRouter()


@router.post("/register", response_model=schemas.UserCreateResponse)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    return service.create_user(db, user)


@router.get("/{user_uuid}", response_model=schemas.UserCreateResponse)
def get_user_by_uuid(
    user_uuid: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    user = service.get_user_by_uuid(db, user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.get("", response_model=list[schemas.UserCreateResponse])
def list_users(
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return service.list_users(db, search=search, skip=skip, limit=limit)


@router.patch("/{user_uuid}", response_model=schemas.UserCreateResponse)
def update_user(
    user_uuid: UUID,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.uuid != user_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own account",
        )

    user = service.get_user_by_uuid(db, user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return service.update_user(db, user, payload)
