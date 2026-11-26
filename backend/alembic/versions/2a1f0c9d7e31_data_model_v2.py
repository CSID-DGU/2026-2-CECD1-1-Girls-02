"""data model v2 (API 명세 기준)

- 문의 상태 값 변경
- 문의 관련 필드 추가 및 불필요한 필드 제거
- 문의 카테고리 3단계 트리
- 매장 코드 및 챗봇 세션 키 추가
- AI 로그 및 출처 상세 필드 추가

Revision ID: 2a1f0c9d7e31
Revises: b40909aa9c7a
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2a1f0c9d7e31"
down_revision: Union[str, Sequence[str], None] = "b40909aa9c7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- inquiries ----------

    op.execute(
        "UPDATE inquiries SET status = 'DRAFT_GENERATING' "
        "WHERE status = 'RECEIVED'"
    )
    op.execute(
        "UPDATE inquiries SET status = 'PENDING_REVIEW' "
        "WHERE status IN ('AI_DRAFTED', 'ESCALATED')"
    )

    op.alter_column(
        "inquiries",
        "status",
        server_default="DRAFT_GENERATING",
    )

    op.add_column(
        "inquiries",
        sa.Column("category_path", sa.JSON(), nullable=True),
    )

    op.add_column(
        "inquiries",
        sa.Column(
            "inquiry_type",
            sa.Enum(
                "QUESTION",
                "SUGGESTION",
                "COMPLIMENT",
                "COMPLAINT",
                name="inquirytype",
                native_enum=False,
                length=32,
            ),
            server_default="QUESTION",
            nullable=False,
        ),
    )

    op.add_column(
        "inquiries",
        sa.Column("store_name", sa.String(100), nullable=True),
    )

    # 기존 매장 이름 보존
    op.execute("""
        UPDATE inquiries
        SET store_name = stores.name
        FROM stores
        WHERE inquiries.store_id = stores.id
    """)

    op.add_column(
        "inquiries",
        sa.Column(
            "privacy_consented_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "inquiries",
        sa.Column("summary", sa.Text(), nullable=True),
    )

    op.add_column(
        "inquiries",
        sa.Column("category_suggestion", sa.JSON(), nullable=True),
    )

    op.add_column(
        "inquiries",
        sa.Column("admin_memo", sa.Text(), nullable=True),
    )

    op.alter_column(
        "inquiries",
        "category_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    op.drop_constraint(
        "fk_inquiries_store_id_stores",
        "inquiries",
        type_="foreignkey",
    )

    op.drop_column("inquiries", "store_id")
    op.drop_column("inquiries", "customer_contact")

    # ---------- inquiry_categories ----------

    op.add_column(
        "inquiry_categories",
        sa.Column("parent_id", sa.Integer(), nullable=True),
    )

    op.add_column(
        "inquiry_categories",
        sa.Column(
            "depth",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )

    op.create_index(
        op.f("ix_inquiry_categories_parent_id"),
        "inquiry_categories",
        ["parent_id"],
        unique=False,
    )

    op.create_foreign_key(
        op.f("fk_inquiry_categories_parent_id_inquiry_categories"),
        "inquiry_categories",
        "inquiry_categories",
        ["parent_id"],
        ["id"],
    )

    # ---------- stores ----------

    op.add_column(
        "stores",
        sa.Column("code", sa.String(20), nullable=True),
    )

    op.execute("""
        UPDATE stores
        SET code = 'S' || LPAD(
            id::text,
            GREATEST(3, LENGTH(id::text)),
            '0'
        )
        WHERE code IS NULL
    """)

    op.alter_column(
        "stores",
        "code",
        existing_type=sa.String(20),
        nullable=False,
    )

    op.create_unique_constraint(
        op.f("uq_stores_brand_id"),
        "stores",
        ["brand_id", "code"],
    )

    # ---------- answer_drafts ----------

    op.alter_column(
        "answer_drafts",
        "action",
        existing_type=sa.VARCHAR(length=32),
        nullable=True,
    )

    # ---------- chat ----------

    op.add_column(
        "chat_conversations",
        sa.Column("session_key", sa.String(36), nullable=True),
    )

    # 기존 대화에 개별 UUID 부여
    import uuid

    connection = op.get_bind()
    conversation_ids = connection.execute(
        sa.text("SELECT id FROM chat_conversations")
    ).scalars().all()

    for conversation_id in conversation_ids:
        connection.execute(
            sa.text("""
                UPDATE chat_conversations
                SET session_key = :session_key
                WHERE id = :id
            """),
            {
                "session_key": str(uuid.uuid4()),
                "id": conversation_id,
            },
        )

    op.alter_column(
        "chat_conversations",
        "session_key",
        existing_type=sa.String(36),
        nullable=False,
    )

    op.create_index(
        op.f("ix_chat_conversations_session_key"),
        "chat_conversations",
        ["session_key"],
        unique=False,
    )

    op.add_column(
        "chat_messages",
        sa.Column(
            "decision",
            sa.Enum(
                "ANSWER",
                "HANDOFF",
                name="chatdecision",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
    )

    op.add_column(
        "chat_messages",
        sa.Column(
            "handoff_reason",
            sa.String(64),
            nullable=True,
        ),
    )

    # ---------- AI generation logs ----------

    op.add_column(
        "ai_generation_logs",
        sa.Column("request_id", sa.String(64), nullable=True),
    )

    op.add_column(
        "ai_generation_logs",
        sa.Column("input_tokens", sa.Integer(), nullable=True),
    )

    op.add_column(
        "ai_generation_logs",
        sa.Column("output_tokens", sa.Integer(), nullable=True),
    )

    op.create_index(
        op.f("ix_ai_generation_logs_request_id"),
        "ai_generation_logs",
        ["request_id"],
        unique=False,
    )

    # ---------- AI generation sources ----------

    op.add_column(
        "ai_generation_sources",
        sa.Column("document_id", sa.String(200), nullable=True),
    )

    op.add_column(
        "ai_generation_sources",
        sa.Column("title", sa.String(255), nullable=True),
    )

    op.add_column(
        "ai_generation_sources",
        sa.Column("excerpt", sa.Text(), nullable=True),
    )

    op.add_column(
        "ai_generation_sources",
        sa.Column("score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    # 분류가 없는 문의는 기존 NOT NULL 구조로 복원할 수 없다.
    # 데이터 자동 삭제 대신 downgrade를 중단한다.
    connection = op.get_bind()

    uncategorized_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM inquiries WHERE category_id IS NULL"
        )
    ).scalar_one()

    if uncategorized_count:
        raise RuntimeError(
            "분류가 없는 문의가 존재하여 downgrade할 수 없습니다."
        )

    # ---------- AI generation sources ----------

    op.drop_column("ai_generation_sources", "score")
    op.drop_column("ai_generation_sources", "excerpt")
    op.drop_column("ai_generation_sources", "title")
    op.drop_column("ai_generation_sources", "document_id")

    # ---------- AI generation logs ----------

    op.drop_index(
        op.f("ix_ai_generation_logs_request_id"),
        table_name="ai_generation_logs",
    )

    op.drop_column("ai_generation_logs", "output_tokens")
    op.drop_column("ai_generation_logs", "input_tokens")
    op.drop_column("ai_generation_logs", "request_id")

    # ---------- chat ----------

    op.drop_column("chat_messages", "handoff_reason")
    op.drop_column("chat_messages", "decision")

    op.drop_index(
        op.f("ix_chat_conversations_session_key"),
        table_name="chat_conversations",
    )

    op.drop_column("chat_conversations", "session_key")

    # ---------- answer_drafts ----------

    op.execute(
        "UPDATE answer_drafts "
        "SET action = 'ESCALATE' WHERE action IS NULL"
    )

    op.alter_column(
        "answer_drafts",
        "action",
        existing_type=sa.VARCHAR(length=32),
        nullable=False,
    )

    # ---------- stores ----------

    op.drop_constraint(
        op.f("uq_stores_brand_id"),
        "stores",
        type_="unique",
    )

    op.drop_column("stores", "code")

    # ---------- inquiry_categories ----------

    op.drop_constraint(
        op.f("fk_inquiry_categories_parent_id_inquiry_categories"),
        "inquiry_categories",
        type_="foreignkey",
    )

    op.drop_index(
        op.f("ix_inquiry_categories_parent_id"),
        table_name="inquiry_categories",
    )

    op.drop_column("inquiry_categories", "depth")
    op.drop_column("inquiry_categories", "parent_id")

    # ---------- inquiries ----------

    op.add_column(
        "inquiries",
        sa.Column(
            "customer_contact",
            sa.VARCHAR(length=100),
            server_default="",
            nullable=False,
        ),
    )

    op.alter_column(
        "inquiries",
        "customer_contact",
        server_default=None,
    )

    op.add_column(
        "inquiries",
        sa.Column("store_id", sa.INTEGER(), nullable=True),
    )

    op.create_foreign_key(
        "fk_inquiries_store_id_stores",
        "inquiries",
        "stores",
        ["store_id"],
        ["id"],
    )

    op.alter_column(
        "inquiries",
        "category_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.drop_column("inquiries", "admin_memo")
    op.drop_column("inquiries", "category_suggestion")
    op.drop_column("inquiries", "summary")
    op.drop_column("inquiries", "privacy_consented_at")
    op.drop_column("inquiries", "store_name")
    op.drop_column("inquiries", "inquiry_type")
    op.drop_column("inquiries", "category_path")

    op.alter_column(
        "inquiries",
        "status",
        server_default="RECEIVED",
    )

    op.execute(
        "UPDATE inquiries SET status = 'RECEIVED' "
        "WHERE status = 'DRAFT_GENERATING'"
    )

    op.execute(
        "UPDATE inquiries SET status = 'AI_DRAFTED' "
        "WHERE status IN ('PENDING_REVIEW', 'IN_REVIEW')"
    )

    op.execute(
        "UPDATE inquiries SET status = 'ANSWERED' "
        "WHERE status = 'CLOSED'"
    )