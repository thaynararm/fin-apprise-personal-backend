from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from src.core.auth import get_current_user
from src.core.database import get_db
from src.modules.users.model import User
from src.modules.loan_recipients import service, schemas

router = APIRouter()


@router.get("", response_model=list[schemas.LoanRecipientResponse])
def list_loan_recipients(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_loan_recipients_by_user(
        db, current_user, skip=skip, limit=limit
    )


@router.post(
    "",
    response_model=schemas.LoanRecipientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_loan_recipient(
    payload: schemas.LoanRecipientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_loan_recipient(db, current_user, payload)


@router.get("/{recipient_uuid}", response_model=schemas.LoanRecipientResponse)
def get_loan_recipient(
    recipient_uuid: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_loan_recipient_by_uuid(db, current_user, recipient_uuid)


@router.patch(
    "/{recipient_uuid}",
    response_model=schemas.LoanRecipientResponse,
)
def update_loan_recipient(
    recipient_uuid: UUID,
    payload: schemas.LoanRecipientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.update_loan_recipient(db, current_user, recipient_uuid, payload)


@router.delete("/{recipient_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loan_recipient(
    recipient_uuid: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_loan_recipient(db, current_user, recipient_uuid)
