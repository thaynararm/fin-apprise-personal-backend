import logging
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Literal
from uuid import UUID
from sqlalchemy.orm import Session
from src.core.utils.normalize_text import normalize_display_text, normalize_text
from src.modules.financial_accounts import schemas
from src.core.exceptions.domain import ValidationDomainError
from src.modules.financial_accounts import repository
from src.modules.merchants import repository as merchants_repository
from src.modules.loan_recipients import repository as loan_recipients_repository
from src.modules.financial_accounts.model import (
    FinancialAccount,
    AccountTransaction,
    AccountTransfer,
)
from src.modules.financial_accounts.schemas import (
    FinancialAccountCreate,
    FinancialAccountUpdate,
)
from src.models.shared.bank_names import BankNames
from src.models.shared.category_transaction import CategoryTransaction
from src.models.shared.enums import TransactionTypeEnum
from src.modules.users.model import User

logger = logging.getLogger(__name__)
RECURRENCE_LOOKAHEAD_DAYS = 365


def _parse_optional_date_filter(raw_date: str | None, field_name: str) -> date | None:
    if raw_date is None:
        return None

    cleaned = raw_date.strip()
    if not cleaned:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    raise ValidationDomainError(f"Invalid {field_name}. Use YYYY-MM-DD or DD/MM/YYYY")


def _get_current_month_date_range() -> tuple[date, date]:
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    end_of_month = date(today.year, today.month, monthrange(today.year, today.month)[1])
    return start_of_month, end_of_month


def _add_months(base_date: date, months: int) -> date:
    year = base_date.year + (base_date.month - 1 + months) // 12
    month = (base_date.month - 1 + months) % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _next_date(base_date: date, frequency) -> date:
    if frequency == "daily":
        return base_date + timedelta(days=1)
    if frequency == "weekly":
        return base_date + timedelta(days=7)
    if frequency == "biweekly":
        return base_date + timedelta(days=14)
    if frequency == "monthly":
        return _add_months(base_date, 1)
    if frequency == "bimonthly":
        return _add_months(base_date, 2)
    if frequency == "quarterly":
        return _add_months(base_date, 3)
    if frequency == "semiannual":
        return _add_months(base_date, 6)
    if frequency == "annual":
        return _add_months(base_date, 12)

    raise ValidationDomainError("Invalid recurrence frequency")


def _generate_recurrence_until_horizon(
    db: Session,
    recurrence_root: AccountTransaction,
) -> list[AccountTransaction]:
    if not recurrence_root.recurrence_enabled:
        return []

    if (
        not recurrence_root.recurrence_group_id
        or not recurrence_root.recurrence_frequency
    ):
        return []

    last_occurrence = repository.get_last_recurrence_occurrence(
        db,
        recurrence_group_id=recurrence_root.recurrence_group_id,
    )
    if not last_occurrence:
        return []

    horizon = date.today() + timedelta(days=RECURRENCE_LOOKAHEAD_DAYS)

    next_purchase = _next_date(
        last_occurrence.purchase_date,
        recurrence_root.recurrence_frequency.value,
    )
    next_payment = _next_date(
        last_occurrence.payment_date,
        recurrence_root.recurrence_frequency.value,
    )

    rows: list[dict[str, object]] = []
    while next_purchase <= horizon:
        rows.append(
            {
                "id_user": recurrence_root.id_user,
                "id_financial_account": recurrence_root.id_financial_account,
                "id_category_transaction": recurrence_root.id_category_transaction,
                "id_merchant_name": recurrence_root.id_merchant_name,
                "transaction_type": recurrence_root.transaction_type,
                "description": recurrence_root.description,
                "purchase_date": next_purchase,
                "payment_date": next_payment,
                "value": recurrence_root.value,
                "is_paid": False,
                "is_recurring": True,
                "recurrence_frequency": recurrence_root.recurrence_frequency,
                "recurrence_enabled": True,
                "recurrence_group_id": recurrence_root.recurrence_group_id,
                "recurrence_parent_id": recurrence_root.id,
            }
        )

        next_purchase = _next_date(
            next_purchase,
            recurrence_root.recurrence_frequency.value,
        )
        next_payment = _next_date(
            next_payment,
            recurrence_root.recurrence_frequency.value,
        )

    if not rows:
        return []

    return repository.create_account_transactions_batch(db, rows)


