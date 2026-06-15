# src/modules/users/model.py

from sqlalchemy import Boolean, Column, Date, String
from src.models.base import BaseModel
from sqlalchemy.orm import relationship


class User(BaseModel):
    __tablename__ = "users"

    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    birthdate = Column(Date, nullable=False)
    cpf = Column(String, unique=True, nullable=False, index=True)
    phone_number = Column(String, unique=True, nullable=False, index=True)

    # Two-factor authentication fields (for future implementation)
    is_2fa_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String, nullable=True)

    def __repr__(self):
        return (
            f"<User(id={self.id}, email='{self.email}', full_name='{self.full_name}')>"
        )

    accounts = relationship("FinancialAccount", back_populates="user")
    cards = relationship("Card", back_populates="user")
    category_transactions = relationship("CategoryTransaction", back_populates="user")
    account_transactions = relationship("AccountTransaction", back_populates="user")
    card_transactions = relationship("CardTransaction", back_populates="user")
    account_transfers = relationship("AccountTransfer", back_populates="user")
    card_invoices = relationship("CardInvoice", back_populates="user")
    merchant_names = relationship("MerchantNames", back_populates="user")
    loan_recipients = relationship("LoanRecipient", back_populates="user")
