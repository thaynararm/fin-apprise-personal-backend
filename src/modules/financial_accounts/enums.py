import enum


class AccountTypeEnum(enum.Enum):
    CURRENT_ACCOUNT = ("current_account", "Conta corrente")
    SAVINGS_ACCOUNT = ("savings_account", "Conta poupança")
    SALARY_ACCOUNT = ("salary_account", "Conta salário")
    INVESTMENT_ACCOUNT = ("investment_account", "Conta de investimento")

    def __init__(self, value, label):
        self._value_ = value
        self.label = label


class RecurrenceFrequencyLiteral(enum.Enum):
    DAILY = ("daily", "Diário")
    WEEKLY = ("weekly", "Semanal")
    BIWEEKLY = ("biweekly", "Quinzenal")
    MONTHLY = ("monthly", "Mensal")
    BIMONTHLY = ("bimonthly", "Bimestral")
    QUARTERLY = ("quarterly", "Trimestral")
    SEMIANNUAL = ("semiannual", "Semestral")
    ANNUAL = ("annual", "Anual")

    def __init__(self, value, label):
        self._value_ = value
        self.label = label
