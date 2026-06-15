import logging
from sqlalchemy.orm import Session
from src.core.exceptions.domain import ValidationDomainError
from src.modules.loan_recipients import repository
from src.modules.users.model import User

logger = logging.getLogger(__name__)


def list_loan_recipients_by_user(
    db: Session,
    current_user: User,
    *,
    skip: int = 0,
    limit: int = 100,
) -> list:
    return repository.list_loan_recipients_by_user(
        db,
        id_user=current_user.id,
        skip=skip,
        limit=limit,
    )


def get_loan_recipient_by_uuid(
    db: Session,
    current_user: User,
    recipient_uuid,
) -> dict:
    db_recipient = repository.get_loan_recipient_by_uuid(
        db, current_user.id, recipient_uuid
    )
    if not db_recipient:
        raise ValidationDomainError("Loan recipient not found")
    return db_recipient


def create_loan_recipient(
    db: Session,
    current_user: User,
    payload,
) -> dict:
    normalized_name = payload.name.strip()
    if not normalized_name:
        raise ValidationDomainError("Loan recipient name cannot be empty")

    existing_recipient = repository.get_loan_recipient_by_name(
        db,
        current_user.id,
        normalized_name,
    )
    if existing_recipient:
        raise ValidationDomainError(
            f"Loan recipient '{normalized_name}' already exists"
        )

    db_recipient = repository.create_loan_recipient(
        db,
        id_user=current_user.id,
        name=normalized_name,
        description=payload.description,
    )

    logger.info(
        "Loan recipient created with uuid: %s for user uuid: %s",
        db_recipient.uuid,
        current_user.uuid,
    )

    return db_recipient


def update_loan_recipient(
    db: Session,
    current_user: User,
    recipient_uuid,
    payload,
) -> dict:
    from uuid import UUID

    db_recipient = repository.get_loan_recipient_by_uuid(
        db, current_user.id, recipient_uuid
    )
    if not db_recipient:
        raise ValidationDomainError("Loan recipient not found")

    fields = payload.model_dump(exclude_unset=True)

    if "name" in fields:
        normalized_name = fields["name"].strip()
        if not normalized_name:
            raise ValidationDomainError("Loan recipient name cannot be empty")

        existing_recipient = repository.get_loan_recipient_by_name(
            db,
            current_user.id,
            normalized_name,
        )
        if existing_recipient and existing_recipient.id != db_recipient.id:
            raise ValidationDomainError(
                f"Loan recipient '{normalized_name}' already exists"
            )

        fields["name"] = normalized_name

    updated_recipient = repository.update_loan_recipient(db, db_recipient, **fields)

    logger.info("Loan recipient updated with uuid: %s", recipient_uuid)

    return updated_recipient


def delete_loan_recipient(
    db: Session,
    current_user: User,
    recipient_uuid,
) -> None:
    db_recipient = repository.get_loan_recipient_by_uuid(
        db, current_user.id, recipient_uuid
    )
    if not db_recipient:
        raise ValidationDomainError("Loan recipient not found")

    repository.delete_loan_recipient(db, db_recipient)

    logger.info(
        "Loan recipient deleted with uuid: %s for user uuid: %s",
        recipient_uuid,
        current_user.uuid,
    )
