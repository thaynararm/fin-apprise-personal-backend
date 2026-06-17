from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from src.core.auth import get_current_user
from src.core.database import get_db
from src.modules.users.model import User
from src.modules.financial_accounts import service, schemas

router = APIRouter()


# ------------------
# Financial Account Model
# ------------------


@router.get(
    "/me/summary",
    response_model=schemas.UserFinancialSummaryResponse,
)
def get_user_financial_summary_from_active_accounts(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    transaction_type: list[Literal["income", "expense", "transfer"]] | None = Query(
        default=None
    ),
    description: str | None = Query(default=None, min_length=1, max_length=255),
    category_uuids: list[UUID] | None = Query(default=None),
    account_uuids: list[UUID] | None = Query(default=None),
    is_paid: bool | None = Query(default=None),
    value_text: str | None = Query(default=None, min_length=1, max_length=32),
    merchant_name: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total, filtered = service.get_user_financial_summary_from_active_accounts(
        db,
        current_user,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        description=description,
        category_uuids=category_uuids,
        account_uuids=account_uuids,
        is_paid=is_paid,
        value_text=value_text,
        merchant_name=merchant_name,
    )

    return {
        "total": total,
        "filtered": filtered,
    }


@router.get("", response_model=list[schemas.FinancialAccountResponse])
def list_financial_accounts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_financial_accounts_by_user(
        db,
        current_user,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=schemas.FinancialAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_financial_account(
    payload: schemas.FinancialAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_financial_account(db, payload, current_user)


@router.patch(
    "/{uuid_financial_account}", response_model=schemas.FinancialAccountResponse
)
def update_financial_account(
    uuid_financial_account: UUID,
    payload: schemas.FinancialAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_account = service.get_financial_account_by_uuid(db, uuid_financial_account)
    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found",
        )

    if db_account.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own financial account",
        )

    return service.update_financial_account(db, db_account, payload)


@router.get(
    "/{uuid_financial_account}", response_model=schemas.FinancialAccountResponse
)
def get_financial_account(
    uuid_financial_account: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_account = service.get_financial_account_by_uuid(db, uuid_financial_account)
    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found",
        )

    if db_account.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own financial account",
        )

    return db_account


# ------------------
# Account Transactions Models
# ------------------


@router.get(
    "/me/movements",
    response_model=list[schemas.AccountMovementResponse],
)
def list_user_movements_from_active_accounts(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    transaction_type: list[Literal["income", "expense", "transfer"]] | None = Query(
        default=None
    ),
    description: str | None = Query(default=None, min_length=1, max_length=255),
    category_uuids: list[UUID] | None = Query(default=None),
    account_uuids: list[UUID] | None = Query(default=None),
    is_paid: bool | None = Query(default=None),
    value_text: str | None = Query(default=None, min_length=1, max_length=32),
    merchant_name: str | None = Query(default=None, min_length=1, max_length=255),
    order_by: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parsed_order_by: list[str] | None = None
    if order_by is not None and order_by.strip():
        allowed_order_fields = {
            "purchase_date",
            "category",
            "description",
            "account_name",
            "value",
        }
        parsed_order_by = []
        invalid_order_fields: list[str] = []

        for raw_field in [
            field.strip() for field in order_by.split(",") if field.strip()
        ]:
            if ":" in raw_field:
                field_name, direction = raw_field.split(":", 1)
                clean_field = field_name.strip()
                clean_direction = direction.strip().lower()

                if clean_field not in allowed_order_fields or clean_direction not in {
                    "asc",
                    "desc",
                }:
                    invalid_order_fields.append(raw_field)
                    continue

                parsed_order_by.append(
                    clean_field if clean_direction == "asc" else f"-{clean_field}"
                )
                continue

            clean_field = raw_field.lstrip("+-")
            if clean_field not in allowed_order_fields:
                invalid_order_fields.append(raw_field)
                continue

            parsed_order_by.append(raw_field)

        if invalid_order_fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Invalid order_by fields: "
                    + ", ".join(invalid_order_fields)
                    + ". Use: purchase_date, category, description, account_name, value "
                    "with +/-, or :asc/:desc (ex: purchase_date:desc)"
                ),
            )

    return service.list_user_movements_from_active_accounts(
        db,
        current_user,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        description=description,
        category_uuids=category_uuids,
        account_uuids=account_uuids,
        is_paid=is_paid,
        value_text=value_text,
        merchant_name=merchant_name,
        order_by=parsed_order_by,
    )


