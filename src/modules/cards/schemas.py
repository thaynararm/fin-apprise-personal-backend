from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from src.modules.cards.model import CardTypeEnum


class CardCreate(BaseModel):
    uuid_financial_account: UUID | None = Field(
        default=None,
        validation_alias=AliasChoices("uuid_financial_account", "id_account"),
    )
    brand_name: str | None = Field(default=None, min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=120)
    card_type: CardTypeEnum
    due_day: int = Field(..., ge=1, le=31)
    closing_day: int = Field(..., ge=1, le=31)
    limit: float | None = None
    last_4_digits: str | None = Field(default=None, min_length=4, max_length=4)
    is_active: bool = True

    @field_validator("uuid_financial_account", mode="before")
    @classmethod
    def normalize_uuid_financial_account(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v


class CardUpdate(BaseModel):
    uuid_financial_account: UUID | None = Field(
        default=None,
        validation_alias=AliasChoices("uuid_financial_account", "id_account"),
    )
    brand_name: str | None = Field(default=None, min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    card_type: CardTypeEnum | None = None
    due_day: int | None = Field(default=None, ge=1, le=31)
    closing_day: int | None = Field(default=None, ge=1, le=31)
    limit: float | None = None
    last_4_digits: str | None = Field(default=None, min_length=4, max_length=4)
    is_active: bool | None = None


class BrandNameResponse(BaseModel):
    uuid: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class BankNameResponse(BaseModel):
    uuid: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class CardResponse(BaseModel):
    uuid: UUID
    user_uuid: UUID = Field(validation_alias="user")
    uuid_financial_account: UUID | None = Field(
        default=None, validation_alias="account"
    )
    brand_name: BrandNameResponse | None = None
    bank_name: BankNameResponse | None = Field(default=None, validation_alias="account")
    name: str
    card_type: CardTypeEnum
    due_day: int
    is_active: bool
    limit: float | None = None
    last_4_digits: str | None = None
    current_invoice: float | None = None
    available_limit: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("user_uuid", "uuid_financial_account", mode="before")
    @classmethod
    def extract_uuid(cls, v):
        if v is None:
            return None
        if hasattr(v, "uuid"):
            return v.uuid
        return v

    @field_validator("bank_name", mode="before")
    @classmethod
    def extract_bank_name(cls, v):
        if v is None:
            return None
        if hasattr(v, "bank_name"):
            return v.bank_name
        return v

    @field_validator("current_invoice", "available_limit", mode="before")
    @classmethod
    def handle_missing_optional_fields(cls, v):
        # If attribute doesn't exist or is None, return None instead of raising error
        return v if v is not None else None


class CardSummaryTotals(BaseModel):
    limits: float
    current_invoice: float
    available_limit: float


class UserCardsSummaryResponse(BaseModel):
    total: CardSummaryTotals


class CardInstallmentInvoiceSummary(BaseModel):
    uuid: UUID
    reference_month: date
    due_date: date
    status: str


class CardInvoiceGroupedByCardResponse(BaseModel):
    uuid: UUID
    reference_month: date
    closing_date: date
    due_date: date
    start_date: date
    end_date: date
    total_amount: float
    paid_amount: float
    status: str
    created_at: datetime
    updated_at: datetime


class UserCardInvoicesGroupedResponse(BaseModel):
    card_uuid: UUID
    card_name: str
    invoices: list[CardInvoiceGroupedByCardResponse]


class CardInstallmentTransactionSummary(BaseModel):
    uuid: UUID
    uuid_category_transaction: UUID
    description: str
    purchase_date: date
    total_value: float
    installments_count: int
    merchant_name: str | None = None
    loan_recipient_name: str | None = None


class CardInstallmentByMonthResponse(BaseModel):
    uuid: UUID
    card_uuid: UUID
    card_name: str
    invoice: CardInstallmentInvoiceSummary
    transaction: CardInstallmentTransactionSummary
    installment_number: int
    value: float
    due_date: date
    is_paid: bool
    paid_at: date | None = None
    created_at: datetime
    updated_at: datetime


class CardTransactionCreate(BaseModel):
    uuid_category_transaction: UUID
    transaction_type: Literal["income", "expense"]
    description: str = Field(..., min_length=1, max_length=255)
    purchase_date: date
    total_value: float = Field(..., gt=0)
    installments_count: int = Field(default=1, ge=1)
    merchant_name: str | None = Field(default=None, min_length=1, max_length=255)
    loan_recipient_name: str | None = Field(default=None, min_length=1, max_length=255)
    invoice_reference_month: date | None = None


class CardTransactionInstallmentCreatedResponse(BaseModel):
    uuid: UUID
    invoice_uuid: UUID
    invoice_reference_month: date
    installment_number: int
    value: float
    due_date: date
    is_paid: bool


class CardTransactionUpdate(BaseModel):
    uuid_category_transaction: UUID | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    purchase_date: date | None = None
    merchant_name: str | None = Field(default=None, min_length=1, max_length=255)
    loan_recipient_name: str | None = Field(default=None, min_length=1, max_length=255)
    uuid_card: UUID | None = None
    total_value: float | None = Field(default=None, gt=0)
    installments_count: int | None = Field(default=None, ge=1)
    invoice_reference_month: date | None = None


class CardTransactionCreatedResponse(BaseModel):
    uuid: UUID
    card_uuid: UUID
    uuid_category_transaction: UUID
    transaction_type: str
    description: str
    purchase_date: date
    total_value: float
    installments_count: int
    merchant_name: str | None = None
    loan_recipient_name: str | None = None
    is_canceled: bool
    created_at: datetime
    updated_at: datetime
    installments: list[CardTransactionInstallmentCreatedResponse]


class ResolveInvoiceReferenceMonthRequest(BaseModel):
    purchase_date: date = Field(..., description="Data de compra")


class ResolveInvoiceReferenceMonthResponse(BaseModel):
    purchase_date: date
    card_closing_day: int
    invoice_reference_month: date = Field(
        ..., description="Mês de referência da fatura em que a compra seria inserida"
    )
    closing_date: date = Field(
        ..., description="Data de fechamento da fatura para este mês de referência"
    )
    due_date: date = Field(
        ..., description="Data de vencimento da fatura para este mês de referência"
    )
