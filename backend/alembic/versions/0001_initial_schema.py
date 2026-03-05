"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("market_summary", sa.Text(), nullable=True),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_reports_user_id", "reports", ["user_id"])

    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("change_pct", sa.Float(), nullable=True),
    )
    op.create_index("ix_market_snapshots_user_id", "market_snapshots", ["user_id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("symbol", sa.String(50), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("seen", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_alerts_user_id", "alerts", ["user_id"])

    op.create_table(
        "portfolio",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, server_default=""),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("buy_price", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("buy_currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("buy_fx_to_usd", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("buy_price_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tab_type", sa.String(20), nullable=False, server_default="zakupione"),
    )
    op.create_index("ix_portfolio_user_id", "portfolio", ["user_id"])

    op.create_table(
        "instrument_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("profile_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.UniqueConstraint("user_id", "symbol", name="uq_user_symbol_profile"),
    )
    op.create_index("ix_instrument_profiles_user_id", "instrument_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_table("instrument_profiles")
    op.drop_table("portfolio")
    op.drop_table("alerts")
    op.drop_table("market_snapshots")
    op.drop_table("reports")
    op.drop_table("users")
