import enum


class CardTypeEnum(enum.Enum):
    CREDIT_CARD = ("credit_card", "Cartao de Crédito")
    # DEBIT_CARD = ("debit_card", "Cartao de debito")
    PREPAID_CARD = ("prepaid_card", "Cartao Pré-Pago")
    

    def __init__(self, value, label):
        self._value_ = value
        self.label = label


class CardInvoiceStatusEnum(enum.Enum):
    OPEN = ("open", "Aberta")
    CLOSED = ("closed", "Fechada")
    PAID = ("paid", "Paga")
    OVERDUE = ("overdue", "Vencida")

    def __init__(self, value, label):
        self._value_ = value
        self.label = label