def _ensure_recurring_transactions_generated(
    db: Session,
    db_account: FinancialAccount,
) -> None:
    recurrence_roots = repository.list_active_recurrence_roots_by_account(
        db,
        id_financial_account=db_account.id,
    )

    for recurrence_root in recurrence_roots:
        _generate_recurrence_until_horizon(db, recurrence_root)


def _resolve_recurrence_root(
    db: Session,
    db_transaction: AccountTransaction,
) -> AccountTransaction | None:
    if db_transaction.is_recurring and db_transaction.recurrence_parent_id is None:
        return db_transaction

    if db_transaction.recurrence_parent_id is None:
        return None

    return repository.get_account_transaction_by_id(
        db, db_transaction.recurrence_parent_id
    )


def _get_or_create_initial_balance_category(
    db: Session,
    id_user: int,
) -> CategoryTransaction:
    normalized_target = normalize_text("saldo inicial")

    user_categories = (
        db.query(CategoryTransaction)
        .filter(
            CategoryTransaction.id_user == id_user,
            CategoryTransaction.type == TransactionTypeEnum.income,
        )
        .all()
    )
    for category in user_categories:
        if normalize_text(category.name) == normalized_target:
            return category

    shared_categories = (
        db.query(CategoryTransaction)
        .filter(
            CategoryTransaction.id_user.is_(None),
            CategoryTransaction.type == TransactionTypeEnum.income,
        )
        .all()
    )
    for category in shared_categories:
        if normalize_text(category.name) == normalized_target:
            return category

    created_category = CategoryTransaction(
        id_user=id_user,
        name="saldo inicial",
        description="Categoria para registrar o saldo inicial da conta",
        type=TransactionTypeEnum.income,
    )
    db.add(created_category)
    db.flush()

    return created_category


# ------------------
# Financial Account Model
# ------------------


def create_financial_account(
    db: Session,
    payload: FinancialAccountCreate,
    current_user: User,
) -> FinancialAccount:
    normalized_name = payload.name.strip()

    if not normalized_name:
        raise ValidationDomainError("Account name cannot be empty")

    id_bank_name: int | None = None
    if payload.id_bank_name is not None:
        bank = (
            db.query(BankNames).filter(BankNames.name == payload.id_bank_name).first()
        )
        if not bank:
            raise ValidationDomainError("Bank not found")
        id_bank_name = bank.id

    if payload.is_primary_bank:
        repository.clear_primary_bank_for_user(db, id_user=current_user.id)

    db_account = repository.create_financial_account(
        db,
        id_user=current_user.id,
        name=normalized_name,
        account_type=payload.account_type,
        is_active=payload.is_active,
        is_primary_bank=payload.is_primary_bank,
        id_bank_name=id_bank_name,
        overdraft_limit=payload.overdraft_limit,
    )

    logger.info(
        "Financial account created with uuid: %s for user uuid: %s",
        db_account.uuid,
        current_user.uuid,
    )

    initial_balance_category = _get_or_create_initial_balance_category(
        db,
        current_user.id,
    )
    initial_balance_payload = schemas.AccountTransactionCreate(
        uuid_category_transaction=initial_balance_category.uuid,
        transaction_type="income",
        description="Saldo inicial",
        purchase_date=payload.initial_balance_date,
        payment_date=payload.initial_balance_date,
        value=payload.initial_balance,
        is_paid=True,
    )

    create_account_transaction(
        db,
        db_account,
        initial_balance_payload,
        current_user,
    )

    return db_account


def get_financial_account_by_uuid(
    db: Session,
    uuid_financial_account: UUID,
) -> FinancialAccount | None:
    return repository.get_financial_account_by_uuid(db, uuid_financial_account)


