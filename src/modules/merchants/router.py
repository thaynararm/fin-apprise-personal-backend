from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from src.core.auth import get_current_user
from src.core.database import get_db
from src.modules.users.model import User
from src.modules.merchants import service, schemas

router = APIRouter()


@router.get("", response_model=list[schemas.MerchantNameResponse])
def list_merchants(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_merchants_by_user(db, current_user, skip=skip, limit=limit)


@router.post(
    "",
    response_model=schemas.MerchantNameResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_merchant(
    payload: schemas.MerchantNameCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_merchant(db, current_user, payload)


@router.get("/{merchant_uuid}", response_model=schemas.MerchantNameResponse)
def get_merchant(
    merchant_uuid: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_merchant_by_uuid(db, current_user, merchant_uuid)


@router.patch(
    "/{merchant_uuid}",
    response_model=schemas.MerchantNameResponse,
)
def update_merchant(
    merchant_uuid: UUID,
    payload: schemas.MerchantNameUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.update_merchant(db, current_user, merchant_uuid, payload)


@router.delete("/{merchant_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_merchant(
    merchant_uuid: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_merchant(db, current_user, merchant_uuid)
