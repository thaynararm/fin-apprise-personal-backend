import logging
import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from src.core.exceptions.domain import ValidationDomainError
from src.modules.cards import repository
from src.modules.cards.model import (
    Card,
    CardInvoice,
    CardTransaction,
    CardTransactionInstallment,
)
from src.modules.cards.schemas import (
    CardCreate,
    CardTransactionCreate,
    CardTransactionUpdate,
    CardUpdate,
)
from src.modules.financial_accounts.repository import get_financial_account_by_uuid
from src.modules.merchants import repository as merchants_repository
from src.modules.loan_recipients import repository as loan_recipients_repository
from src.models.shared.category_transaction import CategoryTransaction
from src.modules.users.model import User
from src.modules.cards.enums import CardInvoiceStatusEnum
from src.modules.cards.invoice_transaction_sync import (
    sync_invoice_account_transaction,
)
from src.core.utils.normalize_text import normalize_text, normalize_display_text

logger = logging.getLogger(__name__)


def _add_months(base_date: date, months: int) -> date:
    year = base_date.year + (base_date.month - 1 + months) // 12
    month = (base_date.month - 1 + months) % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _month_start(base_date: date) -> date:
    return date(base_date.year, base_date.month, 1)


def _safe_day(year: int, month: int, day: int) -> int:
    return min(day, calendar.monthrange(year, month)[1])


def _resolve_first_reference_month(purchase_date: date, closing_day: int) -> date:
    closing_day_for_month = _safe_day(
        purchase_date.year,
        purchase_date.month,
        closing_day,
    )

    date_closing_day = date(
        purchase_date.year, purchase_date.month, closing_day_for_month
    )

    if purchase_date < date_closing_day:
        next_closing_day = date_closing_day

    else:
        next_closing_day = _add_months(date_closing_day, 1)

    # month_offset = 1 if purchase_date.day <= closing_day_for_month else 2
    month_offset = 1 if purchase_date <= next_closing_day else 2
    return _add_months(_month_start(purchase_date), month_offset)


def _split_installments(total_value: float, installments_count: int) -> list[float]:
    total_decimal = Decimal(str(total_value)).quantize(Decimal("0.01"))
    base_value = (total_decimal / installments_count).quantize(
        Decimal("0.01"),
        rounding=ROUND_DOWN,
    )
    values = [base_value for _ in range(installments_count)]

    remainder = total_decimal - (base_value * installments_count)
    remainder_cents = int((remainder * 100).quantize(Decimal("1")))

    for index in range(remainder_cents):
        values[index] += Decimal("0.01")

    return [float(value) for value in values]


def _build_invoice_dates(card: Card, reference_month: date) -> dict[str, date]:
    closing_base_month = _add_months(reference_month, -1)
    previous_closing_base_month = _add_months(reference_month, -2)

    closing_date = date(
        closing_base_month.year,
        closing_base_month.month,
        _safe_day(closing_base_month.year, closing_base_month.month, card.closing_day),
    )

    previous_closing_date = date(
        previous_closing_base_month.year,
        previous_closing_base_month.month,
        _safe_day(
            previous_closing_base_month.year,
            previous_closing_base_month.month,
            card.closing_day,
        ),
    )

    due_date = date(
        reference_month.year,
        reference_month.month,
        _safe_day(reference_month.year, reference_month.month, card.due_day),
    )

    return {
        "closing_date": closing_date,
        "due_date": due_date,
        "start_date": previous_closing_date + timedelta(days=1),
        "end_date": closing_date,
    }


def _get_or_create_invoice_by_reference_month(
    db: Session,
    *,
    current_user: User,
    card: Card,
    reference_month: date,
):
    db_invoice = repository.get_card_invoice_by_reference_month(
        db,
        id_user=current_user.id,
        id_card=card.id,
        reference_month=reference_month,
    )
    if db_invoice:
        return db_invoice

    invoice_dates = _build_invoice_dates(card, reference_month)
    return repository.create_card_invoice_without_commit(
        db,
        id_user=current_user.id,
        id_card=card.id,
        reference_month=reference_month,
        closing_date=invoice_dates["closing_date"],
        due_date=invoice_dates["due_date"],
        start_date=invoice_dates["start_date"],
        end_date=invoice_dates["end_date"],
        total_amount=0.0,
        paid_amount=0.0,
        status=CardInvoiceStatusEnum.OPEN,
    )


