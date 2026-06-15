import logging
from uuid import UUID
from sqlalchemy.orm import Session
from src.core.exceptions.domain import ValidationDomainError
from src.modules.merchants import repository
from src.modules.users.model import User

logger = logging.getLogger(__name__)


def list_merchants_by_user(
    db: Session,
    current_user: User,
    *,
    skip: int = 0,
    limit: int = 100,
) -> list:
    merchants = repository.list_merchants_by_user(
        db,
        id_user=current_user.id,
        skip=skip,
        limit=limit,
    )
    return merchants


def get_merchant_by_uuid(
    db: Session,
    current_user: User,
    merchant_uuid: UUID,
) -> dict:
    db_merchant = repository.get_merchant_by_uuid(db, current_user.id, merchant_uuid)
    if not db_merchant:
        raise ValidationDomainError("Merchant not found")
    return db_merchant


def create_merchant(
    db: Session,
    current_user: User,
    payload,
) -> dict:
    normalized_name = payload.name.strip()
    if not normalized_name:
        raise ValidationDomainError("Merchant name cannot be empty")

    existing_merchant = repository.get_merchant_by_name(
        db,
        current_user.id,
        normalized_name,
    )
    if existing_merchant:
        raise ValidationDomainError(f"Merchant '{normalized_name}' already exists")

    db_merchant = repository.create_merchant(
        db,
        id_user=current_user.id,
        name=normalized_name,
        description=payload.description,
    )

    logger.info(
        "Merchant created with uuid: %s for user uuid: %s",
        db_merchant.uuid,
        current_user.uuid,
    )

    return db_merchant


def update_merchant(
    db: Session,
    current_user: User,
    merchant_uuid: UUID,
    payload,
) -> dict:
    db_merchant = repository.get_merchant_by_uuid(db, current_user.id, merchant_uuid)
    if not db_merchant:
        raise ValidationDomainError("Merchant not found")

    fields = payload.model_dump(exclude_unset=True)

    if "name" in fields:
        normalized_name = fields["name"].strip()
        if not normalized_name:
            raise ValidationDomainError("Merchant name cannot be empty")

        existing_merchant = repository.get_merchant_by_name(
            db,
            current_user.id,
            normalized_name,
        )
        if existing_merchant and existing_merchant.id != db_merchant.id:
            raise ValidationDomainError(f"Merchant '{normalized_name}' already exists")

        fields["name"] = normalized_name

    updated_merchant = repository.update_merchant(db, db_merchant, **fields)

    logger.info("Merchant updated with uuid: %s", merchant_uuid)

    return updated_merchant


def delete_merchant(
    db: Session,
    current_user: User,
    merchant_uuid: UUID,
) -> None:
    db_merchant = repository.get_merchant_by_uuid(db, current_user.id, merchant_uuid)
    if not db_merchant:
        raise ValidationDomainError("Merchant not found")

    repository.delete_merchant(db, db_merchant)

    logger.info(
        "Merchant deleted with uuid: %s for user uuid: %s",
        merchant_uuid,
        current_user.uuid,
    )
