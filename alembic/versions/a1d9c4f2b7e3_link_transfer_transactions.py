"""link transfer transactions

Revision ID: a1d9c4f2b7e3
Revises: 48e00ee07fb4
Create Date: 2026-06-12 22:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1d9c4f2b7e3"
down_revision: Union[str, Sequence[str], None] = "48e00ee07fb4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "account_transfers",
        sa.Column("id_origin_transaction", sa.Integer(), nullable=True),
    )
    op.add_column(
        "account_transfers",
        sa.Column("id_destination_transaction", sa.Integer(), nullable=True),
    )

    op.create_foreign_key(
        "fk_account_transfers_origin_transaction",
        "account_transfers",
        "account_transactions",
        ["id_origin_transaction"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_account_transfers_destination_transaction",
        "account_transfers",
        "account_transactions",
        ["id_destination_transaction"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_account_transfers_destination_transaction",
        "account_transfers",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_account_transfers_origin_transaction",
        "account_transfers",
        type_="foreignkey",
    )

    op.drop_column("account_transfers", "id_destination_transaction")
    op.drop_column("account_transfers", "id_origin_transaction")
