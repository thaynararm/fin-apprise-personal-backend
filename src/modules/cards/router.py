from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from src.core.auth import get_current_user
from src.core.database import get_db
from src.modules.users.model import User
from src.modules.cards import service, schemas

router = APIRouter()


# ------------------
# Cards Model
# ------------------

@router.get("/{card_uuid}", response_model=schemas.CardResponse)
def get_card(
    card_uuid: UUID,
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=1900, le=9999),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_card = service.get_card_by_uuid(db, card_uuid)
    if not db_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    if db_card.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own cards",
        )

    # Populate current_invoice and available_limit if month is provided
    if month is not None:
        current_invoice = service.get_card_invoice_amount(db_card, month, year)
        db_card.current_invoice = current_invoice
        db_card.available_limit = service._get_available_limit(db_card)

    return db_card


@router.post(
    "",
    response_model=schemas.CardResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_card(
    payload: schemas.CardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_card(db, payload, current_user)


@router.patch("/{card_uuid}", response_model=schemas.CardResponse)
def update_card(
    card_uuid: UUID,
    payload: schemas.CardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_card = service.get_card_by_uuid(db, card_uuid)
    if not db_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    if db_card.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own card",
        )

    return service.update_card(db, db_card, payload)


@router.get("", response_model=list[schemas.CardResponse])
def list_cards(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=1900, le=9999),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cards = service.list_cards_by_user(db, current_user, skip=skip, limit=limit)

    if month is not None:
        for card in cards:
            current_invoice = service.get_card_invoice_amount(card, month, year)
            card.current_invoice = current_invoice
            card.available_limit = service._get_available_limit(card)

    return cards



# ------------------
# Card Transactions Model
# ------------------

@router.get(
    "/installments/by-reference-month",
    response_model=list[schemas.CardInstallmentByMonthResponse],
)
def list_installments_by_reference_month(
    month: int = Query(..., ge=1, le=12),
    year: int | None = Query(default=None, ge=1900, le=9999),
    purchase_date_start: date | None = Query(default=None),
    purchase_date_end: date | None = Query(default=None),
    description: str | None = Query(default=None, min_length=1, max_length=255),
    category: str | None = Query(default=None, min_length=1, max_length=120),
    card_uuid: list[UUID] | None = Query(default=None),
    value_text: str | None = Query(default=None, min_length=1, max_length=32),
    order_by: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if (
        purchase_date_start is not None
        and purchase_date_end is not None
        and purchase_date_start > purchase_date_end
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="purchase_date_start cannot be greater than purchase_date_end",
        )

    parsed_order_by: list[str] | None = None
    if order_by is not None and order_by.strip():
        allowed_order_fields = {
            "purchase_date",
            "category",
            "description",
            "card_name",
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
                    + ". Use: purchase_date, category, description, card_name, value "
                    "with +/-, or :asc/:desc (ex: purchase_date:desc)"
                ),
            )

    installments = service.list_card_installments_by_reference_month(
        db,
        current_user,
        month=month,
        year=year,
        purchase_date_start=purchase_date_start,
        purchase_date_end=purchase_date_end,
        description=description,
        category=category,
        card_uuid=card_uuid,
        value_text=value_text,
        order_by=parsed_order_by,
    )

    return [
        {
            "uuid": installment.uuid,
            "card_uuid": installment.invoice.card.uuid,
            "card_name": installment.invoice.card.name,
            "invoice": {
                "uuid": installment.invoice.uuid,
                "reference_month": installment.invoice.reference_month,
                "due_date": installment.invoice.due_date,
                "status": installment.invoice.status.value,
            },
            "transaction": {
                "uuid": installment.card_transaction.uuid,
                "uuid_category_transaction": installment.card_transaction.category_transaction.uuid,
                "description": installment.card_transaction.description,
                "purchase_date": installment.card_transaction.purchase_date,
                "total_value": installment.card_transaction.total_value,
                "installments_count": installment.card_transaction.installments_count,
                "merchant_name": (
                    installment.card_transaction.merchant_name.name
                    if installment.card_transaction.merchant_name
                    else None
                ),
                "loan_recipient_name": (
                    installment.card_transaction.loan_recipient.name
                    if installment.card_transaction.loan_recipient
                    else None
                ),
            },
            "installment_number": installment.installment_number,
            "value": installment.value,
            "due_date": installment.due_date,
            "is_paid": installment.is_paid,
            "paid_at": installment.paid_at,
            "created_at": installment.created_at,
            "updated_at": installment.updated_at,
        }
        for installment in installments
    ]


@router.post(
    "/{card_uuid}/transactions",
    response_model=schemas.CardTransactionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_card_transaction(
    card_uuid: UUID,
    payload: schemas.CardTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_card = service.get_card_by_uuid(db, card_uuid)
    if not db_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    if db_card.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create transactions for your own cards",
        )

    return service.create_card_transaction(db, db_card, payload, current_user)


@router.get(
    "/invoices/grouped-by-card",
    response_model=list[schemas.UserCardInvoicesGroupedResponse],
)
def list_user_invoices_grouped_by_card(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_user_invoices_grouped_by_card(db, current_user)


@router.put(
    "/{card_uuid}/transactions/{transaction_uuid}",
    response_model=schemas.CardTransactionCreatedResponse,
)
def update_card_transaction(
    card_uuid: UUID,
    transaction_uuid: UUID,
    payload: schemas.CardTransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_card = service.get_card_by_uuid(db, card_uuid)
    if not db_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    if db_card.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update transactions for your own cards",
        )

    db_transaction = service.repository.get_card_transaction_by_uuid(
        db, transaction_uuid
    )
    if not db_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    if db_transaction.id_card != db_card.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction does not belong to this card",
        )

    if db_transaction.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own transactions",
        )

    return service.update_card_transaction(db, db_transaction, payload, current_user)


@router.delete(
    "/{card_uuid}/transactions/{transaction_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_card_transaction(
    card_uuid: UUID,
    transaction_uuid: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_card = service.get_card_by_uuid(db, card_uuid)
    if not db_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    if db_card.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete transactions for your own cards",
        )

    db_transaction = service.repository.get_card_transaction_by_uuid(
        db, transaction_uuid
    )
    if not db_transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    if db_transaction.id_card != db_card.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction does not belong to this card",
        )

    if db_transaction.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own transactions",
        )

    service.delete_card_transaction(db, db_transaction)


@router.get(
    "/me/summary",
    response_model=schemas.UserCardsSummaryResponse,
)
def get_user_cards_summary(
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=1900, le=9999),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = service.get_user_cards_summary(db, current_user, month=month, year=year)
    return {"total": total}

@router.post(
    "/{card_uuid}/resolve-invoice-reference-month",
    response_model=schemas.ResolveInvoiceReferenceMonthResponse,
)
def resolve_invoice_reference_month(
    card_uuid: UUID,
    payload: schemas.ResolveInvoiceReferenceMonthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resolve which invoice reference month a purchase date would be inserted into.

    Given a card and a purchase date, returns which invoice reference month
    the purchase would belong to, along with the closing and due dates for that invoice.
    """
    db_card = service.get_card_by_uuid(db, card_uuid)
    if not db_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    if db_card.id_user != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only resolve reference months for your own cards",
        )

    return service.resolve_invoice_reference_month(db_card, payload.purchase_date)