def list_financial_accounts_by_user(
    db: Session,
    current_user: User,
    *,
    skip: int = 0,
    limit: int = 100,
) -> list[FinancialAccount]:
    return repository.list_financial_accounts_by_user(
        db,
        id_user=current_user.id,
        skip=skip,
        limit=limit,
    )


def update_financial_account(
    db: Session,
    db_account: FinancialAccount,
    payload: FinancialAccountUpdate,
) -> FinancialAccount:
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise ValidationDomainError("No fields provided for update")

    if "name" in update_data:
        normalized_name = update_data["name"].strip()

        if not normalized_name:
            raise ValidationDomainError("Account name cannot be empty")

        update_data["name"] = normalized_name

    if update_data.get("is_primary_bank") is True:
        repository.clear_primary_bank_for_user(db, id_user=db_account.id_user)

    updated_account = repository.update_financial_account(db, db_account, **update_data)

    logger.info("Financial account updated with uuid: %s", updated_account.uuid)

    return updated_account


# ------------------
# Account Transactions Models
# ------------------


def create_account_transaction(
    db: Session,
    db_account: FinancialAccount,
    payload: schemas.AccountTransactionCreate,
    current_user: User,
):
    # Valida se a categoria de transação existe e pertence ao usuário ou é global (id_user is null)
    category = (
        db.query(CategoryTransaction)
        .filter(CategoryTransaction.uuid == payload.uuid_category_transaction)
        .first()
    )
    if not category:
        raise ValidationDomainError("Category transaction not found")

    if category.id_user is not None and category.id_user != current_user.id:
        raise ValidationDomainError("A categoria informada não pertence ao usuário.")

    # Normaliza e valida o nome do estabelecimento, criando o registro de merchant caso necessário
    id_merchant_name: int | None = None
    if payload.merchant_name is not None:
        db_merchant = merchants_repository.get_or_create_merchant_by_name(
            db,
            current_user.id,
            normalize_text(payload.merchant_name),
            normalize_display_text(payload.merchant_name),
        )
        id_merchant_name = db_merchant.id

    # Normaliza e valida o nome do destinatário do empréstimo, criando o registro de loan recipient caso necessário
    id_loan_recipient: int | None = None
    if payload.loan_recipient_name is not None:
        if normalize_text(category.name) not in (
            "emprestimo",
            "emprestimos",
            "credito",
            "amortizacao",
        ):
            raise ValidationDomainError(
                "loan_recipient_name só pode ser informado quando a categoria for 'Empréstimo'"
            )

        db_recipient = loan_recipients_repository.get_or_create_loan_recipient_by_name(
            db,
            current_user.id,
            normalize_text(payload.loan_recipient_name),
            normalize_display_text(payload.loan_recipient_name),
        )
        id_loan_recipient = db_recipient.id

    # Cria a transação associada à conta financeira, categoria, merchant e destinatário de empréstimo (se aplicável)
    created_transaction = repository.create_account_transaction(
        db,
        db_account,
        payload,
        current_user,
        id_category_transaction=category.id,
        id_merchant_name=id_merchant_name,
        id_loan_recipient=id_loan_recipient,
    )

    # Se a transação for marcada como recorrente já na criação, gera o grupo de recorrência e as futuras ocorrências
    if payload.is_recurring:
        recurrence_group_id = uuid.uuid4()
        created_transaction = repository.update_account_transaction(
            db,
            created_transaction,
            is_recurring=True,
            recurrence_frequency=payload.recurrence_frequency,
            recurrence_enabled=True,
            recurrence_group_id=recurrence_group_id,
            recurrence_parent_id=None,
        )

        _generate_recurrence_until_horizon(db, created_transaction)

    return created_transaction


