from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class LoanRecipient(BaseModel):
    __tablename__ = "loan_recipients"
    __table_args__ = (
        UniqueConstraint("id_user", "name", name="uq_loan_recipients_user_name"),
    )

    id_user = Column(ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    user = relationship("User", back_populates="loan_recipients")
    card_transactions = relationship("CardTransaction", back_populates="loan_recipient")
    account_transactions = relationship(
        "AccountTransaction", back_populates="loan_recipient"
    )

    def __repr__(self):
        return (
            f"<LoanRecipient(id={self.id}, id_user={self.id_user}, name='{self.name}')>"
        )
