from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class MerchantNames(BaseModel):
    __tablename__ = "merchant_names"
    __table_args__ = (
        UniqueConstraint("id_user", "name", name="uq_merchant_names_user_name"),
    )

    id_user = Column(ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, default="A inserir")

    user = relationship("User", back_populates="merchant_names")
    card_transactions = relationship("CardTransaction", back_populates="merchant_name")
    account_transactions = relationship(
        "AccountTransaction", back_populates="merchant_name"
    )

    def __repr__(self):
        return (
            f"<MerchantNames(id={self.id}, id_user={self.id_user}, name='{self.name}')>"
        )