def update_account_transaction(
    db: Session,
    db_transaction: AccountTransaction,
    payload: schemas.AccountTransactionUpdate,
    current_user: User,
) -> AccountTransaction:
    # Extrai os campos a serem atualizados do payload, ignorando os que não foram informados (exclude_unset=True)
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise ValidationDomainError("No fields provided for update")

    # Valida se a transação pertence ao usuário antes de permitir qualquer atualização
    if "uuid_financial_account" in update_data:
        account = repository.get_financial_account_by_uuid(
            db,
            update_data["uuid_financial_account"],
        )
        if not account:
            raise ValidationDomainError("Financial account not found")
        if account.id_user != current_user.id:
            raise ValidationDomainError("You can only use your own financial account")
        update_data["id_financial_account"] = account.id
        update_data.pop("uuid_financial_account")

    # Valida se a categoria de transação existe e pertence ao usuário ou é global (id_user is null)
    if "uuid_category_transaction" in update_data:
        category = (
            db.query(CategoryTransaction)
            .filter(
                CategoryTransaction.uuid == update_data["uuid_category_transaction"]
            )
            .first()
        )
        if not category:
            raise ValidationDomainError("Category transaction not found")
        if category.id_user is not None and category.id_user != current_user.id:
            raise ValidationDomainError(
                "You can only use your own category transaction"
            )
        update_data["id_category_transaction"] = category.id
        update_data.pop("uuid_category_transaction")

    # Normaliza e valida o nome do estabelecimento, criando o registro de merchant caso necessário
    if "merchant_name" in update_data:
        merchant_name = update_data.pop("merchant_name")
        if merchant_name is None:
            update_data["id_merchant_name"] = None
        else:
            db_merchant = merchants_repository.get_or_create_merchant_by_name(
                db,
                current_user.id,
                normalize_text(merchant_name),
                normalize_display_text(merchant_name),
            )
            update_data["id_merchant_name"] = db_merchant.id

    # Normaliza e valida o nome do destinatário do empréstimo, criando o registro de loan recipient caso necessário
    if "loan_recipient_name" in update_data:

        loan_recipient_name = update_data.pop("loan_recipient_name")
        if loan_recipient_name is None:
            update_data["id_loan_recipient"] = None
        else:
            if "id_category_transaction" in update_data:
                resolved_category = (
                    db.query(CategoryTransaction)
                    .filter(
                        CategoryTransaction.id == update_data["id_category_transaction"]
                    )
                    .first()
                )
            else:
                resolved_category = (
                    db.query(CategoryTransaction)
                    .filter(
                        CategoryTransaction.id == db_transaction.id_category_transaction
                    )
                    .first()
                )

            if resolved_category and normalize_text(resolved_category.name) not in (
                "emprestimo",
                "emprestimos",
                "credito",
                "amortizacao",
            ):
                raise ValidationDomainError(
                    "loan_recipient_name só pode ser informado quando a categoria for 'Empréstimo'"
                )

            db_recipient = (
                loan_recipients_repository.get_or_create_loan_recipient_by_name(
                    db,
                    current_user.id,
                    normalize_text(loan_recipient_name),
                    normalize_display_text(loan_recipient_name),
                )
            )
            update_data["id_loan_recipient"] = db_recipient.id

    # Gerencia as atualizações relacionadas à recorrência
    recurrence_enabled = update_data.pop("recurrence_enabled", None)
    recurrence_frequency = update_data.pop("recurrence_frequency", None)

    # Se a transação já era recorrente e está sendo desmarcada como recorrente ou tendo a frequência alterada,
    # deleta os filhos futuros da recorrência a partir da data da compra da transação atual,
    # mantendo os filhos passados para preservar o histórico e os registros futuros que já venceram
    if db_transaction.is_recurring:
        recurrence_root = _resolve_recurrence_root(db, db_transaction)
        if not recurrence_root:
            raise ValidationDomainError(
                "This transaction is not part of a recurring series"
            )

        recurrence_updates: dict[str, object] = {}
        if recurrence_enabled is not None:
            recurrence_updates["recurrence_enabled"] = recurrence_enabled

        if recurrence_frequency is not None:
            recurrence_updates["recurrence_frequency"] = recurrence_frequency

        # Atualiza o registro raiz da recorrência para manter as configurações de recorrência consistentes para os filhos existentes
        recurrence_root = repository.update_account_transaction(
            db,
            recurrence_root,
            **recurrence_updates,
        )

        # Se a recorrência foi desabilitada ou teve a frequência alterada, os filhos futuros serão deletados
        repository.delete_future_recurrence_children(
            db,
            recurrence_group_id=recurrence_root.recurrence_group_id,
            from_purchase_date=db_transaction.purchase_date,
        )

        # Se a recorrência ainda estiver habilitada após a atualização, gera novas ocorrências futuras com base na nova configuração
        if recurrence_root.recurrence_enabled:
            _generate_recurrence_until_horizon(db, recurrence_root)

        # Recarrega a transação após possíveis alterações na recorrência para garantir que o estado mais atualizado seja retornado
        db_transaction = repository.get_account_transaction_by_uuid(
            db, db_transaction.uuid
        )

    # Se a transação não era recorrente mas está sendo marcada como recorrente, gera o grupo de recorrência e futuras ocorrências
    if db_transaction.is_recurring is False and payload.is_recurring is True:
        recurrence_group_id = uuid.uuid4()

        # Atualiza a transação atual para ser o registro raiz da recorrência com as configurações de recorrência
        created_transaction = repository.update_account_transaction(
            db,
            db_transaction,
            is_recurring=True,
            recurrence_frequency=payload.recurrence_frequency,
            recurrence_enabled=True,
            recurrence_group_id=recurrence_group_id,
            recurrence_parent_id=None,
        )

        # Gerar futuras ocorrências com base na configuração de recorrência a partir da transação atualizada, que agora é o registro raiz
        _generate_recurrence_until_horizon(db, created_transaction)

        # Recarrega a transação após possíveis alterações na recorrência para garantir que o estado mais atualizado seja retornado
        db_transaction = repository.get_account_transaction_by_uuid(
            db, db_transaction.uuid
        )

    updated_transaction = repository.update_account_transaction(
        db, db_transaction, **update_data
    )

    logger.info("Account transaction updated with uuid: %s", updated_transaction.uuid)

    return updated_transaction


