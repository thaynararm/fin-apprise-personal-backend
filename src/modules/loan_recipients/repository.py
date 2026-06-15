from uuid import UUID
from sqlalchemy.orm import Session
from src.models.shared.loan_recipient import LoanRecipient


def get_loan_recipient_by_name(
    db: Session,
    id_user: int,
    name: str,
) -> LoanRecipient | None:
    return (
        db.query(LoanRecipient)
        .filter(
            LoanRecipient.id_user == id_user,
            LoanRecipient.name.ilike(name),
        )
        .first()
    )


def get_or_create_loan_recipient_by_name(
    db: Session,
    id_user: int,
    name: str,
    description: str | None = None,
) -> LoanRecipient:
    db_recipient = get_loan_recipient_by_name(db, id_user, name)
    if db_recipient:
        return db_recipient

    db_recipient = LoanRecipient(
        id_user=id_user, name=name, description=description or "A inserir"
    )
    db.add(db_recipient)
    db.flush()

    return db_recipient


def get_loan_recipient_by_uuid(
    db: Session,
    id_user: int,
    recipient_uuid: UUID,
) -> LoanRecipient | None:
    return (
        db.query(LoanRecipient)
        .filter(
            LoanRecipient.id_user == id_user,
            LoanRecipient.uuid == recipient_uuid,
        )
        .first()
    )


def list_loan_recipients_by_user(
    db: Session,
    id_user: int,
    skip: int = 0,
    limit: int = 100,
) -> list[LoanRecipient]:
    return (
        db.query(LoanRecipient)
        .filter(LoanRecipient.id_user == id_user)
        .order_by(LoanRecipient.name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_loan_recipient(
    db: Session,
    id_user: int,
    name: str,
    description: str | None = None,
) -> LoanRecipient:
    db_recipient = LoanRecipient(
        id_user=id_user,
        name=name,
        description=description or "A inserir",
    )
    db.add(db_recipient)
    db.commit()
    db.refresh(db_recipient)
    return db_recipient


def update_loan_recipient(
    db: Session,
    db_recipient: LoanRecipient,
    **fields,
) -> LoanRecipient:
    for key, value in fields.items():
        if value is not None:
            setattr(db_recipient, key, value)

    db.commit()
    db.refresh(db_recipient)
    return db_recipient


def delete_loan_recipient(
    db: Session,
    db_recipient: LoanRecipient,
) -> None:
    db.delete(db_recipient)
    db.commit()
