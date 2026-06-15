import enum
import importlib
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import Enum as SQLAlchemyEnum
from src.models.shared.category_transaction import CategoryTransaction
from src.core.database import get_db
from src.models.shared import enums as shared_enums
from src.models.shared.bank_names import BankNames, BrandNames

router = APIRouter()


@router.get("")
def list_enums() -> dict[str, list[tuple[str, str]]]:
    all_enums: dict[str, list[tuple[str, str]]] = {}

    for name, enum_value in vars(shared_enums).items():
        if isinstance(enum_value, SQLAlchemyEnum):
            all_enums[name] = [(value, value) for value in enum_value.enums]
            continue

        if (
            isinstance(enum_value, type)
            and issubclass(enum_value, enum.Enum)
            and enum_value is not enum.Enum
        ):
            all_enums[name] = [
                (str(member.value), str(getattr(member, "label", member.value)))
                for member in enum_value
            ]

    modules_root = Path(__file__).resolve().parents[1]
    enum_files = list(modules_root.glob("*/enum.py")) + list(
        modules_root.glob("*/enums.py")
    )

    for enum_file in enum_files:
        module_folder_name = enum_file.parent.name
        module_file_name = enum_file.stem
        module_path = f"src.modules.{module_folder_name}.{module_file_name}"
        module = importlib.import_module(module_path)

        for enum_name, enum_class in vars(module).items():
            if (
                isinstance(enum_class, type)
                and issubclass(enum_class, enum.Enum)
                and enum_class is not enum.Enum
            ):
                key = f"{module_folder_name}.{enum_name}"
                all_enums[key] = [
                    (str(member.value), str(getattr(member, "label", member.value)))
                    for member in enum_class
                ]

    return all_enums


@router.get("/bank_names")
def list_bank_names(
    db: Session = Depends(get_db),
) -> list[tuple[str, str]]:
    banks = db.query(BankNames).order_by(BankNames.name).all()
    return [(bank.name, bank.description or "") for bank in banks]


@router.get("/brand_names")
def list_brand_names(
    db: Session = Depends(get_db),
) -> list[tuple[str, str]]:
    brands = db.query(BrandNames).order_by(BrandNames.name).all()
    return [(brand.name, brand.description or "") for brand in brands]


@router.get("/categories_transactions")
def list_categories_transactions(
    db: Session = Depends(get_db),
) -> list[tuple[str, str, str]]:
    categories = db.query(CategoryTransaction).order_by(CategoryTransaction.name).all()
    return [(str(category.uuid), category.description or "", category.type) for category in categories]