def list_account_transactions(
    db: Session,
    db_account: FinancialAccount,
    *,
    skip: int = 0,
    limit: int = 100,
    description: str | None = None,
    category: str | None = None,
    order_by: list[str] | None = None,
) -> list[AccountTransaction]:
    _ensure_recurring_transactions_generated(db, db_account)

    return repository.list_account_transactions(
        db,
        id_financial_account=db_account.id,
        skip=skip,
        limit=limit,
        description=description,
        category=category,
        order_by=order_by,
    )


def get_account_transaction_by_uuid(
    db: Session,
    transaction_uuid: UUID,
) -> AccountTransaction | None:
    return repository.get_account_transaction_by_uuid(db, transaction_uuid)


def delete_account_transaction(
    db: Session,
    db_transaction: AccountTransaction,
) -> None:
    repository.delete_account_transaction(db, db_transaction)

    logger.info("Account transaction deleted with uuid: %s", db_transaction.uuid)


def _get_or_create_transfer_category(
    db: Session,
    id_user: int,
    transaction_type: TransactionTypeEnum,
) -> CategoryTransaction:
    normalized_target = normalize_text("transferencia entre contas")

    user_categories = (
        db.query(CategoryTransaction)
        .filter(
            CategoryTransaction.id_user == id_user,
            CategoryTransaction.type == transaction_type,
        )
        .all()
    )
    for category in user_categories:
        if normalize_text(category.name) == normalized_target:
            return category

    shared_categories = (
        db.query(CategoryTransaction)
        .filter(
            CategoryTransaction.id_user.is_(None),
            CategoryTransaction.type == transaction_type,
        )
        .all()
    )
    for category in shared_categories:
        if normalize_text(category.name) == normalized_target:
            return category

    created_category = CategoryTransaction(
        id_user=id_user,
        name="Transferencia entre contas",
        description="Categoria para registrar transferencias entre contas",
        type=transaction_type,
    )
    db.add(created_category)
    db.flush()

    return created_category


