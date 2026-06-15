# src/api/routers.py

from fastapi import APIRouter
from src.modules.auth.router import router as auth_router
from src.modules.users.router import router as users_router
from src.modules.financial_accounts.router import router as financial_accounts_router
from src.modules.cards.router import router as cards_router
from src.modules.merchants.router import router as merchants_router
from src.modules.loan_recipients.router import router as loan_recipients_router
from src.modules.enums.router import router as enums_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(
    financial_accounts_router,
    prefix="/financial-accounts",
    tags=["Financial Accounts"],
)
api_router.include_router(cards_router, prefix="/cards", tags=["Cards"])
api_router.include_router(merchants_router, prefix="/merchants", tags=["Merchants"])
api_router.include_router(
    loan_recipients_router,
    prefix="/loan-recipients",
    tags=["Loan Recipients"],
)
api_router.include_router(enums_router, prefix="/enums", tags=["Enums"])
