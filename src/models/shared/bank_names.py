from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class BankNames(BaseModel):
    __tablename__ = "bank_names"

    name = Column(String, nullable=False)
    description = Column(String, default="A inserir")

    financial_accounts = relationship("FinancialAccount", back_populates="bank_name")

    def __repr__(self):
        return f"<BankNames(id={self.id}, name='{self.name}')>"


class BrandNames(BaseModel):
    __tablename__ = "brand_names"

    name = Column(String, nullable=False)
    description = Column(String, default="A inserir")

    cards = relationship("Card", back_populates="brand_name")

    def __repr__(self):
        return f"<BrandNames(id={self.id}, name='{self.name}')>"