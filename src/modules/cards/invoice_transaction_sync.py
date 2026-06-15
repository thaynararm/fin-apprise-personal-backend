"""Synchronization between card invoices and account transactions."""

import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session
from src.core.exceptions.domain import ValidationDomainError
from src.models.shared.category_transaction import CategoryTransaction
from src.models.shared.enums import TransactionTypeEnum
from src.modules.cards.enums import CardInvoiceStatusEnum
from src.modules.cards.model import CardInvoice
from src.modules.financial_accounts.model import AccountTransaction, FinancialAccount

logger = logging.getLogger(__name__)


def _get_account_for_invoice(db: Session, card_invoice: CardInvoice) -> int:
    card = card_invoice.card

    if card.id_account:
        return card.id_account

    primary_account = (
        db.query(FinancialAccount)
        .filter(
            FinancialAccount.id_user == card_invoice.id_user,
            FinancialAccount.is_primary_bank.is_(True),
            FinancialAccount.is_active.is_(True),
        )
        .order_by(FinancialAccount.id.asc())
        .first()
    )

    if primary_account:
        return primary_account.id

    raise ValidationDomainError(
        "Nao foi encontrada uma conta vinculada ao cartao e nem uma conta principal ativa."
    )


def _build_invoice_description(card_invoice: CardInvoice) -> str:
    card_name = card_invoice.card.name
    reference_month_str = card_invoice.reference_month.strftime("%m/%Y")
    return f"Fatura Cartao {card_name} - {reference_month_str}"


def _get_or_create_invoice_category(db: Session, id_user: int) -> CategoryTransaction:
    category = (
        db.query(CategoryTransaction)
        .filter(
            CategoryTransaction.id_user == id_user,
            or_(
                CategoryTransaction.name.ilike("%fatura%"),
                CategoryTransaction.name.ilike("%cartao%"),
            ),
        )
        .order_by(CategoryTransaction.id.asc())
        .first()
    )

    if category:
        return category

    category = CategoryTransaction(id_user=id_user, name="Fatura Cartao")
    db.add(category)
    db.flush()
    return category


def create_invoice_account_transaction(
    db: Session, card_invoice: CardInvoice
) -> AccountTransaction:
    id_financial_account = _get_account_for_invoice(db, card_invoice)
    category = _get_or_create_invoice_category(db, card_invoice.id_user)

    account_transaction = AccountTransaction(
        id_user=card_invoice.id_user,
        id_financial_account=id_financial_account,
        id_category_transaction=category.id,
        id_merchant_name=None,
        id_loan_recipient=None,
        transaction_type=TransactionTypeEnum.expense,
        description=_build_invoice_description(card_invoice),
        purchase_date=card_invoice.due_date,
        payment_date=card_invoice.due_date,
        value=float(card_invoice.total_amount or 0.0),
        is_paid=(card_invoice.status == CardInvoiceStatusEnum.PAID),
        is_recurring=False,
        recurrence_frequency=None,
        recurrence_enabled=False,
        recurrence_group_id=None,
        recurrence_parent_id=None,
    )

    db.add(account_transaction)
    db.flush()
    card_invoice.id_account_transaction = account_transaction.id

    logger.info(
        "Created account transaction %s for invoice %s",
        account_transaction.id,
        card_invoice.id,
    )

    return account_transaction


def update_invoice_account_transaction(
    db: Session, card_invoice: CardInvoice
) -> AccountTransaction | None:
    if not card_invoice.id_account_transaction:
        return None

    account_transaction = (
        db.query(AccountTransaction)
        .filter(AccountTransaction.id == card_invoice.id_account_transaction)
        .first()
    )

    if not account_transaction:
        return None

    account_transaction.id_financial_account = _get_account_for_invoice(
        db, card_invoice
    )
    account_transaction.description = _build_invoice_description(card_invoice)
    account_transaction.purchase_date = card_invoice.due_date
    account_transaction.payment_date = card_invoice.due_date
    account_transaction.value = float(card_invoice.total_amount or 0.0)
    account_transaction.is_paid = card_invoice.status == CardInvoiceStatusEnum.PAID

    return account_transaction


def delete_invoice_account_transaction(db: Session, card_invoice: CardInvoice) -> bool:
    if not card_invoice.id_account_transaction:
        return False

    account_transaction = (
        db.query(AccountTransaction)
        .filter(AccountTransaction.id == card_invoice.id_account_transaction)
        .first()
    )

    if not account_transaction:
        return False

    db.delete(account_transaction)

    return True


def sync_invoice_account_transaction(
    db: Session, card_invoice: CardInvoice
) -> AccountTransaction:
    existing = update_invoice_account_transaction(db, card_invoice)
    if existing is not None:
        return existing
    return create_invoice_account_transaction(db, card_invoice)


def validate_invoice_sync(db: Session, card_invoice: CardInvoice) -> bool:
    if not card_invoice.id_account_transaction:
        return False

    account_transaction = (
        db.query(AccountTransaction)
        .filter(AccountTransaction.id == card_invoice.id_account_transaction)
        .first()
    )

    if not account_transaction:
        raise ValidationDomainError(
            f"Inconsistência: Fatura {card_invoice.id} vinculada a transação inexistente "
            f"{card_invoice.id_account_transaction}"
        )

    if float(account_transaction.value or 0.0) != float(
        card_invoice.total_amount or 0.0
    ):
        return False

    is_paid_expected = card_invoice.status == CardInvoiceStatusEnum.PAID
    if bool(account_transaction.is_paid) != is_paid_expected:
        return False

    return True
