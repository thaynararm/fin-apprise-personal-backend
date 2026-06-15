# src/modules/users/repository.py

from datetime import date
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .model import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_cpf(db: Session, cpf: str) -> User | None:
    return db.query(User).filter(User.cpf == cpf).first()


def get_user_by_phone_number(db: Session, phone_number: str) -> User | None:
    return db.query(User).filter(User.phone_number == phone_number).first()


def get_user_by_uuid(db: Session, user_uuid: UUID) -> User | None:
    return db.query(User).filter(User.uuid == user_uuid).first()


def list_users(
    db: Session,
    *,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[User]:
    query = db.query(User)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()


def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password_hash: str,
    birthdate: date,
    cpf: str,
    phone_number: str,
) -> User:
    db_user = User(
        full_name=full_name,
        email=email,
        password_hash=password_hash,
        birthdate=birthdate,
        cpf=cpf,
        phone_number=phone_number,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


def update_user(db: Session, db_user: User, **fields) -> User:
    for key, value in fields.items():
        setattr(db_user, key, value)

    db.commit()
    db.refresh(db_user)

    return db_user
