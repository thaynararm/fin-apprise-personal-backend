from sqlalchemy.orm import Session, aliased, joinedload
from sqlalchemy import String, and_, case, cast, or_, func, select
from datetime import date
from typing import Literal
from uuid import UUID
from src.modules.financial_accounts import schemas
from src.modules.users.model import User
from src.models.shared.category_transaction import CategoryTransaction
from src.modules.merchants.model import MerchantNames
from src.modules.financial_accounts.model import (
    FinancialAccount,
    AccountTypeEnum,
    AccountTransaction,
    AccountTransfer,
)
from src.models.shared.enums import TransactionTypeEnum

# ------------------
# Financial Account Model
# ------------------


def create_financial_account(
    db: Session,
    *,
    id_user: int,
    name: str,
    account_type: AccountTypeEnum,
    is_active: bool = True,
    is_primary_bank: bool = False,
    id_bank_name: int | None = None,
    overdraft_limit: float | None = None,
) -> FinancialAccount:
    db_account = FinancialAccount(
        id_user=id_user,
        name=name,
        account_type=account_type,
        is_active=is_active,
        is_primary_bank=is_primary_bank,
        id_bank_name=id_bank_name,
        overdraft_limit=overdraft_limit,
    )

    db.add(db_account)
    db.commit()
    db.refresh(db_account)

    return db_account


def clear_primary_bank_for_user(db: Session, *, id_user: int) -> None:
    (
        db.query(FinancialAccount)
        .filter(FinancialAccount.id_user == id_user)
        .update({"is_primary_bank": False}, synchronize_session=False)
    )


def get_financial_account_by_uuid(
    db: Session,
    uuid_financial_account: UUID,
) -> FinancialAccount | None:
    return (
        db.query(FinancialAccount)
        .filter(FinancialAccount.uuid == uuid_financial_account)
        .first()
    )


def get_financial_account_by_id(
    db: Session,
    id_financial_account: int,
) -> FinancialAccount | None:
    return (
        db.query(FinancialAccount)
        .filter(FinancialAccount.id == id_financial_account)
        .first()
    )


def update_financial_account(
    db: Session,
    db_account: FinancialAccount,
    **fields,
) -> FinancialAccount:
    for key, value in fields.items():
        setattr(db_account, key, value)

    db.commit()
    db.refresh(db_account)

    return db_account


