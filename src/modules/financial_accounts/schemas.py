from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from src.modules.financial_accounts.enums import RecurrenceFrequencyLiteral
from src.modules.financial_accounts.model import AccountTypeEnum

# ------------------
# Financial Account Model
# ------------------


class FinancialAccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    account_type: AccountTypeEnum
    is_active: bool = True
    is_primary_bank: bool = False
    id_bank_name: str | None = None
    overdraft_limit: float = 0.0
    initial_balance_date: date = Field(default_factory=date.today)
    initial_balance: float = Field(default=0.0, ge=0)


class FinancialAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    account_type: AccountTypeEnum | None = None
    is_active: bool | None = None
    is_primary_bank: bool | None = None
    id_bank_name: int | None = None
    overdraft_limit: float | None = None


class BankNameResponse(BaseModel):
    uuid: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class FinancialAccountResponse(BaseModel):
    uuid: UUID
    user_uuid: UUID = Field(validation_alias="user")
    name: str
    account_type: AccountTypeEnum
    is_active: bool
    is_primary_bank: bool
    bank_name: BankNameResponse | None = None
    overdraft_limit: float | None
    current_balance: float | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("user_uuid", mode="before")
    @classmethod
    def extract_user_uuid(cls, v):
        if hasattr(v, "uuid"):
            return v.uuid
        return v


# ------------------
# Account Transactions Models
# ------------------


class AccountTransactionCreate(BaseModel):
    uuid_category_transaction: UUID
    transaction_type: Literal["income", "expense"]
    description: str = Field(..., min_length=1, max_length=255)
    purchase_date: date
    payment_date: date
    value: float
    merchant_name: str | None = Field(default=None, min_length=1, max_length=255)
    loan_recipient_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_paid: bool = False
    is_recurring: bool = False
    recurrence_frequency: RecurrenceFrequencyLiteral | None = None

    @model_validator(mode="after")
    def validate_recurrence(self):
        if self.is_recurring and self.recurrence_frequency is None:
            raise ValueError(
                "recurrence_frequency is required when is_recurring is true"
            )

        if not self.is_recurring and self.recurrence_frequency is not None:
            raise ValueError(
                "recurrence_frequency must be null when is_recurring is false"
            )

        return self


class AccountTransactionUpdate(BaseModel):
    uuid_financial_account: UUID | None = None
    uuid_category_transaction: UUID | None = None
    transaction_type: Literal["income", "expense"] | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    merchant_name: str | None = Field(default=None, min_length=1, max_length=255)
    loan_recipient_name: str | None = Field(default=None, min_length=1, max_length=255)
    purchase_date: date | None = None
    payment_date: date | None = None
    value: float | None = None
    is_paid: bool | None = None
    is_recurring: bool | None = None
    recurrence_enabled: bool | None = None
    recurrence_frequency: RecurrenceFrequencyLiteral | None = None


class AccountTransactionResponse(BaseModel):
    uuid: UUID
    user_uuid: UUID = Field(validation_alias="user")
    uuid_financial_account: UUID = Field(validation_alias="financial_account")
    uuid_category_transaction: UUID = Field(validation_alias="category_transaction")
    transaction_type: str
    description: str
    merchant_name: str | None = None
    loan_recipient_name: str | None = Field(
        default=None, validation_alias="loan_recipient"
    )
    purchase_date: date
    payment_date: date
    value: float
    is_paid: bool
    is_recurring: bool
    recurrence_frequency: RecurrenceFrequencyLiteral | None
    recurrence_enabled: bool
    recurrence_group_id: UUID | None
    uuid_destination_account: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator(
        "user_uuid",
        "uuid_financial_account",
        "uuid_category_transaction",
        mode="before",
    )
    @classmethod
    def extract_uuid(cls, v):
        if hasattr(v, "uuid"):
            return v.uuid
        return v

    @field_validator("merchant_name", mode="before")
    @classmethod
    def extract_merchant_name(cls, v):
        if hasattr(v, "name"):
            return v.name
        return v

    @field_validator("loan_recipient_name", mode="before")
    @classmethod
    def extract_loan_recipient_name(cls, v):
        if hasattr(v, "description") and v.description:
            return v.description
        if hasattr(v, "name"):
            return v.name
        return v


class AccountMovementResponse(BaseModel):
    uuid: UUID
    user_uuid: UUID = Field(validation_alias="user")
    uuid_financial_account: UUID = Field(validation_alias="financial_account")
    uuid_category_transaction: UUID = Field(validation_alias="category_transaction")
    transaction_type: str
    description: str
    merchant_name: str | None = None
    loan_recipient_name: str | None = Field(
        default=None, validation_alias="loan_recipient"
    )
    purchase_date: date
    payment_date: date
    value: float
    is_paid: bool
    is_recurring: bool
    recurrence_frequency: RecurrenceFrequencyLiteral | None
    recurrence_enabled: bool
    recurrence_group_id: UUID | None
    uuid_account_destination: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator(
        "user_uuid",
        "uuid_financial_account",
        "uuid_category_transaction",
        mode="before",
    )
    @classmethod
    def extract_uuid(cls, v):
        if hasattr(v, "uuid"):
            return v.uuid
        return v

    @field_validator("merchant_name", mode="before")
    @classmethod
    def extract_merchant_description(cls, v):
        if hasattr(v, "description"):
            return v.description
        if hasattr(v, "name"):
            return v.name
        return v

    @field_validator("loan_recipient_name", mode="before")
    @classmethod
    def extract_loan_recipient_name(cls, v):
        if hasattr(v, "description") and v.description:
            return v.description
        if hasattr(v, "name"):
            return v.name
        return v


# ------------------
# Account Transfers Models
# ------------------


class AccountTransferCreate(BaseModel):
    origin_uuid_financial_account: UUID
    destination_uuid_financial_account: UUID
    transfer_date: date
    amount: float
    description: str | None = Field(default=None, max_length=255)


class AccountTransferUpdate(BaseModel):
    origin_uuid_financial_account: UUID | None = None
    destination_uuid_financial_account: UUID | None = None
    transfer_date: date | None = None
    amount: float | None = None
    description: str | None = Field(default=None, max_length=255)


class AccountTransferResponse(BaseModel):
    uuid: UUID
    user_uuid: UUID = Field(validation_alias="user")
    origin_uuid_financial_account: UUID = Field(validation_alias="origin_account")
    destination_uuid_financial_account: UUID = Field(
        validation_alias="destination_account"
    )
    transfer_date: date
    amount: float
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator(
        "user_uuid",
        "origin_uuid_financial_account",
        "destination_uuid_financial_account",
        mode="before",
    )
    @classmethod
    def extract_uuid(cls, v):
        if hasattr(v, "uuid"):
            return v.uuid
        return v


class UserActiveAccountsMovementsResponse(BaseModel):
    transactions: list[AccountTransactionResponse]
    transfers: list[AccountTransferResponse]


class FinancialSummaryTotals(BaseModel):
    incomes: float
    expenses: float
    current_balance: float
    provisioned_balance: float


class UserFinancialSummaryResponse(BaseModel):
    total: FinancialSummaryTotals
    filtered: FinancialSummaryTotals | None = None
