from uuid import UUID
from datetime import date
from sqlalchemy import String, cast, extract
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from src.modules.cards import service
from src.modules.cards.model import (
    Card,
    CardInvoice,
    CardTransaction,
    CardTransactionInstallment,
    CardTypeEnum,
)
from src.models.shared.category_transaction import CategoryTransaction
from src.modules.financial_accounts.model import FinancialAccount
from src.modules.cards.enums import CardInvoiceStatusEnum
from src.models.shared.bank_names import BrandNames


def get_card_by_uuid(
    db: Session,
    card_uuid: UUID,
) -> Card | None:
    return (
        db.query(Card)
        .options(
            joinedload(Card.brand_name),
            joinedload(Card.account).joinedload(FinancialAccount.bank_name),
            joinedload(Card.card_transactions),
            joinedload(Card.invoices),
        )
        .filter(Card.uuid == card_uuid)
        .first()
    )


def update_card(
    db: Session,
    db_card: Card,
    **fields,
) -> Card:
    for key, value in fields.items():
        setattr(db_card, key, value)

    db.commit()
    db.refresh(db_card)

    return db_card


def list_cards_by_user(
    db: Session,
    *,
    id_user: int,
    skip: int = 0,
    limit: int = 100,
) -> list[Card]:
    return (
        db.query(Card)
        .options(
            joinedload(Card.brand_name),
            joinedload(Card.account).joinedload(FinancialAccount.bank_name),
            joinedload(Card.card_transactions),
            joinedload(Card.invoices),
        )
        .filter(Card.id_user == id_user)
        .order_by(Card.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_brand_by_name(
    db: Session,
    brand_name: str,
) -> BrandNames | None:
    return db.query(BrandNames).filter(BrandNames.name.ilike(brand_name)).first()


def create_card(
    db: Session,
    *,
    id_user: int,
    id_account: int | None,
    id_brand_names: int | None = None,
    name: str,
    card_type: CardTypeEnum,
    due_day: int,
    closing_day: int | None = None,
    limit: float | None = None,
    last_4_digits: str | None = None,
    is_active: bool = True,
) -> Card:
    db_card = Card(
        id_user=id_user,
        id_account=id_account,
        id_brand_names=id_brand_names,
        name=name,
        card_type=card_type,
        due_day=due_day,
        closing_day=closing_day,
        limit=limit,
        last_4_digits=last_4_digits,
        is_active=is_active,
    )

    db.add(db_card)
    db.commit()
    db.refresh(db_card)

    return db_card


def get_user_cards_summary(
    db: Session,
    *,
    id_user: int,
    month: int | None = None,
    year: int | None = None,
) -> dict[str, float]:
    from datetime import datetime

    cards = (
        db.query(Card)
        .options(joinedload(Card.invoices))
        .filter(Card.id_user == id_user)
        .all()
    )

    total_limits = sum(float(card.limit or 0.0) for card in cards)
    total_available_limit = sum(service._get_available_limit(card) for card in cards)

    return {
        "limits": float(total_limits),
        "current_invoice": float(total_limits - total_available_limit),
        "available_limit": float(total_available_limit),
    }


def _get_card_current_invoice_legacy(card: Card) -> float:
    """Legacy method to get the first open invoice amount for a card."""
    open_invoices = [
        invoice
        for invoice in card.invoices
        if invoice.status == CardInvoiceStatusEnum.OPEN
    ]

    if not open_invoices:
        return 0.0

    first_open_invoice = min(open_invoices, key=lambda invoice: invoice.reference_month)

    return float(first_open_invoice.total_amount or 0.0)


def create_card_invoice(
    db: Session,
    *,
    id_user: int,
    id_card: int,
    reference_month: date,
    closing_date: date,
    due_date: date,
    start_date: date,
    end_date: date,
    total_amount: float = 0.0,
    paid_amount: float = 0.0,
    status: CardInvoiceStatusEnum = CardInvoiceStatusEnum.OPEN,
):
    db_card_invoice = CardInvoice(
        id_user=id_user,
        id_card=id_card,
        reference_month=reference_month,
        closing_date=closing_date,
        due_date=due_date,
        start_date=start_date,
        end_date=end_date,
        total_amount=total_amount,
        paid_amount=paid_amount,
        status=status,
    )

    db.add(db_card_invoice)
    db.commit()
    db.refresh(db_card_invoice)

    return db_card_invoice


def list_card_installments_by_reference_month(
    db: Session,
    *,
    id_user: int,
    month: int,
    year: int | None = None,
    purchase_date_start: date | None = None,
    purchase_date_end: date | None = None,
    description: str | None = None,
    category: str | None = None,
    card_uuid: list[UUID] | None = None,
    value_text: str | None = None,
    order_by: list[str] | None = None,
) -> list[CardTransactionInstallment]:
    normalized_value_text = value_text.strip() if value_text else None
    order_by_fields = order_by or ["purchase_date", "card_name"]

    query = (
        db.query(CardTransactionInstallment)
        .join(CardInvoice, CardTransactionInstallment.id_card_invoice == CardInvoice.id)
        .join(
            CardTransaction,
            CardTransactionInstallment.id_card_transaction == CardTransaction.id,
        )
        .join(Card, CardInvoice.id_card == Card.id)
        .outerjoin(
            CategoryTransaction,
            CardTransaction.id_category_transaction == CategoryTransaction.id,
        )
        .options(
            joinedload(CardTransactionInstallment.invoice).joinedload(CardInvoice.card),
            joinedload(CardTransactionInstallment.card_transaction).joinedload(
                CardTransaction.category_transaction
            ),
            joinedload(CardTransactionInstallment.card_transaction).joinedload(
                CardTransaction.merchant_name
            ),
        )
        .filter(CardInvoice.id_user == id_user)
        .filter(extract("month", CardInvoice.reference_month) == month)
    )

    if year is not None:
        query = query.filter(extract("year", CardInvoice.reference_month) == year)

    if purchase_date_start is not None:
        query = query.filter(CardTransaction.purchase_date >= purchase_date_start)

    if purchase_date_end is not None:
        query = query.filter(CardTransaction.purchase_date <= purchase_date_end)

    if description is not None and description.strip():
        query = query.filter(
            CardTransaction.description.ilike(f"%{description.strip()}%")
        )

    if category is not None and category.strip():
        query = query.filter(CategoryTransaction.name.ilike(f"%{category.strip()}%"))

    if card_uuid:
        query = query.filter(Card.uuid.in_(card_uuid))

    if normalized_value_text:
        query = query.filter(
            cast(CardTransactionInstallment.value, String).ilike(
                f"%{normalized_value_text}%"
            )
        )

    order_by_mapping = {
        "purchase_date": CardTransaction.purchase_date,
        "category": CategoryTransaction.name,
        "description": CardTransaction.description,
        "card_name": Card.name,
        "value": CardTransactionInstallment.value,
    }

    order_clauses = []
    for field in order_by_fields:
        direction = "asc"
        clean_field = field

        if field.startswith("-"):
            direction = "desc"
            clean_field = field[1:]
        elif field.startswith("+"):
            clean_field = field[1:]

        column = order_by_mapping.get(clean_field)
        if column is None:
            continue

        order_clauses.append(column.desc() if direction == "desc" else column.asc())

    order_clauses.append(CardTransactionInstallment.installment_number.asc())

    return query.order_by(*order_clauses).all()


def list_card_invoices_by_user(
    db: Session,
    *,
    id_user: int,
) -> list[CardInvoice]:
    return (
        db.query(CardInvoice)
        .options(joinedload(CardInvoice.card))
        .filter(CardInvoice.id_user == id_user)
        .join(Card, CardInvoice.id_card == Card.id)
        .order_by(Card.name.asc(), CardInvoice.reference_month.desc())
        .all()
    )


def get_card_invoice_by_reference_month(
    db: Session,
    *,
    id_user: int,
    id_card: int,
    reference_month: date,
) -> CardInvoice | None:
    return (
        db.query(CardInvoice)
        .filter(CardInvoice.id_user == id_user)
        .filter(CardInvoice.id_card == id_card)
        .filter(CardInvoice.reference_month == reference_month)
        .first()
    )


def create_card_invoice_without_commit(
    db: Session,
    *,
    id_user: int,
    id_card: int,
    reference_month: date,
    closing_date: date,
    due_date: date,
    start_date: date,
    end_date: date,
    total_amount: float = 0.0,
    paid_amount: float = 0.0,
    status: CardInvoiceStatusEnum = CardInvoiceStatusEnum.OPEN,
) -> CardInvoice:
    db_card_invoice = CardInvoice(
        id_user=id_user,
        id_card=id_card,
        reference_month=reference_month,
        closing_date=closing_date,
        due_date=due_date,
        start_date=start_date,
        end_date=end_date,
        total_amount=total_amount,
        paid_amount=paid_amount,
        status=status,
    )

    db.add(db_card_invoice)
    db.flush()

    return db_card_invoice


def create_card_transaction_without_commit(
    db: Session,
    *,
    id_user: int,
    id_card: int,
    id_category_transaction: int,
    transaction_type,
    description: str,
    purchase_date: date,
    total_value: float,
    installments_count: int,
    id_merchant_name: int | None = None,
    id_loan_recipient: int | None = None,
    is_canceled: bool = False,
) -> CardTransaction:
    db_card_transaction = CardTransaction(
        id_user=id_user,
        id_card=id_card,
        id_category_transaction=id_category_transaction,
        transaction_type=transaction_type,
        description=description,
        purchase_date=purchase_date,
        total_value=total_value,
        installments_count=installments_count,
        id_merchant_name=id_merchant_name,
        id_loan_recipient=id_loan_recipient,
        is_canceled=is_canceled,
    )

    db.add(db_card_transaction)
    db.flush()

    return db_card_transaction


def create_card_transaction_installment_without_commit(
    db: Session,
    *,
    id_card_transaction: int,
    id_card_invoice: int,
    installment_number: int,
    value: float,
    due_date: date,
    is_paid: bool = False,
) -> CardTransactionInstallment:
    db_installment = CardTransactionInstallment(
        id_card_transaction=id_card_transaction,
        id_card_invoice=id_card_invoice,
        installment_number=installment_number,
        value=value,
        due_date=due_date,
        is_paid=is_paid,
    )

    db.add(db_installment)
    db.flush()

    return db_installment


def get_card_transaction_by_uuid(
    db: Session,
    transaction_uuid: UUID,
) -> CardTransaction | None:
    return (
        db.query(CardTransaction)
        .options(
            joinedload(CardTransaction.category_transaction),
            joinedload(CardTransaction.merchant_name),
            joinedload(CardTransaction.card),
            joinedload(CardTransaction.installments),
        )
        .filter(CardTransaction.uuid == transaction_uuid)
        .first()
    )


def update_card_transaction(
    db: Session,
    db_transaction: CardTransaction,
    **fields,
) -> CardTransaction:
    for key, value in fields.items():
        setattr(db_transaction, key, value)

    db.commit()
    db.refresh(db_transaction)

    return db_transaction


def delete_card_transaction(
    db: Session,
    db_transaction: CardTransaction,
) -> None:
    # Delete installments first
    for installment in db_transaction.installments:
        if installment.invoice is not None:
            old_total = float(installment.invoice.total_amount or 0.0)
            new_total = old_total - float(installment.value)
            installment.invoice.total_amount = new_total if new_total > 0 else 0.0
        db.delete(installment)

    db.delete(db_transaction)
    db.commit()