def _get_available_limit(card: Card) -> float:
    if card.limit is None:
        return 0.0

    total_invoices_amount = sum(
        float(invoice.total_amount or 0.0) for invoice in card.invoices
    )

    available_limit = float(card.limit) - total_invoices_amount
    return max(available_limit, 0.0)


def create_card(
    db: Session,
    payload: CardCreate,
    current_user: User,
) -> Card:
    normalized_name = payload.name.strip()

    if not normalized_name:
        raise ValidationDomainError("Card name cannot be empty")

    id_account = None
    if payload.uuid_financial_account is not None:
        db_account = get_financial_account_by_uuid(db, payload.uuid_financial_account)
        if not db_account:
            raise ValidationDomainError("Financial account not found")
        if db_account.id_user != current_user.id:
            raise ValidationDomainError("Financial account does not belong to you")
        id_account = db_account.id

    id_brand_names = None
    if payload.brand_name is not None:
        db_brand = repository.get_brand_by_name(db, payload.brand_name)
        if not db_brand:
            raise ValidationDomainError("Brand not found")
        id_brand_names = db_brand.id

    db_card = repository.create_card(
        db,
        id_user=current_user.id,
        id_account=id_account,
        id_brand_names=id_brand_names,
        name=normalized_name,
        card_type=payload.card_type,
        due_day=payload.due_day,
        closing_day=payload.closing_day,
        limit=payload.limit,
        last_4_digits=payload.last_4_digits,
        is_active=payload.is_active,
    )

    # Dia atual para calcular o mês de referência da fatura inicial
    current_date = date(
        db_card.created_at.year, db_card.created_at.month, db_card.created_at.day
    )
    current_month_closing = date(
        current_date.year, current_date.month, payload.closing_day
    )

    if current_date > current_month_closing:
        last_closing = current_month_closing
        next_closing = date(
            current_date.year, (current_date.month + 1), payload.closing_day
        )
        reference_month = date(next_closing.year, (next_closing.month + 1), 1)
        due_date = date(next_closing.year, reference_month.month, payload.due_day)
    else:
        last_closing = date(
            current_date.year, (current_date.month - 1), payload.closing_day
        )
        next_closing = current_month_closing
        reference_month = date(next_closing.year, (next_closing.month + 1), 1)
        due_date = date(next_closing.year, reference_month.month, payload.due_day)

    repository.create_card_invoice(
        db,
        id_user=current_user.id,
        id_card=db_card.id,
        reference_month=reference_month,
        closing_date=next_closing,
        due_date=due_date,
        start_date=(last_closing + timedelta(days=1)),
        end_date=next_closing,
        total_amount=0,
        paid_amount=0,
        status=CardInvoiceStatusEnum.OPEN,
    )

    logger.info(
        "Card created with uuid: %s for user uuid: %s",
        db_card.uuid,
        current_user.uuid,
    )

    return db_card


def get_card_by_uuid(
    db: Session,
    card_uuid: UUID,
) -> Card | None:
    return repository.get_card_by_uuid(db, card_uuid)


def list_cards_by_user(
    db: Session,
    current_user: User,
    *,
    skip: int = 0,
    limit: int = 100,
) -> list[Card]:
    return repository.list_cards_by_user(
        db,
        id_user=current_user.id,
        skip=skip,
        limit=limit,
    )


def get_user_cards_summary(
    db: Session,
    current_user: User,
    *,
    month: int | None = None,
    year: int | None = None,
) -> dict[str, float]:
    return repository.get_user_cards_summary(
        db,
        id_user=current_user.id,
        month=month,
        year=year,
    )


def get_card_invoice_amount(
    card: Card,
    month: int,
    year: int | None = None,
) -> float:
    """
    Get the invoice amount for a specific card and reference month.

    Args:
        card: The Card object
        month: Month (1-12)
        year: Year. If None, uses the current year

    Returns:
        Float representing the total amount for the invoice, or 0.0 if not found
    """
    from datetime import datetime

    if year is None:
        year = datetime.now().year

    # Create reference_month as first day of the requested month/year
    reference_month = date(year, month, 1)

    # Find invoice with matching reference_month
    for invoice in card.invoices:
        if (
            invoice.reference_month.month == month
            and invoice.reference_month.year == year
        ):
            return float(invoice.total_amount or 0.0)

    return 0.0


