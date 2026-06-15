# src/modules/users/service.py

from uuid import UUID
from sqlalchemy.orm import Session
from src.modules.users import repository
from src.modules.users.model import User
from src.modules.users.schemas import UserCreate, UserUpdate
from src.core.security import hash_password
from src.core.exceptions.domain import ConflictDomainError, ValidationDomainError
import logging
import re

logger = logging.getLogger(__name__)


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _normalize_phone_number(phone_number: str) -> str:
    normalized_phone = _only_digits(phone_number)

    # Remove a leading zero from DDD when provided in formats like 0XX...
    if normalized_phone.startswith("0"):
        normalized_phone = normalized_phone[1:]

    return normalized_phone


def create_user(db: Session, user: UserCreate) -> User:
    normalized_cpf = _only_digits(user.cpf)
    normalized_phone_number = _normalize_phone_number(user.phone_number)

    # validate cpf format (stores only 11 digits)
    if len(normalized_cpf) != 11:
        raise ValidationDomainError("Invalid CPF format")

    # validate phone number format (DDD + number, without leading zero)
    if len(normalized_phone_number) not in [10, 11]:
        raise ValidationDomainError("Invalid phone number format")

    # Verify duplicity by email
    if repository.get_user_by_email(db, user.email):
        raise ConflictDomainError("Email already registered")

    # Verify duplicity by CPF
    if repository.get_user_by_cpf(db, normalized_cpf):
        raise ConflictDomainError("CPF already registered")

    # Verify duplicity by phone number
    if repository.get_user_by_phone_number(db, normalized_phone_number):
        raise ConflictDomainError("Phone number already registered")

    # Hash the password
    password_hash = hash_password(user.password)

    # Create in the database
    new_user = repository.create_user(
        db,
        full_name=user.full_name,
        email=user.email,
        password_hash=password_hash,
        birthdate=user.birthdate,
        cpf=normalized_cpf,
        phone_number=normalized_phone_number,
    )

    logger.info("User created with email: %s and uuid: %s", new_user.email, new_user.uuid)

    return new_user


def get_user_by_email(db: Session, email: str) -> User | None:
    """Get a user by email"""
    return repository.get_user_by_email(db, email)


def get_user_by_uuid(db: Session, user_uuid: UUID) -> User | None:
    return repository.get_user_by_uuid(db, user_uuid)


def list_users(
    db: Session,
    *,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[User]:
    return repository.list_users(db, search=search, skip=skip, limit=limit)


def update_user(db: Session, db_user: User, payload: UserUpdate) -> User:
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise ValidationDomainError("No fields provided for update")

    if "email" in update_data:
        existing_user = repository.get_user_by_email(db, update_data["email"])
        if existing_user and existing_user.uuid != db_user.uuid:
            raise ConflictDomainError("Email already registered")

    if "cpf" in update_data:
        normalized_cpf = _only_digits(update_data["cpf"])

        if len(normalized_cpf) != 11:
            raise ValidationDomainError("Invalid CPF format")

        existing_user = repository.get_user_by_cpf(db, normalized_cpf)
        if existing_user and existing_user.uuid != db_user.uuid:
            raise ConflictDomainError("CPF already registered")

        update_data["cpf"] = normalized_cpf

    if "phone_number" in update_data:
        normalized_phone_number = _normalize_phone_number(update_data["phone_number"])

        if len(normalized_phone_number) not in [10, 11]:
            raise ValidationDomainError("Invalid phone number format")

        existing_user = repository.get_user_by_phone_number(db, normalized_phone_number)
        if existing_user and existing_user.uuid != db_user.uuid:
            raise ConflictDomainError("Phone number already registered")

        update_data["phone_number"] = normalized_phone_number

    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))

    updated_user = repository.update_user(db, db_user, **update_data)

    logger.info("User updated with email: %s and uuid: %s", updated_user.email, updated_user.uuid)

    return updated_user
