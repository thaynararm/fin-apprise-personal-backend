import uuid
from sqlalchemy import Boolean, Column, Date, Float, String, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from src.modules.financial_accounts.enums import (
    AccountTypeEnum,
    RecurrenceFrequencyLiteral,
)
from src.models.base import BaseModel
from src.models.shared.category_transaction import CategoryTransaction
from src.modules.merchants.model import MerchantNames
from src.models.shared.loan_recipient import LoanRecipient
from sqlalchemy.orm import relationship
from src.models.shared.enums import TransactionTypeEnum

# ------------------
# Financial Account Model
# ------------------


class FinancialAccount(BaseModel):
    __tablename__ = "financial_accounts"

    id_user = Column(ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    account_type = Column(Enum(AccountTypeEnum), nullable=False)
    is_active = Column(Boolean, default=True)
    id_bank_name = Column(ForeignKey("bank_names.id"), nullable=True)
    is_primary_bank = Column(Boolean, default=False, nullable=False)
    overdraft_limit = Column(Float, default=0.0)

    user = relationship("User", back_populates="accounts")
    cards = relationship("Card", back_populates="account")
    account_transactions = relationship(
        "AccountTransaction", back_populates="financial_account"
    )
    origin_transfers = relationship(
        "AccountTransfer",
        foreign_keys="AccountTransfer.id_origin_account",
        back_populates="origin_account",
    )
    destination_transfers = relationship(
        "AccountTransfer",
        foreign_keys="AccountTransfer.id_destination_account",
        back_populates="destination_account",
    )
    bank_name = relationship("BankNames", back_populates="financial_accounts")

    @property
    def current_balance(self):
        transactions = self.account_transactions

        incomes = sum(
            t.value
            for t in transactions
            if t.transaction_type.value == "income" and t.is_paid
        )

        expenses = sum(
            t.value
            for t in transactions
            if t.transaction_type.value == "expense" and t.is_paid
        )

        return incomes - expenses

    def __repr__(self):
        return (
            f"<FinancialAccount(id={self.id}, name='{self.name}', "
            f"account_type='{self.account_type.value}', is_active={self.is_active}, "
            f"id_bank_name={self.id_bank_name}, is_primary_bank={self.is_primary_bank}, overdraft_limit={self.overdraft_limit})>"
        )


# ------------------
# Account Transactions Models
# ------------------


class AccountTransaction(BaseModel):
    __tablename__ = "account_transactions"

    id_user = Column(ForeignKey("users.id"), nullable=False)
    id_financial_account = Column(ForeignKey("financial_accounts.id"), nullable=False)
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
    payment_date = Column(Date, nullable=False)
    value = Column(Float, nullable=False)
    is_paid = Column(Boolean, default=False)
    is_recurring = Column(Boolean, nullable=False, default=False)
    recurrence_frequency = Column(
        Enum(RecurrenceFrequencyLiteral, name="recurrence_frequency_enum"),
        nullable=True,
    )
    recurrence_enabled = Column(Boolean, nullable=False, default=False)
    recurrence_group_id = Column(UUID(as_uuid=True), nullable=True)
    recurrence_parent_id = Column(ForeignKey("account_transactions.id"), nullable=True)

    user = relationship("User", back_populates="account_transactions")
    financial_account = relationship(
        "FinancialAccount", back_populates="account_transactions"
    )
    category_transaction = relationship(
        "CategoryTransaction", back_populates="account_transactions"
    )
    merchant_name = relationship("MerchantNames", back_populates="account_transactions")
    loan_recipient = relationship(
        "LoanRecipient", back_populates="account_transactions"
    )
    transaction_installments = relationship(
        "AccountTransactionInstallment", back_populates="account_transaction"
    )
    recurrence_parent = relationship(
        "AccountTransaction",
        remote_side="AccountTransaction.id",
        foreign_keys=[recurrence_parent_id],
        backref="recurrence_children",
    )

    def __repr__(self):
        return (
            f"<AccountTransaction(id={self.id}, description='{self.description}', "
            f"category='{self.category_transaction}', purchase_date={self.purchase_date}, "
            f"payment_date={self.payment_date}, value={self.value}, transaction_type={self.transaction_type}, is_paid={self.is_paid})>"
        )


class AccountTransactionInstallment(BaseModel):
    __tablename__ = "account_transaction_installments"

    id_account_transaction = Column(
        ForeignKey("account_transactions.id"), nullable=False
    )
    installment_number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    value = Column(Float, nullable=False)
    is_paid = Column(Boolean, default=False)

    account_transaction = relationship(
        "AccountTransaction", back_populates="transaction_installments"
    )

    def __repr__(self):
        return (
            f"<AccountTransactionInstallment(id={self.id}, "
            f"installment_number={self.installment_number}, due_date={self.due_date}, "
            f"value={self.value}, is_paid={self.is_paid})>"
        )


class AccountTransfer(BaseModel):
    __tablename__ = "account_transfers"

    id_user = Column(ForeignKey("users.id"), nullable=False)

    id_origin_account = Column(ForeignKey("financial_accounts.id"), nullable=False)

    id_destination_account = Column(ForeignKey("financial_accounts.id"), nullable=False)

    id_origin_transaction = Column(
        ForeignKey("account_transactions.id"),
        nullable=True,
    )

    id_destination_transaction = Column(
        ForeignKey("account_transactions.id"),
        nullable=True,
    )

    transfer_date = Column(Date, nullable=False)

    amount = Column(Float, nullable=False)

    description = Column(String, nullable=True)

    user = relationship(
        "User", foreign_keys=[id_user], back_populates="account_transfers"
    )
    origin_account = relationship(
        "FinancialAccount",
        foreign_keys=[id_origin_account],
        back_populates="origin_transfers",
    )
    destination_account = relationship(
        "FinancialAccount",
        foreign_keys=[id_destination_account],
        back_populates="destination_transfers",
    )
    origin_transaction = relationship(
        "AccountTransaction",
        foreign_keys=[id_origin_transaction],
    )
    destination_transaction = relationship(
        "AccountTransaction",
        foreign_keys=[id_destination_transaction],
    )