def list_card_installments_by_reference_month(
    db: Session,
    current_user: User,
    *,
    month: int,
    year: int | None = None,
    purchase_date_start: date | None = None,
    purchase_date_end: date | None = None,
    description: str | None = None,
    category: str | None = None,
    card_uuid: list[UUID] | None = None,
    value_text: str | None = None,
    order_by: list[str] | None = None,
):
    return repository.list_card_installments_by_reference_month(
        db,
        id_user=current_user.id,
        month=month,
        year=year,
        purchase_date_start=purchase_date_start,
        purchase_date_end=purchase_date_end,
        description=description,
        category=category,
        card_uuid=card_uuid,
        value_text=value_text,
        order_by=order_by,
    )


def list_user_invoices_grouped_by_card(
    db: Session,
    current_user: User,
) -> list[dict]:
    invoices = repository.list_card_invoices_by_user(db, id_user=current_user.id)

    grouped: dict[int, dict] = {}
    for invoice in invoices:
        card = invoice.card
        if card is None:
            continue

        if card.id not in grouped:
            grouped[card.id] = {
                "card_uuid": card.uuid,
                "card_name": card.name,
                "invoices": [],
            }

        grouped[card.id]["invoices"].append(
            {
                "uuid": invoice.uuid,
                "reference_month": invoice.reference_month,
                "closing_date": invoice.closing_date,
                "due_date": invoice.due_date,
                "start_date": invoice.start_date,
                "end_date": invoice.end_date,
                "total_amount": float(invoice.total_amount or 0.0),
                "paid_amount": float(invoice.paid_amount or 0.0),
                "status": invoice.status.value,
                "created_at": invoice.created_at,
                "updated_at": invoice.updated_at,
            }
        )

    return list(grouped.values())


