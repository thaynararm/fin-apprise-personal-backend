from sqlalchemy import (
    Boolean,
    Column,
    String,
    Enum,
    ForeignKey,
    Float,
    Date,
    Integer,
    UniqueConstraint,
)
from src.models.base import BaseModel
from sqlalchemy.orm import relationship
from src.modules.cards.enums import CardInvoiceStatusEnum, CardTypeEnum
from src.models.shared.category_transaction import CategoryTransaction
from src.modules.merchants.model import MerchantNames
from src.models.shared.enums import TransactionTypeEnum
from src.models.shared.loan_recipient import LoanRecipient

# ------------------
# Card Model
# ------------------


class Card(BaseModel):
    __tablename__ = "cards"

    id_user = Column(ForeignKey("users.id"), nullable=False)
    id_account = Column(ForeignKey("financial_accounts.id"), nullable=True)
    id_brand_names = Column(ForeignKey("brand_names.id"), nullable=True)
    name = Column(String, nullable=False)
    card_type = Column(Enum(CardTypeEnum), nullable=False)
    due_day = Column(Integer, nullable=False, default=1)
    closing_day = Column(Integer, nullable=True)
    limit = Column(Float, nullable=True)
    last_4_digits = Column(String(4), nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="cards")
    account = relationship("FinancialAccount", back_populates="cards")
    invoices = relationship("CardInvoice", back_populates="card")
    card_transactions = relationship("CardTransaction", back_populates="card")
    brand_name = relationship("BrandNames", back_populates="cards")

    def __repr__(self):
        return (
            f"<Card(id={self.id}, name='{self.name}', card_type='{self.card_type.value}', due_day={self.due_day},"
            f"is_active={self.is_active}, brand='{self.brand_name.name if self.brand_name else None}', limit={self.limit})>"
        )


# ------------------
# Card Invoice Model
# ------------------


class CardInvoice(BaseModel):
    __tablename__ = "card_invoices"

    id_user = Column(ForeignKey("users.id"), nullable=False)
    id_card = Column(ForeignKey("cards.id"), nullable=False)
    id_account_transaction = Column(
        ForeignKey("account_transactions.id"), nullable=True
    )

    # Exemplo:
    # 2026-05-01 representa a fatura de Maio/2026
    reference_month = Column(Date, nullable=False)

    # Datas operacionais para controle interno
    closing_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)

    # Intervalo real da fatura
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_amount = Column(Float, default=0)
    paid_amount = Column(Float, default=0)

    status = Column(Enum(CardInvoiceStatusEnum), nullable=False)

    # Relationships
    user = relationship("User", back_populates="card_invoices")

    card = relationship("Card", back_populates="invoices")

    account_transaction = relationship(
        "AccountTransaction",
        foreign_keys="CardInvoice.id_account_transaction",
        backref="card_invoice",
    )

    installments = relationship("CardTransactionInstallment", back_populates="invoice")

    def __repr__(self):
        return (
            f"<CardInvoice(id={self.id}, "
            f"reference_month='{self.reference_month}', "
            f"total_amount={self.total_amount}, "
            f"status='{self.status.value}')>"
        )


# ------------------
# Card Transaction Model
# ------------------


class CardTransaction(BaseModel):
    __tablename__ = "card_transactions"

    id_user = Column(ForeignKey("users.id"), nullable=False)
    id_card = Column(ForeignKey("cards.id"), nullable=False)
    id_category_transaction = Column(
        ForeignKey("category_transactions.id"), nullable=False
    )
    id_merchant_name = Column(ForeignKey("merchant_names.id"), nullable=True)
    id_loan_recipient = Column(ForeignKey("loan_recipients.id"), nullable=True)
    transaction_type = Column(
        Enum(TransactionTypeEnum, name="transaction_type_enum"),
        nullable=False,
    )
    description = Column(String, nullable=False)
    purchase_date = Column(Date, nullable=False)
    total_value = Column(Float, nullable=False)
    installments_count = Column(Integer, default=1)
    is_canceled = Column(Boolean, default=False)

    user = relationship("User", back_populates="card_transactions")
    card = relationship("Card", back_populates="card_transactions")
    category_transaction = relationship(
        "CategoryTransaction", back_populates="card_transactions"
    )
    merchant_name = relationship("MerchantNames", back_populates="card_transactions")
    loan_recipient = relationship("LoanRecipient", back_populates="card_transactions")
    installments = relationship(
        "CardTransactionInstallment", back_populates="card_transaction"
    )

    def __repr__(self):
        return (
            f"<CardTransaction(id={self.id}, description='{self.description}', "
            f"category='{self.category_transaction.name}', purchase_date={self.purchase_date}, "
            f"total_value={self.total_value}, is_paid={self.is_paid})>"
        )


class CardTransactionInstallment(BaseModel):
    __tablename__ = "card_transaction_installments"

    id_card_transaction = Column(ForeignKey("card_transactions.id"), nullable=False)
    id_card_invoice = Column(ForeignKey("card_invoices.id"), nullable=False)
    installment_number = Column(Integer, nullable=False)
    value = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False)
    is_paid = Column(Boolean, default=False)
    paid_at = Column(Date, nullable=True)

    card_transaction = relationship("CardTransaction", back_populates="installments")
    invoice = relationship("CardInvoice", back_populates="installments")

    def __repr__(self):
        return (
            f"<CardTransactionInstallment(id={self.id}, "
            f"installment_number={self.installment_number}, due_date={self.due_date}, "
            f"value={self.value}, is_paid={self.is_paid})>"
        )
