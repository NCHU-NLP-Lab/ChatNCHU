"""ChatNCHU: Drop demo_session unique constraint to allow multiple daily logins

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-03-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from open_webui.migrations.util import get_existing_tables

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    if "demo_session" in existing_tables:
        # Use batch mode for SQLite compatibility
        with op.batch_alter_table("demo_session") as batch_op:
            batch_op.drop_constraint(
                "uq_demo_session_user_date", type_="unique"
            )


def downgrade() -> None:
    with op.batch_alter_table("demo_session") as batch_op:
        batch_op.create_unique_constraint(
            "uq_demo_session_user_date", ["user_id", "login_date"]
        )
