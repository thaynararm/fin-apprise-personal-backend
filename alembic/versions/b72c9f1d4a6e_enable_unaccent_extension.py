"""enable unaccent extension

Revision ID: b72c9f1d4a6e
Revises: a1d9c4f2b7e3
Create Date: 2026-06-17 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b72c9f1d4a6e"
down_revision: Union[str, Sequence[str], None] = "a1d9c4f2b7e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS unaccent;")
