import enum

class TransactionTypeEnum(enum.Enum):
    income = ("income", "Receita")
    expense = ("expense", "Despesa")
    transfer = ("transfer", "Transferência")

    def __init__(self, value, label):
        self._value_ = value
        self.label = label