def create_card_transaction(
    db: Session,
    db_card: Card,
    payload: CardTransactionCreate,
    current_user: User,
):
    if db_card.closing_day is None:
        raise ValidationDomainError("Card does not have closing_day configured")

    category = (
        db.query(CategoryTransaction)
        .filter(CategoryTransaction.uuid == payload.uuid_category_transaction)
        .first()
    )

    if not category:
        raise ValidationDomainError("Category transaction not found")

    if category.id_user != current_user.id:
        raise ValidationDomainError("You can only use your own category transaction")

    normalized_description = payload.description.strip()
    if not normalized_description:
        raise ValidationDomainError("Description cannot be empty")

    id_merchant_name = None
    if payload.merchant_name is not None:
        normalized_merchant_name = normalize_text(payload.merchant_name)
        normalized_merchant_description = normalize_display_text(payload.merchant_name)
        if normalized_merchant_name:
            db_merchant = merchants_repository.get_or_create_merchant_by_name(
                db,
                current_user.id,
                normalized_merchant_name,
                normalized_merchant_description,
            )
            id_merchant_name = db_merchant.id

    id_loan_recipient = None
    if payload.loan_recipient_name is not None:
        if normalize_text(category.name) != "emprestimo":
            raise ValidationDomainError(
                "loan_recipient_name só pode ser informado quando a categoria for 'Empréstimo'"
            )
        if payload.loan_recipient_name:
            db_recipient = (
                loan_recipients_repository.get_or_create_loan_recipient_by_name(
                    db,
                    current_user.id,
                    normalize_text(payload.loan_recipient_name),
                    normalize_display_text(payload.loan_recipient_name),
                )
            )
            id_loan_recipient = db_recipient.id

    installment_values = _split_installments(
        payload.total_value,
        payload.installments_count,
    )

    try:
        db_card_transaction = repository.create_card_transaction_without_commit(
            db,
            id_user=current_user.id,
            id_card=db_card.id,
            id_category_transaction=category.id,
            transaction_type=payload.transaction_type,
            description=normalized_description,
            purchase_date=payload.purchase_date,
            total_value=payload.total_value,
            installments_count=payload.installments_count,
            id_merchant_name=id_merchant_name,
            id_loan_recipient=id_loan_recipient,
            is_canceled=False,
        )

        first_reference_month = _resolve_first_reference_month(
            payload.purchase_date,
            db_card.closing_day,
        )

        if (
            payload.invoice_reference_month is not None
            and payload.invoice_reference_month != first_reference_month
            and payload.invoice_reference_month > first_reference_month
        ):
            closing_day_for_month = date(
                payload.purchase_date.year,
                payload.purchase_date.month,
                db_card.closing_day,
            )

            purchase_date = payload.purchase_date
            if purchase_date - closing_day_for_month < timedelta(days=5):
                invoice_reference_month_payload = (
                    _get_or_create_invoice_by_reference_month(
                        db,
                        current_user=current_user,
                        card=db_card,
                        reference_month=payload.invoice_reference_month,
                    )
                )
                invoice_first_reference_month = (
                    _get_or_create_invoice_by_reference_month(
                        db,
                        current_user=current_user,
                        card=db_card,
                        reference_month=first_reference_month,
                    )
                )

                invoice_reference_month_payload.start_date = purchase_date
                invoice_first_reference_month.end_date = purchase_date - timedelta(
                    days=1
                )

                first_reference_month = payload.invoice_reference_month

            else:
                raise ValidationDomainError(
                    "O mês de referência da fatura não pôde ser alterado. Contate o suporte para mais informações."
                )

        if (
            payload.invoice_reference_month is not None
            and payload.invoice_reference_month != first_reference_month
            and payload.invoice_reference_month < first_reference_month
        ):
            closing_day_for_month = date(
                payload.purchase_date.year,
                payload.purchase_date.month,
                db_card.closing_day,
            )

            purchase_date = payload.purchase_date
            if purchase_date - closing_day_for_month < timedelta(days=5):
                invoice_reference_month_payload = (
                    _get_or_create_invoice_by_reference_month(
                        db,
                        current_user=current_user,
                        card=db_card,
                        reference_month=payload.invoice_reference_month,
                    )
                )
                invoice_first_reference_month = (
                    _get_or_create_invoice_by_reference_month(
                        db,
                        current_user=current_user,
                        card=db_card,
                        reference_month=first_reference_month,
                    )
                )

                invoice_reference_month_payload.start_date = purchase_date
                invoice_first_reference_month.end_date = purchase_date - timedelta(
                    days=1
                )

                first_reference_month = payload.invoice_reference_month

            else:
                raise ValidationDomainError(
                    "O mês de referência da fatura não pôde ser alterado. Contate o suporte para mais informações."
                )

        created_installments = []
        affected_invoice_ids: set[int] = set()
        for installment_index in range(payload.installments_count):
            reference_month = _add_months(first_reference_month, installment_index)
            db_invoice = _get_or_create_invoice_by_reference_month(
                db,
                current_user=current_user,
                card=db_card,
                reference_month=reference_month,
            )

            installment_value = installment_values[installment_index]

            db_invoice.total_amount = float(db_invoice.total_amount or 0.0) + float(
                installment_value
            )

            db_installment = (
                repository.create_card_transaction_installment_without_commit(
                    db,
                    id_card_transaction=db_card_transaction.id,
                    id_card_invoice=db_invoice.id,
                    installment_number=installment_index + 1,
                    value=installment_value,
                    due_date=db_invoice.due_date,
                    is_paid=False,
                )
            )

            created_installments.append((db_installment, db_invoice))
            affected_invoice_ids.add(db_invoice.id)

        for invoice_id in affected_invoice_ids:
            invoice_to_sync = (
                db.query(CardInvoice)
                .options(joinedload(CardInvoice.card))
                .filter(CardInvoice.id == invoice_id)
                .first()
            )
            if invoice_to_sync is not None:
                sync_invoice_account_transaction(db, invoice_to_sync)

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(db_card_transaction)

    return {
        "uuid": db_card_transaction.uuid,
        "card_uuid": db_card.uuid,
        "uuid_category_transaction": category.uuid,
        "transaction_type": db_card_transaction.transaction_type.value,
        "description": db_card_transaction.description,
        "purchase_date": db_card_transaction.purchase_date,
        "total_value": db_card_transaction.total_value,
        "installments_count": db_card_transaction.installments_count,
        "merchant_name": (
            db_card_transaction.merchant_name.name
            if db_card_transaction.merchant_name
            else None
        ),
        "loan_recipient_name": (
            db_card_transaction.loan_recipient.name
            if db_card_transaction.loan_recipient
            else None
        ),
        "is_canceled": db_card_transaction.is_canceled,
        "created_at": db_card_transaction.created_at,
        "updated_at": db_card_transaction.updated_at,
        "installments": [
            {
                "uuid": db_installment.uuid,
                "invoice_uuid": db_invoice.uuid,
                "invoice_reference_month": db_invoice.reference_month,
                "installment_number": db_installment.installment_number,
                "value": db_installment.value,
                "due_date": db_installment.due_date,
                "is_paid": db_installment.is_paid,
            }
            for db_installment, db_invoice in created_installments
        ],
    }


