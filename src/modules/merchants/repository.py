from uuid import UUID
from sqlalchemy.orm import Session
from src.modules.merchants.model import MerchantNames


def get_merchant_by_name(
    db: Session,
    id_user: int,
    merchant_name: str,
) -> MerchantNames | None:
    return (
        db.query(MerchantNames)
        .filter(
            MerchantNames.id_user == id_user,
            MerchantNames.name.ilike(merchant_name),
        )
        .first()
    )


def get_or_create_merchant_by_name(
    db: Session,
    id_user: int,
    merchant_name: str,
    description: str,
) -> MerchantNames:
    db_merchant = get_merchant_by_name(db, id_user, merchant_name)
    if db_merchant:
        return db_merchant

    db_merchant = MerchantNames(id_user=id_user, name=merchant_name, description=description)
    db.add(db_merchant)
    db.flush()

    return db_merchant


def get_merchant_by_uuid(
    db: Session,
    id_user: int,
    merchant_uuid: UUID,
) -> MerchantNames | None:
    return (
        db.query(MerchantNames)
        .filter(MerchantNames.id_user == id_user, MerchantNames.uuid == merchant_uuid)
        .first()
    )


def list_merchants_by_user(
    db: Session,
    id_user: int,
    skip: int = 0,
    limit: int = 100,
) -> list[MerchantNames]:
    return (
        db.query(MerchantNames)
        .filter(MerchantNames.id_user == id_user)
        .order_by(MerchantNames.name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_merchant(
    db: Session,
    id_user: int,
    name: str,
    description: str | None = None,
) -> MerchantNames:
    db_merchant = MerchantNames(
        id_user=id_user,
        name=name,
        description=description or "A inserir",
    )
    db.add(db_merchant)
    db.commit()
    db.refresh(db_merchant)
    return db_merchant


def update_merchant(
    db: Session,
    db_merchant: MerchantNames,
    **fields,
) -> MerchantNames:
    for key, value in fields.items():
        if value is not None:
            setattr(db_merchant, key, value)

    db.commit()
    db.refresh(db_merchant)
    return db_merchant


def delete_merchant(
    db: Session,
    db_merchant: MerchantNames,
) -> None:
    db.delete(db_merchant)
    db.commit()