def list_financial_accounts_by_user(
    db: Session,
    *,
    id_user: int,
    skip: int = 0,
    limit: int = 100,
) -> list[FinancialAccount]:
    return (
        db.query(FinancialAccount)
        .filter(FinancialAccount.id_user == id_user)
        .order_by(FinancialAccount.name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ------------------
# Account Transactions Models
# ------------------


def create_account_transaction(
    db: Session,
    db_account: FinancialAccount,
    payload: schemas.AccountTransactionCreate,
    current_user: User,
    id_category_transaction: int,
    id_merchant_name: int | None = None,
    id_loan_recipient: int | None = None,
    auto_commit: bool = True,
) -> AccountTransaction:
    db_transaction = AccountTransaction(
        id_user=current_user.id,
        id_financial_account=db_account.id,
        id_category_transaction=id_category_transaction,
        id_merchant_name=id_merchant_name,
        id_loan_recipient=id_loan_recipient,
        transaction_type=payload.transaction_type,
        description=payload.description,
        purchase_date=payload.purchase_date,
        payment_date=payload.payment_date,
        value=payload.value,
        is_paid=payload.is_paid,
    )
    db.add(db_transaction)
    if auto_commit:
        db.commit()
    else:
        db.flush()
    db.refresh(db_transaction)
    return db_transaction


def create_account_transactions_batch(
    db: Session,
    rows: list[dict[str, object]],
    auto_commit: bool = True,
) -> list[AccountTransaction]:
    db_transactions = [AccountTransaction(**row) for row in rows]

    db.add_all(db_transactions)
    if auto_commit:
        db.commit()
    else:
        db.flush()

    for transaction in db_transactions:
        db.refresh(transaction)

    return db_transactions


def list_account_transactions(
    db: Session,
    *,
    id_financial_account: int,
    skip: int = 0,
    limit: int = 100,
    description: str | None = None,
    category: str | None = None,
    order_by: list[str] | None = None,
) -> list[AccountTransaction]:
    order_by_fields = order_by or ["purchase_date"]

    query = (
        db.query(AccountTransaction)
        .options(
            joinedload(AccountTransaction.merchant_name),
            joinedload(AccountTransaction.category_transaction),
            joinedload(AccountTransaction.financial_account),
        )
        .join(
            FinancialAccount,
            AccountTransaction.id_financial_account == FinancialAccount.id,
        )
        .outerjoin(
            CategoryTransaction,
            AccountTransaction.id_category_transaction == CategoryTransaction.id,
        )
        .filter(AccountTransaction.id_financial_account == id_financial_account)
        .filter(
            or_(
                CategoryTransaction.name.is_(None),
                CategoryTransaction.name != "transferencia_entre_contas",
            )
        )
    )

    if description is not None and description.strip():
        query = query.filter(
            AccountTransaction.description.ilike(f"%{description.strip()}%")
        )

    if category is not None and category.strip():
        query = query.filter(CategoryTransaction.name.ilike(f"%{category.strip()}%"))

    order_by_mapping = {
        "purchase_date": AccountTransaction.purchase_date,
        "category": CategoryTransaction.name,
        "description": AccountTransaction.description,
        "account_name": FinancialAccount.name,
        "value": AccountTransaction.value,
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

    if not order_clauses:
        order_clauses.append(AccountTransaction.purchase_date.desc())

    return query.order_by(*order_clauses).offset(skip).limit(limit).all()


def get_account_transaction_by_uuid(
    db: Session,
    transaction_uuid: UUID,
) -> AccountTransaction | None:
    return (
        db.query(AccountTransaction)
        .options(joinedload(AccountTransaction.merchant_name))
        .filter(AccountTransaction.uuid == transaction_uuid)
        .first()
    )


def get_account_transaction_by_id(
    db: Session,
    transaction_id: int,
) -> AccountTransaction | None:
    return (
        db.query(AccountTransaction)
        .options(joinedload(AccountTransaction.merchant_name))
        .filter(AccountTransaction.id == transaction_id)
        .first()
    )


def list_active_recurrence_roots_by_account(
    db: Session,
    *,
    id_financial_account: int,
) -> list[AccountTransaction]:
    return (
        db.query(AccountTransaction)
        .filter(
            AccountTransaction.id_financial_account == id_financial_account,
            AccountTransaction.is_recurring.is_(True),
            AccountTransaction.recurrence_enabled.is_(True),
            AccountTransaction.recurrence_parent_id.is_(None),
        )
        .all()
    )


def get_last_recurrence_occurrence(
    db: Session,
    *,
    recurrence_group_id: UUID,
) -> AccountTransaction | None:
    return (
        db.query(AccountTransaction)
        .filter(AccountTransaction.recurrence_group_id == recurrence_group_id)
        .order_by(AccountTransaction.purchase_date.desc(), AccountTransaction.id.desc())
        .first()
    )


def delete_future_recurrence_children(
    db: Session,
    *,
    recurrence_group_id: UUID,
    from_purchase_date: date,
) -> None:
    (
        db.query(AccountTransaction)
        .filter(
            AccountTransaction.recurrence_group_id == recurrence_group_id,
            AccountTransaction.purchase_date > from_purchase_date,
            AccountTransaction.is_paid.is_(False),
        )
        .delete(synchronize_session=False)
    )
    db.commit()


def update_account_transaction(
    db: Session,
    db_transaction: AccountTransaction,
    auto_commit: bool = True,
    **fields,
) -> AccountTransaction:
    for key, value in fields.items():
        setattr(db_transaction, key, value)

    if auto_commit:
        db.commit()
    else:
        db.flush()
    db.refresh(db_transaction)

    return db_transaction


def delete_account_transaction(
    db: Session,
    db_transaction: AccountTransaction,
    auto_commit: bool = True,
) -> None:
    db.delete(db_transaction)
    if auto_commit:
        db.commit()
    else:
        db.flush()


# ------------------
# Account Transfers Models
# ------------------


def create_account_transfer(
    db: Session,
    *,
    id_user: int,
    id_origin_account: int,
    id_destination_account: int,
    id_origin_transaction: int | None = None,
    id_destination_transaction: int | None = None,
    transfer_date,
    amount: float,
    description: str | None = None,
    auto_commit: bool = True,
) -> AccountTransfer:
    db_transfer = AccountTransfer(
        id_user=id_user,
        id_origin_account=id_origin_account,
        id_destination_account=id_destination_account,
        id_origin_transaction=id_origin_transaction,
        id_destination_transaction=id_destination_transaction,
        transfer_date=transfer_date,
        amount=amount,
        description=description,
    )

    db.add(db_transfer)
    if auto_commit:
        db.commit()
    else:
        db.flush()
    db.refresh(db_transfer)

    return db_transfer


def get_account_transfer_by_uuid(
    db: Session,
    transfer_uuid: UUID,
) -> AccountTransfer | None:
    return (
        db.query(AccountTransfer).filter(AccountTransfer.uuid == transfer_uuid).first()
    )


def update_account_transfer(
    db: Session,
    db_transfer: AccountTransfer,
    auto_commit: bool = True,
    **fields,
) -> AccountTransfer:
    for key, value in fields.items():
        setattr(db_transfer, key, value)

    if auto_commit:
        db.commit()
    else:
        db.flush()
    db.refresh(db_transfer)

    return db_transfer


def delete_account_transfer(
    db: Session,
    db_transfer: AccountTransfer,
    auto_commit: bool = True,
) -> None:
    db.delete(db_transfer)
    if auto_commit:
        db.commit()
    else:
        db.flush()


def list_user_movements_from_active_accounts(
    db: Session,
    *,
    id_user: int,
    start_date: date | None = None,
    end_date: date | None = None,
    transaction_type: list[Literal["income", "expense", "transfer"]] | None = None,
    description: str | None = None,
    category_uuids: list[UUID] | None = None,
    account_uuids: list[UUID] | None = None,
    is_paid: bool | None = None,
    value_text: str | None = None,
    merchant_name: str | None = None,
    order_by: list[str] | None = None,
) -> list[AccountTransaction]:
    active_accounts_query = db.query(FinancialAccount.id).filter(
        FinancialAccount.id_user == id_user,
        FinancialAccount.is_active.is_(True),
    )

    if account_uuids:
        active_accounts_query = active_accounts_query.filter(
            FinancialAccount.uuid.in_(account_uuids)
        )

    active_account_ids = [row[0] for row in active_accounts_query.all()]

    if not active_account_ids:
        return []

    normalized_description = description.strip().lower() if description else None
    normalized_value_text = value_text.strip() if value_text else None
    normalized_merchant_name = merchant_name.strip().lower() if merchant_name else None

    category_ids: list[int] | None = None
    if category_uuids:
        category_ids = [
            row[0]
            for row in db.query(CategoryTransaction.id)
            .filter(
                CategoryTransaction.uuid.in_(category_uuids),
            )
            .all()
        ]

        if not category_ids:
            return []

    order_by_fields = order_by or ["purchase_date"]

    # Subquery: IDs das transações que são a ORIGEM de uma transferência (ficam visíveis, mas
    # terão transaction_type sobrescrito para "transfer" no pós-processamento)
    transfer_origin_ids_sq = (
        db.query(AccountTransfer.id_origin_transaction.label("transaction_id"))
        .filter(AccountTransfer.id_origin_transaction.isnot(None))
        .subquery()
    )

    # Subquery: IDs das transações que são o DESTINO de uma transferência (excluídas para evitar
    # duplicidade — a origem já representa a movimentação completa)
    transfer_destination_ids_sq = (
        db.query(AccountTransfer.id_destination_transaction.label("transaction_id"))
        .filter(AccountTransfer.id_destination_transaction.isnot(None))
        .subquery()
    )

    query = (
        db.query(AccountTransaction)
        .filter(AccountTransaction.id_financial_account.in_(active_account_ids))
        .options(
            joinedload(AccountTransaction.merchant_name),
            joinedload(AccountTransaction.category_transaction),
            joinedload(AccountTransaction.financial_account),
        )
        .join(
            FinancialAccount,
            AccountTransaction.id_financial_account == FinancialAccount.id,
        )
        .outerjoin(
            CategoryTransaction,
            AccountTransaction.id_category_transaction == CategoryTransaction.id,
        )
        .filter(
            ~AccountTransaction.id.in_(
                select(transfer_destination_ids_sq.c.transaction_id)
            )
        )
    )

    if start_date is not None:
        query = query.filter(AccountTransaction.purchase_date >= start_date)

    if end_date is not None:
        query = query.filter(AccountTransaction.purchase_date <= end_date)

    if transaction_type is not None:
        # No banco, origens de transferência são salvas com transaction_type="expense".
        # Remapeamento: "transfer" no filtro → origens de transferência (expense no banco);
        # "expense" no filtro → expenses reais (excluindo origens de transferência).
        include_transfers = "transfer" in transaction_type
        real_types = [t for t in transaction_type if t != "transfer"]

        conditions = []

        if real_types:
            if "expense" in real_types:
                other_real = [t for t in real_types if t != "expense"]
                if other_real:
                    conditions.append(
                        AccountTransaction.transaction_type.in_(other_real)
                    )
                # Expenses reais: exclui as que são origens de transferência
                conditions.append(
                    and_(
                        AccountTransaction.transaction_type == "expense",
                        ~AccountTransaction.id.in_(
                            select(transfer_origin_ids_sq.c.transaction_id)
                        ),
                    )
                )
            else:
                conditions.append(AccountTransaction.transaction_type.in_(real_types))

        if include_transfers:
            conditions.append(
                AccountTransaction.id.in_(
                    select(transfer_origin_ids_sq.c.transaction_id)
                )
            )

        if conditions:
            query = query.filter(
                or_(*conditions) if len(conditions) > 1 else conditions[0]
            )

    if normalized_description:
        query = query.filter(
            func.unaccent(func.lower(AccountTransaction.description)).ilike(
                f"%{normalized_description}%"
            )
        )

    if category_ids is not None:
        query = query.filter(
            AccountTransaction.id_category_transaction.in_(category_ids)
        )

    if is_paid is not None:
        query = query.filter(AccountTransaction.is_paid == is_paid)

    if normalized_value_text:
        query = query.filter(
            cast(AccountTransaction.value, String).ilike(f"%{normalized_value_text}%")
        )

    if normalized_merchant_name:
        query = query.join(
            MerchantNames,
            AccountTransaction.id_merchant_name == MerchantNames.id,
        ).filter(
            func.unaccent(func.lower(MerchantNames.name)).ilike(
                f"%{normalized_merchant_name}%"
            )
        )

    order_by_mapping = {
        "purchase_date": AccountTransaction.purchase_date,
        "category": CategoryTransaction.name,
        "description": AccountTransaction.description,
        "account_name": FinancialAccount.name,
        "value": AccountTransaction.value,
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

    if not order_clauses:
        order_clauses.append(AccountTransaction.purchase_date.desc())

    results = query.order_by(*order_clauses).all()

    # Pós-processamento: nas transações que são origem de transferência, sobrescreve
    # transaction_type para "transfer", uuid para o uuid da transferência e adiciona
    # uuid_destination_account com o uuid da conta destino.
    # Seguro pois a sessão usa autoflush=False e não há commit após essa função,
    # então os objetos não são persistidos com esses valores alterados.
    if results:
        result_ids = [t.id for t in results]
        DestinationAccount = aliased(FinancialAccount)
        transfer_by_origin_transaction_id = {
            row[0]: (row[1], row[2])
            for row in db.query(
                AccountTransfer.id_origin_transaction,
                AccountTransfer.uuid,
                DestinationAccount.uuid,
            )
            .join(
                DestinationAccount,
                AccountTransfer.id_destination_account == DestinationAccount.id,
            )
            .filter(
                AccountTransfer.id_origin_transaction.isnot(None),
                AccountTransfer.id_origin_transaction.in_(result_ids),
            )
            .all()
        }
        for transaction in results:
            transfer_info = transfer_by_origin_transaction_id.get(transaction.id)
            if transfer_info is not None:
                transfer_uuid, destination_account_uuid = transfer_info
                transaction.transaction_type = TransactionTypeEnum.transfer
                transaction.uuid = transfer_uuid
                transaction.uuid_destination_account = destination_account_uuid

    return results


def get_user_financial_summary_from_active_accounts(
    db: Session,
    *,
    id_user: int,
    start_date: date | None = None,
    end_date: date | None = None,
    transaction_type: list[Literal["income", "expense", "transfer"]] | None = None,
    description: str | None = None,
    category_uuids: list[UUID] | None = None,
    account_uuids: list[UUID] | None = None,
    is_paid: bool | None = None,
    value_text: str | None = None,
    merchant_name: str | None = None,
) -> tuple[dict[str, float], dict[str, float] | None]:
    active_accounts_query = db.query(FinancialAccount.id, FinancialAccount.uuid).filter(
        FinancialAccount.id_user == id_user,
        FinancialAccount.is_active.is_(True),
    )

    active_accounts = active_accounts_query.all()
    active_account_ids = [row[0] for row in active_accounts]

    has_filtered_filters = any(
        [
            bool(transaction_type),
            bool(description and description.strip()),
            bool(category_uuids),
            account_uuids is not None,
            is_paid is not None,
            bool(value_text and value_text.strip()),
            bool(merchant_name and merchant_name.strip()),
        ]
    )

    zero_totals = {
        "incomes": 0.0,
        "expenses": 0.0,
        "current_balance": 0.0,
        "provisioned_balance": 0.0,
    }

    if not active_account_ids:
        return zero_totals, zero_totals if has_filtered_filters else None

    normalized_description = description.strip().lower() if description else None
    normalized_value_text = value_text.strip() if value_text else None
    normalized_merchant_name = merchant_name.strip().lower() if merchant_name else None

    category_ids: list[int] | None = None
    if category_uuids:
        category_ids = [
            row[0]
            for row in db.query(CategoryTransaction.id)
            .filter(
                CategoryTransaction.id_user == id_user,
                CategoryTransaction.uuid.in_(category_uuids),
            )
            .all()
        ]

    def _aggregate_totals(base_query) -> dict[str, float]:
        income_sum, expense_sum, paid_income_sum, paid_expense_sum = (
            base_query.with_entities(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                AccountTransaction.transaction_type == "income",
                                AccountTransaction.value,
                            ),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                AccountTransaction.transaction_type == "expense",
                                AccountTransaction.value,
                            ),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    AccountTransaction.transaction_type == "income",
                                    AccountTransaction.is_paid.is_(True),
                                ),
                                AccountTransaction.value,
                            ),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    AccountTransaction.transaction_type == "expense",
                                    AccountTransaction.is_paid.is_(True),
                                ),
                                AccountTransaction.value,
                            ),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ),
            ).one()
        )

        incomes = float(income_sum or 0.0)
        expenses = float(expense_sum or 0.0)
        current_balance = float((paid_income_sum or 0.0) - (paid_expense_sum or 0.0))
        provisioned_balance = float(incomes - expenses)

        return {
            "incomes": incomes,
            "expenses": expenses,
            "current_balance": current_balance,
            "provisioned_balance": provisioned_balance,
        }

    base_transactions_query = db.query(AccountTransaction).filter(
        AccountTransaction.id_financial_account.in_(active_account_ids)
    )

    if end_date is not None:
        base_transactions_query = base_transactions_query.filter(
            AccountTransaction.purchase_date <= end_date
        )

    total = _aggregate_totals(base_transactions_query)

    if not has_filtered_filters:
        return total, None

    filtered_transactions_query = base_transactions_query

    if account_uuids is not None:
        active_accounts_by_uuid = {str(row[1]): row[0] for row in active_accounts}
        filtered_account_ids = [
            active_accounts_by_uuid[str(account_uuid)]
            for account_uuid in account_uuids
            if str(account_uuid) in active_accounts_by_uuid
        ]

        if not filtered_account_ids:
            return total, zero_totals

        filtered_transactions_query = filtered_transactions_query.filter(
            AccountTransaction.id_financial_account.in_(filtered_account_ids)
        )

    if transaction_type is not None:
        filtered_transactions_query = filtered_transactions_query.filter(
            AccountTransaction.transaction_type.in_(transaction_type)
        )

    if normalized_description:
        filtered_transactions_query = filtered_transactions_query.filter(
            func.unaccent(func.lower(AccountTransaction.description)).ilike(
                f"%{normalized_description}%"
            )
        )

    if category_uuids:
        if not category_ids:
            return total, zero_totals

        filtered_transactions_query = filtered_transactions_query.filter(
            AccountTransaction.id_category_transaction.in_(category_ids)
        )

    if is_paid is not None:
        filtered_transactions_query = filtered_transactions_query.filter(
            AccountTransaction.is_paid == is_paid
        )

    if normalized_value_text:
        filtered_transactions_query = filtered_transactions_query.filter(
            cast(AccountTransaction.value, String).ilike(f"%{normalized_value_text}%")
        )

    if normalized_merchant_name:
        filtered_transactions_query = filtered_transactions_query.join(
            MerchantNames,
            AccountTransaction.id_merchant_name == MerchantNames.id,
        ).filter(
            func.unaccent(func.lower(MerchantNames.name)).ilike(
                f"%{normalized_merchant_name}%"
            )
        )

    filtered = _aggregate_totals(filtered_transactions_query)

    return total, filtered
