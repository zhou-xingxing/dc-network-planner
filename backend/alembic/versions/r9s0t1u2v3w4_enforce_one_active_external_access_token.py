"""enforce one active external access token per user

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
Create Date: 2026-07-16 00:00:00.000000
"""

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

from sqlalchemy import text

from alembic import op

revision: str = "r9s0t1u2v3w4"
down_revision: Union[str, None] = "q8r9s0t1u2v3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """保留每位用户最新的有效令牌，并撤销其余令牌。"""
    connection = op.get_bind()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    active_tokens = connection.execute(
        text(
            """
            SELECT id, user_id
            FROM external_access_tokens
            WHERE revoked_at IS NULL AND expires_at > :now
            ORDER BY user_id, created_at DESC, id DESC
            """
        ),
        {"now": now},
    ).mappings()

    retained_user_ids: set[str] = set()
    token_ids_to_revoke: list[str] = []
    for token in active_tokens:
        if token["user_id"] in retained_user_ids:
            token_ids_to_revoke.append(token["id"])
        else:
            retained_user_ids.add(token["user_id"])

    for token_id in token_ids_to_revoke:
        connection.execute(
            text(
                """
                UPDATE external_access_tokens
                SET revoked_at = :now
                WHERE id = :token_id AND revoked_at IS NULL
                """
            ),
            {"now": now, "token_id": token_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO change_logs (
                    id, entity_type, entity_id, entity_name, action,
                    old_value, new_value, operator, operation_method, comment, created_at
                ) VALUES (
                    :id, :entity_type, :entity_id, :entity_name, :action,
                    :old_value, :new_value, :operator, :operation_method, :comment, :created_at
                )
                """
            ),
            {
                "id": str(uuid4()),
                "entity_type": "external_access_token",
                "entity_id": token_id,
                "entity_name": "外部 API 访问令牌",
                "action": "revoke",
                "old_value": "状态=有效",
                "new_value": "状态=已撤销",
                "operator": "system",
                "operation_method": "system",
                "comment": "启用单令牌策略时自动撤销旧令牌",
                "created_at": now,
            },
        )


def downgrade() -> None:
    """数据撤销不可逆，保留已撤销令牌状态。"""
