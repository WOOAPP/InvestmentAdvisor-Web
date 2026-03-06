"""add token_usage table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("request_type", sa.String(50), nullable=False, server_default="chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_token_usage_user_id", "token_usage", ["user_id"])
    op.create_index("ix_token_usage_created_at", "token_usage", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_token_usage_created_at", "token_usage")
    op.drop_index("ix_token_usage_user_id", "token_usage")
    op.drop_table("token_usage")