def update_card(
    db: Session,
    db_card: Card,
    payload: CardUpdate,
) -> Card:
    fields = payload.model_dump(exclude_unset=True)

    if "name" in fields:
        normalized_name = fields["name"].strip()
        if not normalized_name:
            raise ValidationDomainError("Card name cannot be empty")
        fields["name"] = normalized_name

    if "uuid_financial_account" in fields:
        uuid_financial_account = fields.pop("uuid_financial_account")
        if uuid_financial_account is None:
            fields["id_account"] = None
        else:
            db_account = get_financial_account_by_uuid(db, uuid_financial_account)
            if not db_account:
                raise ValidationDomainError("Financial account not found")
            if db_account.id_user != db_card.id_user:
                raise ValidationDomainError("Financial account does not belong to you")
            fields["id_account"] = db_account.id

    if "brand_name" in fields:
        brand_name_value = fields.pop("brand_name")
        if brand_name_value is None:
            fields["id_brand_names"] = None
        else:
            db_brand = repository.get_brand_by_name(db, brand_name_value)
            if not db_brand:
                raise ValidationDomainError("Brand not found")
            fields["id_brand_names"] = db_brand.id

    updated_card = repository.update_card(db, db_card, **fields)

    logger.info("Card updated with uuid: %s", db_card.uuid)

    return updated_card


