"""ChatNCHU Stage 1: verification_code, demo_session tables and user.employee_id

Revision ID: c1d2e3f4a5b6
Revises: 3781e22d8b01
Create Date: 2026-03-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from open_webui.migrations.util import get_existing_tables

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "3781e22d8b01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    # Add employee_id to user table
    if "user" in existing_tables:
        try:
            op.add_column(
                "user", sa.Column("employee_id", sa.String(50), nullable=True)
            )
        except Exception:
            pass

    # Create verification_code table
    if "verification_code" not in existing_tables:
        op.create_table(
            "verification_code",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("code", sa.String(6), nullable=True),
            sa.Column("purpose", sa.String(), nullable=True),
            sa.Column("expires_at", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=True),
            sa.Column("used", sa.Boolean(), nullable=True, default=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_verification_code_email", "verification_code", ["email"]
        )

    # Create demo_session table
    if "demo_session" not in existing_tables:
        op.create_table(
            "demo_session",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("login_date", sa.String(), nullable=True),
            sa.Column("login_at", sa.BigInteger(), nullable=True),
            sa.Column("expires_at", sa.BigInteger(), nullable=True),
            sa.Column("logged_out", sa.Boolean(), nullable=True, default=False),
            sa.Column("logged_out_at", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "login_date", name="uq_demo_session_user_date"
            ),
        )
        op.create_index("ix_demo_session_user_id", "demo_session", ["user_id"])


def downgrade() -> None:
    op.drop_table("demo_session")
    op.drop_table("verification_code")
    op.drop_column("user", "employee_id")