def _build_transfer_transaction_description(
    transfer_description: str | None,
    origin_account: FinancialAccount,
    destination_account: FinancialAccount,
    *,
    is_origin_transaction: bool,
) -> str:
    if transfer_description is not None and transfer_description.strip():
        return transfer_description.strip()

    if is_origin_transaction:
        return f"Transfer to {destination_account.name}"

    return f"Transfer from {origin_account.name}"


def _ensure_transfer_mirror_transactions(
    db: Session,
    db_transfer: AccountTransfer,
    current_user: User,
    *,
    origin_account: FinancialAccount,
    destination_account: FinancialAccount,
    transfer_date: date,
    amount: float,
    description: str | None,
) -> tuple[AccountTransaction, AccountTransaction]:
    income_category = _get_or_create_transfer_category(
        db,
        current_user.id,
        TransactionTypeEnum.income,
    )
    expense_category = _get_or_create_transfer_category(
        db,
        current_user.id,
        TransactionTypeEnum.expense,
    )

    origin_transaction = None
    if db_transfer.id_origin_transaction is not None:
        origin_transaction = repository.get_account_transaction_by_id(
            db,
            db_transfer.id_origin_transaction,
        )

    destination_transaction = None
    if db_transfer.id_destination_transaction is not None:
        destination_transaction = repository.get_account_transaction_by_id(
            db,
            db_transfer.id_destination_transaction,
        )

    origin_description = _build_transfer_transaction_description(
        description,
        origin_account,
        destination_account,
        is_origin_transaction=True,
    )
    destination_description = _build_transfer_transaction_description(
        description,
        origin_account,
        destination_account,
        is_origin_transaction=False,
    )

    if origin_transaction is None or destination_transaction is None:
        created_transactions = repository.create_account_transactions_batch(
            db,
            [
                {
                    "id_user": current_user.id,
                    "id_financial_account": origin_account.id,
                    "id_category_transaction": expense_category.id,
                    "transaction_type": TransactionTypeEnum.expense,
                    "description": origin_description,
                    "purchase_date": transfer_date,
                    "payment_date": transfer_date,
                    "value": amount,
                    "is_paid": True,
                    "is_recurring": False,
                    "recurrence_frequency": None,
                    "recurrence_enabled": False,
                    "recurrence_group_id": None,
                    "recurrence_parent_id": None,
                },
                {
                    "id_user": current_user.id,
                    "id_financial_account": destination_account.id,
                    "id_category_transaction": income_category.id,
                    "transaction_type": TransactionTypeEnum.income,
                    "description": destination_description,
                    "purchase_date": transfer_date,
                    "payment_date": transfer_date,
                    "value": amount,
                    "is_paid": True,
                    "is_recurring": False,
                    "recurrence_frequency": None,
                    "recurrence_enabled": False,
                    "recurrence_group_id": None,
                    "recurrence_parent_id": None,
                },
            ],
            auto_commit=False,
        )

        origin_transaction = created_transactions[0]
        destination_transaction = created_transactions[1]

    else:
        if (
            origin_transaction.id_user != current_user.id
            or destination_transaction.id_user != current_user.id
        ):
            raise ValidationDomainError("Transfer transactions do not belong to user")

        origin_transaction = repository.update_account_transaction(
            db,
            origin_transaction,
            auto_commit=False,
            id_financial_account=origin_account.id,
            id_category_transaction=expense_category.id,
            transaction_type=TransactionTypeEnum.expense,
            description=origin_description,
            purchase_date=transfer_date,
            payment_date=transfer_date,
            value=amount,
            is_paid=True,
            is_recurring=False,
            recurrence_frequency=None,
            recurrence_enabled=False,
            recurrence_group_id=None,
            recurrence_parent_id=None,
        )

        destination_transaction = repository.update_account_transaction(
            db,
            destination_transaction,
            auto_commit=False,
            id_financial_account=destination_account.id,
            id_category_transaction=income_category.id,
            transaction_type=TransactionTypeEnum.income,
            description=destination_description,
            purchase_date=transfer_date,
            payment_date=transfer_date,
            value=amount,
            is_paid=True,
            is_recurring=False,
            recurrence_frequency=None,
            recurrence_enabled=False,
            recurrence_group_id=None,
            recurrence_parent_id=None,
        )

    repository.update_account_transfer(
        db,
        db_transfer,
        auto_commit=False,
        id_origin_transaction=origin_transaction.id,
        id_destination_transaction=destination_transaction.id,
    )

    return origin_transaction, destination_transaction


