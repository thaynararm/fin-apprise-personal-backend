from sqlalchemy import Column, Enum, ForeignKey, String
from sqlalchemy.orm import relationship

from src.models.shared.enums import TransactionTypeEnum
from src.models.base import BaseModel


class CategoryTransaction(BaseModel):
    __tablename__ = "category_transactions"

    id_user = Column(ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    type = Column(
        Enum(TransactionTypeEnum, name="transaction_type_enum"),
        nullable=False,
    )

    user = relationship("User", back_populates="category_transactions")
    account_transactions = relationship(
        "AccountTransaction", back_populates="category_transaction"
    )
    card_transactions = relationship(
        "CardTransaction", back_populates="category_transaction"
    )

    def __repr__(self):
        return f"<CategoryTransaction(id={self.id}, name='{self.name}')>"
