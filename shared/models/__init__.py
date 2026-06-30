import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    minio_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Pipeline processing fields (added in migration 0002)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lang: Mapped[str | None] = mapped_column(Text, nullable=True)
    bbox_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