# ------------------
# Account Transfers Models
# ------------------


def create_account_transfer(
    db: Session,
    payload: schemas.AccountTransferCreate,
    current_user: User,
) -> AccountTransfer:
    if (
        payload.origin_uuid_financial_account
        == payload.destination_uuid_financial_account
    ):
        raise ValidationDomainError("Origin and destination accounts must be different")

    if payload.amount <= 0:
        raise ValidationDomainError("Transfer amount must be greater than zero")

    origin_account = repository.get_financial_account_by_uuid(
        db,
        payload.origin_uuid_financial_account,
    )
    if not origin_account:
        raise ValidationDomainError("Origin account not found")

    destination_account = repository.get_financial_account_by_uuid(
        db,
        payload.destination_uuid_financial_account,
    )
    if not destination_account:
        raise ValidationDomainError("Destination account not found")

    if origin_account.id_user != current_user.id:
        raise ValidationDomainError("You can only transfer from your own account")

    if destination_account.id_user != current_user.id:
        raise ValidationDomainError("You can only transfer to your own account")

    try:
        created_transfer = repository.create_account_transfer(
            db,
            id_user=current_user.id,
            id_origin_account=origin_account.id,
            id_destination_account=destination_account.id,
            transfer_date=payload.transfer_date,
            amount=payload.amount,
            description=payload.description,
            auto_commit=False,
        )

        _ensure_transfer_mirror_transactions(
            db,
            created_transfer,
            current_user,
            origin_account=origin_account,
            destination_account=destination_account,
            transfer_date=payload.transfer_date,
            amount=payload.amount,
            description=payload.description,
        )
        db.commit()
        db.refresh(created_transfer)
    except Exception:
        db.rollback()
        raise

    logger.info("Account transfer created with uuid: %s", created_transfer.uuid)

    return created_transfer


def get_account_transfer_by_uuid(
    db: Session,
    transfer_uuid: UUID,
) -> AccountTransfer | None:
    return repository.get_account_transfer_by_uuid(db, transfer_uuid)