@router.get(
    "/{uuid_financial_account}/transactions",
    response_model=list[schemas.AccountTransactionResponse],
)
def list_account_transactions(
    uuid_financial_account: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    description: str | None = Query(default=None, min_length=1, max_length=255),
    category: str | None = Query(default=None, min_length=1, max_length=120),
    order_by: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_account = service.get_financial_account_by_uuid(db, uuid_financial_account)
    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found",
        )

    if db_account.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access transactions from your own financial account",
        )

    parsed_order_by: list[str] | None = None
    if order_by is not None and order_by.strip():
        allowed_order_fields = {
            "purchase_date",
            "category",
            "description",
            "account_name",
            "value",
        }
        parsed_order_by = []
        invalid_order_fields: list[str] = []

        for raw_field in [
            field.strip() for field in order_by.split(",") if field.strip()
        ]:
            if ":" in raw_field:
                field_name, direction = raw_field.split(":", 1)
                clean_field = field_name.strip()
                clean_direction = direction.strip().lower()

                if clean_field not in allowed_order_fields or clean_direction not in {
                    "asc",
                    "desc",
                }:
                    invalid_order_fields.append(raw_field)
                    continue

                parsed_order_by.append(
                    clean_field if clean_direction == "asc" else f"-{clean_field}"
                )
                continue

            clean_field = raw_field.lstrip("+-")
            if clean_field not in allowed_order_fields:
                invalid_order_fields.append(raw_field)
                continue

            parsed_order_by.append(raw_field)

        if invalid_order_fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Invalid order_by fields: "
                    + ", ".join(invalid_order_fields)
                    + ". Use: purchase_date, category, description, account_name, value "
                    "with +/-, or :asc/:desc (ex: purchase_date:desc)"
                ),
            )

    return service.list_account_transactions(
        db,
        db_account,
        skip=skip,
        limit=limit,
        description=description,
        category=category,
        order_by=parsed_order_by,
    )


@router.post(
    "/{uuid_financial_account}/transactions",
    response_model=schemas.AccountTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account_transaction(
    uuid_financial_account: UUID,
    payload: schemas.AccountTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Valida se a conta financeira existe e pertence ao usuário antes de criar a transação
    db_account = service.get_financial_account_by_uuid(db, uuid_financial_account)
    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found",
        )

    if db_account.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only add transactions to your own financial account",
        )

    return service.create_account_transaction(db, db_account, payload, current_user)


@router.get(
    "/{uuid_financial_account}/transactions/{transaction_uuid}",
    response_model=schemas.AccountTransactionResponse,
)
def get_account_transaction(
    uuid_financial_account: UUID,
    transaction_uuid: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_account = service.get_financial_account_by_uuid(db, uuid_financial_account)
    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found",
        )

    if db_account.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access transactions from your own financial account",
        )

    db_transaction = service.get_account_transaction_by_uuid(db, transaction_uuid)
    if not db_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    if db_transaction.id_financial_account != db_account.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found in this account",
        )

    return db_transaction


@router.put(
    "/{uuid_financial_account}/transactions/{transaction_uuid}",
    response_model=schemas.AccountTransactionResponse,
)
def update_account_transaction(
    uuid_financial_account: UUID,
    transaction_uuid: UUID,
    payload: schemas.AccountTransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_account = service.get_financial_account_by_uuid(db, uuid_financial_account)
    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found",
        )

    if db_account.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit transactions from your own financial account",
        )

    db_transaction = service.get_account_transaction_by_uuid(db, transaction_uuid)
    if not db_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    if db_transaction.id_financial_account != db_account.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found in this account",
        )

    return service.update_account_transaction(
        db,
        db_transaction,
        payload,
        current_user,
    )


@router.delete(
    "/{uuid_financial_account}/transactions/{transaction_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_account_transaction(
    uuid_financial_account: UUID,
    transaction_uuid: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_account = service.get_financial_account_by_uuid(db, uuid_financial_account)
    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found",
        )

    if db_account.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete transactions from your own financial account",
        )

    db_transaction = service.get_account_transaction_by_uuid(db, transaction_uuid)
    if not db_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    if db_transaction.id_financial_account != db_account.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found in this account",
        )

    service.delete_account_transaction(db, db_transaction)


# ------------------
# Account Transfers Models
# ------------------


@router.post(
    "/transfers",
    response_model=schemas.AccountTransferResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account_transfer(
    payload: schemas.AccountTransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_account_transfer(db, payload, current_user)


@router.put(
    "/transfers/{transfer_uuid}",
    response_model=schemas.AccountTransferResponse,
)
def update_account_transfer(
    transfer_uuid: UUID,
    payload: schemas.AccountTransferUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_transfer = service.get_account_transfer_by_uuid(db, transfer_uuid)
    if not db_transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer not found",
        )

    if db_transfer.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own transfer",
        )

    return service.update_account_transfer(db, db_transfer, payload, current_user)


@router.delete(
    "/transfers/{transfer_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_account_transfer(
    transfer_uuid: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_transfer = service.get_account_transfer_by_uuid(db, transfer_uuid)
    if not db_transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer not found",
        )

    if db_transfer.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own transfer",
        )

    service.delete_account_transfer(db, db_transfer)