def update_card_transaction(
    db: Session,
    db_transaction: CardTransaction,
    payload: CardTransactionUpdate,
    current_user: User,
) -> dict:
    fields = payload.model_dump(exclude_unset=True)

    if "description" in fields:
        normalized_description = fields["description"].strip()
        if not normalized_description:
            raise ValidationDomainError("Description cannot be empty")
        fields["description"] = normalized_description

    if "uuid_category_transaction" in fields:
        category_uuid = fields.pop("uuid_category_transaction")
        if category_uuid is None:
            raise ValidationDomainError("Category transaction cannot be empty")

        category = (
            db.query(CategoryTransaction)
            .filter(CategoryTransaction.uuid == category_uuid)
            .first()
        )
        if not category:
            raise ValidationDomainError("Category transaction not found")

        if category.id_user != current_user.id:
            raise ValidationDomainError(
                "You can only use your own category transaction"
            )

        fields["id_category_transaction"] = category.id

    if "merchant_name" in fields:
        merchant_name = fields.pop("merchant_name")
        if merchant_name is None:
            fields["id_merchant_name"] = None
        else:
            normalized_merchant_name = normalize_text(merchant_name)
            normalized_merchant_description = normalize_display_text(merchant_name)
            if not normalized_merchant_name:
                raise ValidationDomainError("Merchant name cannot be empty")

            db_merchant = merchants_repository.get_or_create_merchant_by_name(
                db,
                current_user.id,
                normalized_merchant_name,
                normalized_merchant_description,
            )
            fields["id_merchant_name"] = db_merchant.id

    if "loan_recipient_name" in fields:
        loan_recipient_name = fields.pop("loan_recipient_name")
        if loan_recipient_name is None:
            fields["id_loan_recipient"] = None
        else:
            # Resolve category to validate
            if "id_category_transaction" in fields:
                resolved_category_id = fields["id_category_transaction"]
                from src.models.shared.category_transaction import (
                    CategoryTransaction as CT,
                )

                resolved_category = (
                    db.query(CT).filter(CT.id == resolved_category_id).first()
                )
            else:
                from src.models.shared.category_transaction import (
                    CategoryTransaction as CT,
                )

                resolved_category = (
                    db.query(CT)
                    .filter(CT.id == db_transaction.id_category_transaction)
                    .first()
                )

            if (
                resolved_category
                and normalize_text(resolved_category.name) != "emprestimo"
            ):
                raise ValidationDomainError(
                    "loan_recipient_name só pode ser informado quando a categoria for 'Empréstimo'"
                )

            normalized_recipient_name = normalize_display_text(loan_recipient_name)
            if not normalized_recipient_name:
                raise ValidationDomainError("Loan recipient name cannot be empty")

            db_recipient = (
                loan_recipients_repository.get_or_create_loan_recipient_by_name(
                    db,
                    current_user.id,
                    normalize_text(payload.loan_recipient_name),
                    normalize_display_text(payload.loan_recipient_name),
                )
            )
            fields["id_loan_recipient"] = db_recipient.id

    if "uuid_card" in fields:
        target_card_uuid = fields.pop("uuid_card")
        if target_card_uuid is None:
            raise ValidationDomainError("Card uuid cannot be empty")

        target_card = get_card_by_uuid(db, target_card_uuid)
        if not target_card:
            raise ValidationDomainError("Card not found")
        if target_card.id_user != current_user.id:
            raise ValidationDomainError("You can only use your own card")

        fields["id_card"] = target_card.id

    should_rebuild_installments = any(
        key in fields
        for key in (
            "id_card",
            "total_value",
            "installments_count",
            "purchase_date",
            "invoice_reference_month",
        )
    )

    if "total_value" in fields and fields["total_value"] is None:
        raise ValidationDomainError("Total value cannot be empty")

    if "installments_count" in fields and fields["installments_count"] is None:
        raise ValidationDomainError("Installments count cannot be empty")

    if "purchase_date" in fields and fields["purchase_date"] is None:
        raise ValidationDomainError("Purchase date cannot be empty")

    try:
        affected_invoice_ids: set[int] = set()
        if should_rebuild_installments:
            old_installments = list(db_transaction.installments)

            for old_installment in old_installments:
                if old_installment.invoice is not None:
                    old_total = float(old_installment.invoice.total_amount or 0.0)
                    new_total = old_total - float(old_installment.value)
                    old_installment.invoice.total_amount = (
                        new_total if new_total > 0 else 0.0
                    )
                    affected_invoice_ids.add(old_installment.invoice.id)

            for old_installment in old_installments:
                db.delete(old_installment)

            db.flush()

            for key, value in fields.items():
                setattr(db_transaction, key, value)

            target_card = (
                db.query(Card).filter(Card.id == db_transaction.id_card).first()
            )
            if target_card is None:
                raise ValidationDomainError("Card not found")
            if target_card.closing_day is None:
                raise ValidationDomainError("Card does not have closing_day configured")

            installment_values = _split_installments(
                db_transaction.total_value,
                db_transaction.installments_count,
            )

            first_reference_month = _resolve_first_reference_month(
                db_transaction.purchase_date,
                target_card.closing_day,
            )

            effective_purchase_date = db_transaction.purchase_date

            if (
                payload.invoice_reference_month is not None
                and payload.invoice_reference_month != first_reference_month
                and payload.invoice_reference_month > first_reference_month
            ):
                closing_day_for_month = date(
                    effective_purchase_date.year,
                    effective_purchase_date.month,
                    target_card.closing_day,
                )

                purchase_date = effective_purchase_date
                if purchase_date - closing_day_for_month < timedelta(days=5):
                    invoice_reference_month_payload = (
                        _get_or_create_invoice_by_reference_month(
                            db,
                            current_user=current_user,
                            card=target_card,
                            reference_month=payload.invoice_reference_month,
                        )
                    )
                    invoice_first_reference_month = (
                        _get_or_create_invoice_by_reference_month(
                            db,
                            current_user=current_user,
                            card=target_card,
                            reference_month=first_reference_month,
                        )
                    )

                    invoice_reference_month_payload.start_date = purchase_date
                    invoice_first_reference_month.end_date = purchase_date - timedelta(
                        days=1
                    )

                    first_reference_month = payload.invoice_reference_month

                else:
                    raise ValidationDomainError(
                        "O mês de referência da fatura não pôde ser alterado. Contate o suporte para mais informações."
                    )

            if (
                payload.invoice_reference_month is not None
                and payload.invoice_reference_month != first_reference_month
                and payload.invoice_reference_month < first_reference_month
            ):
                closing_day_for_month = date(
                    effective_purchase_date.year,
                    effective_purchase_date.month,
                    target_card.closing_day,
                )

                purchase_date = effective_purchase_date
                if purchase_date - closing_day_for_month < timedelta(days=5):
                    invoice_reference_month_payload = (
                        _get_or_create_invoice_by_reference_month(
                            db,
                            current_user=current_user,
                            card=target_card,
                            reference_month=payload.invoice_reference_month,
                        )
                    )
                    invoice_first_reference_month = (
                        _get_or_create_invoice_by_reference_month(
                            db,
                            current_user=current_user,
                            card=target_card,
                            reference_month=first_reference_month,
                        )
                    )

                    invoice_reference_month_payload.start_date = purchase_date
                    invoice_first_reference_month.end_date = purchase_date - timedelta(
                        days=1
                    )

                    first_reference_month = payload.invoice_reference_month

                else:
                    raise ValidationDomainError(
                        "O mês de referência da fatura não pôde ser alterado. Contate o suporte para mais informações."
                    )

            for installment_index, installment_value in enumerate(installment_values):
                reference_month = _add_months(first_reference_month, installment_index)
                db_invoice = _get_or_create_invoice_by_reference_month(
                    db,
                    current_user=current_user,
                    card=target_card,
                    reference_month=reference_month,
                )

                db_invoice.total_amount = float(db_invoice.total_amount or 0.0) + float(
                    installment_value
                )
                affected_invoice_ids.add(db_invoice.id)

                repository.create_card_transaction_installment_without_commit(
                    db,
                    id_card_transaction=db_transaction.id,
                    id_card_invoice=db_invoice.id,
                    installment_number=installment_index + 1,
                    value=installment_value,
                    due_date=db_invoice.due_date,
                    is_paid=False,
                )

            for invoice_id in affected_invoice_ids:
                invoice_to_sync = (
                    db.query(CardInvoice)
                    .options(joinedload(CardInvoice.card))
                    .filter(CardInvoice.id == invoice_id)
                    .first()
                )
                if invoice_to_sync is not None:
                    sync_invoice_account_transaction(db, invoice_to_sync)

            db.commit()
            db.refresh(db_transaction)
            updated_transaction = db_transaction
        else:
            updated_transaction = repository.update_card_transaction(
                db,
                db_transaction,
                **fields,
            )

            affected_invoice_ids = {
                installment.id_card_invoice
                for installment in db.query(CardTransactionInstallment)
                .filter(
                    CardTransactionInstallment.id_card_transaction
                    == updated_transaction.id
                )
                .all()
            }

            # Fallback para transacoes antigas/orfas sem parcelas: recria o vinculo com fatura.
            if not affected_invoice_ids:
                target_card = (
                    db.query(Card)
                    .filter(Card.id == updated_transaction.id_card)
                    .first()
                )
                if target_card is None:
                    raise ValidationDomainError("Card not found")
                if target_card.closing_day is None:
                    raise ValidationDomainError(
                        "Card does not have closing_day configured"
                    )

                installment_values = _split_installments(
                    updated_transaction.total_value,
                    updated_transaction.installments_count,
                )
                first_reference_month = _resolve_first_reference_month(
                    updated_transaction.purchase_date,
                    target_card.closing_day,
                )

                for installment_index, installment_value in enumerate(
                    installment_values
                ):
                    reference_month = _add_months(
                        first_reference_month, installment_index
                    )
                    db_invoice = _get_or_create_invoice_by_reference_month(
                        db,
                        current_user=current_user,
                        card=target_card,
                        reference_month=reference_month,
                    )

                    db_invoice.total_amount = float(
                        db_invoice.total_amount or 0.0
                    ) + float(installment_value)
                    affected_invoice_ids.add(db_invoice.id)

                    repository.create_card_transaction_installment_without_commit(
                        db,
                        id_card_transaction=updated_transaction.id,
                        id_card_invoice=db_invoice.id,
                        installment_number=installment_index + 1,
                        value=installment_value,
                        due_date=db_invoice.due_date,
                        is_paid=False,
                    )

            for invoice_id in affected_invoice_ids:
                invoice_to_sync = (
                    db.query(CardInvoice)
                    .options(joinedload(CardInvoice.card))
                    .filter(CardInvoice.id == invoice_id)
                    .first()
                )
                if invoice_to_sync is not None:
                    sync_invoice_account_transaction(db, invoice_to_sync)

            if affected_invoice_ids:
                db.commit()
                db.refresh(updated_transaction)
    except Exception:
        db.rollback()
        raise

    logger.info("Card transaction updated with uuid: %s", db_transaction.uuid)

    updated_transaction = (
        db.query(CardTransaction)
        .options(
            joinedload(CardTransaction.category_transaction),
            joinedload(CardTransaction.merchant_name),
            joinedload(CardTransaction.loan_recipient),
            joinedload(CardTransaction.card),
            joinedload(CardTransaction.installments).joinedload(
                CardTransactionInstallment.invoice
            ),
        )
        .filter(CardTransaction.id == updated_transaction.id)
        .first()
    )

    return {
        "uuid": updated_transaction.uuid,
        "card_uuid": updated_transaction.card.uuid,
        "uuid_category_transaction": updated_transaction.category_transaction.uuid,
        "transaction_type": updated_transaction.transaction_type.value,
        "description": updated_transaction.description,
        "purchase_date": updated_transaction.purchase_date,
        "total_value": updated_transaction.total_value,
        "installments_count": updated_transaction.installments_count,
        "merchant_name": (
            updated_transaction.merchant_name.name
            if updated_transaction.merchant_name
            else None
        ),
        "loan_recipient_name": (
            updated_transaction.loan_recipient.name
            if updated_transaction.loan_recipient
            else None
        ),
        "is_canceled": updated_transaction.is_canceled,
        "created_at": updated_transaction.created_at,
        "updated_at": updated_transaction.updated_at,
        "installments": [
            {
                "uuid": installment.uuid,
                "invoice_uuid": installment.invoice.uuid,
                "invoice_reference_month": installment.invoice.reference_month,
                "installment_number": installment.installment_number,
                "value": installment.value,
                "due_date": installment.due_date,
                "is_paid": installment.is_paid,
            }
            for installment in updated_transaction.installments
        ],
    }