def update_account_transfer(
    db: Session,
    db_transfer: AccountTransfer,
    payload: schemas.AccountTransferUpdate,
    current_user: User,
) -> AccountTransfer:
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise ValidationDomainError("No fields provided for update")

    if db_transfer.id_user != current_user.id:
        raise ValidationDomainError("You can only edit your own transfer")

    fields_to_update: dict[str, object] = {}

    resolved_origin_account = repository.get_financial_account_by_id(
        db,
        db_transfer.id_origin_account,
    )
    if not resolved_origin_account:
        raise ValidationDomainError("Origin account not found")

    if "origin_uuid_financial_account" in update_data:
        origin_uuid_financial_account = update_data["origin_uuid_financial_account"]
        origin_account = repository.get_financial_account_by_uuid(
            db, origin_uuid_financial_account
        )
        if not origin_account:
            raise ValidationDomainError("Origin account not found")
        if origin_account.id_user != current_user.id:
            raise ValidationDomainError("You can only transfer from your own account")
        resolved_origin_account = origin_account
        fields_to_update["id_origin_account"] = resolved_origin_account.id

    resolved_destination_account = repository.get_financial_account_by_id(
        db,
        db_transfer.id_destination_account,
    )
    if not resolved_destination_account:
        raise ValidationDomainError("Destination account not found")

    if "destination_uuid_financial_account" in update_data:
        destination_uuid_financial_account = update_data[
            "destination_uuid_financial_account"
        ]
        destination_account = repository.get_financial_account_by_uuid(
            db,
            destination_uuid_financial_account,
        )
        if not destination_account:
            raise ValidationDomainError("Destination account not found")
        if destination_account.id_user != current_user.id:
            raise ValidationDomainError("You can only transfer to your own account")
        resolved_destination_account = destination_account
        fields_to_update["id_destination_account"] = resolved_destination_account.id

    if resolved_origin_account.id == resolved_destination_account.id:
        raise ValidationDomainError("Origin and destination accounts must be different")

    resolved_amount = db_transfer.amount
    if "amount" in update_data:
        amount = update_data["amount"]
        if amount <= 0:
            raise ValidationDomainError("Transfer amount must be greater than zero")
        resolved_amount = amount
        fields_to_update["amount"] = resolved_amount

    resolved_transfer_date = db_transfer.transfer_date
    if "transfer_date" in update_data:
        resolved_transfer_date = update_data["transfer_date"]
        fields_to_update["transfer_date"] = resolved_transfer_date

    resolved_description = db_transfer.description
    if "description" in update_data:
        resolved_description = update_data["description"]
        fields_to_update["description"] = resolved_description

    try:
        updated_transfer = repository.update_account_transfer(
            db,
            db_transfer,
            auto_commit=False,
            **fields_to_update,
        )

        _ensure_transfer_mirror_transactions(
            db,
            updated_transfer,
            current_user,
            origin_account=resolved_origin_account,
            destination_account=resolved_destination_account,
            transfer_date=resolved_transfer_date,
            amount=resolved_amount,
            description=resolved_description,
        )
        db.commit()
        db.refresh(updated_transfer)
    except Exception:
        db.rollback()
        raise

    logger.info("Account transfer updated with uuid: %s", updated_transfer.uuid)

    return updated_transfer


def list_user_movements_from_active_accounts(
    db: Session,
    current_user: User,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    transaction_type: Literal["income", "expense"] | None = None,
    description: str | None = None,
    category_uuids: list[UUID] | None = None,
    account_uuids: list[UUID] | None = None,
    is_paid: bool | None = None,
    value_text: str | None = None,
    merchant_name: str | None = None,
    order_by: list[str] | None = None,
) -> list[AccountTransaction]:

    return repository.list_user_movements_from_active_accounts(
        db,
        id_user=current_user.id,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        description=description,
        category_uuids=category_uuids,
        account_uuids=account_uuids,
        is_paid=is_paid,
        value_text=value_text,
        merchant_name=merchant_name,
        order_by=order_by,
    )


def get_user_financial_summary_from_active_accounts(
    db: Session,
    current_user: User,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    transaction_type: list[Literal["income", "expense"]] | None = None,
    description: str | None = None,
    category_uuids: list[UUID] | None = None,
    account_uuids: list[UUID] | None = None,
    is_paid: bool | None = None,
    value_text: str | None = None,
    merchant_name: str | None = None,
) -> tuple[dict[str, float], dict[str, float] | None]:
    parsed_start_date = _parse_optional_date_filter(start_date, "start_date")
    parsed_end_date = _parse_optional_date_filter(end_date, "end_date")

    if (
        parsed_start_date is not None
        and parsed_end_date is not None
        and parsed_start_date > parsed_end_date
    ):
        raise ValidationDomainError("start_date cannot be greater than end_date")

    return repository.get_user_financial_summary_from_active_accounts(
        db,
        id_user=current_user.id,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        transaction_type=transaction_type,
        description=description,
        category_uuids=category_uuids,
        account_uuids=account_uuids,
        is_paid=is_paid,
        value_text=value_text,
        merchant_name=merchant_name,
    )
