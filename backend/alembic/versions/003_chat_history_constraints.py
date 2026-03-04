"""Add unique constraint and cascade on conversations

Revision ID: 003_chat_history_constraints
Revises: 002_chat_history
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op

revision: str = '003_chat_history_constraints'
down_revision: Union[str, None] = '002_chat_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint on conversations.user_id (prevents duplicate conversations)
    op.create_unique_constraint(
        'uq_conversations_user_id', 'conversations', ['user_id']
    )

    # Add CASCADE to conversations.user_id FK (so deleting a user deletes their conversation)
    op.drop_constraint('conversations_user_id_fkey', 'conversations', type_='foreignkey')
    op.create_foreign_key(
        'conversations_user_id_fkey',
        'conversations', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('conversations_user_id_fkey', 'conversations', type_='foreignkey')
    op.create_foreign_key(
        'conversations_user_id_fkey',
        'conversations', 'users',
        ['user_id'], ['id'],
    )
    op.drop_constraint('uq_conversations_user_id', 'conversations', type_='unique')