def delete_card_transaction(
    db: Session,
    db_transaction: CardTransaction,
) -> None:
    """Delete a card transaction and all its installments."""
    logger.info("Deleting card transaction with uuid: %s", db_transaction.uuid)
    affected_invoice_ids = {
        installment.invoice.id
        for installment in db_transaction.installments
        if installment.invoice is not None
    }
    repository.delete_card_transaction(db, db_transaction)

    for invoice_id in affected_invoice_ids:
        db_invoice = (
            db.query(CardInvoice)
            .options(joinedload(CardInvoice.card))
            .filter(CardInvoice.id == invoice_id)
            .first()
        )
        if db_invoice is not None:
            sync_invoice_account_transaction(db, db_invoice)

    if affected_invoice_ids:
        db.commit()


def resolve_invoice_reference_month(
    card: Card,
    purchase_date: date,
) -> dict[str, date | int]:
    """
    Resolve which invoice reference month a purchase date would be inserted into.

    Args:
        card: The Card object with closing_day and due_day configured
        purchase_date: The purchase date to resolve

    Returns:
        Dictionary containing:
        - purchase_date: The input purchase date
        - card_closing_day: The card's closing day
        - invoice_reference_month: The resolved invoice reference month
        - closing_date: The closing date for this invoice
        - due_date: The due date for this invoice

    Raises:
        ValidationDomainError: If the card doesn't have closing_day configured
    """
    if card.closing_day is None:
        raise ValidationDomainError("Card does not have closing_day configured")

    if card.due_day is None:
        raise ValidationDomainError("Card does not have due_day configured")

    first_reference_month = _resolve_first_reference_month(
        purchase_date,
        card.closing_day,
    )

    invoice_dates = _build_invoice_dates(card, first_reference_month)

    return {
        "purchase_date": purchase_date,
        "card_closing_day": card.closing_day,
        "invoice_reference_month": first_reference_month,
        "closing_date": invoice_dates["closing_date"],
        "due_date": invoice_dates["due_date"],
    }
