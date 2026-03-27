"""
Database setup - SQLAlchemy async with SQLite (default).
Cross-platform: pathlib used for DB path.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Float, Text, JSON
from datetime import datetime, timezone
from typing import Optional
import uuid

from utils.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},  # needed for SQLite
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class EmailAnalysis(Base):
    __tablename__ = "email_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String(255))
    file_hash_sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Parsed header fields
    mail_from: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mail_to: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mail_subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mail_date: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    return_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reply_to: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    x_mailer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    x_originating_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    x_campaign_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Auth results
    spf_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    dkim_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    dmarc_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Analysis results (stored as JSON)
    header_indicators: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    body_indicators: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    url_indicators: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    attachment_indicators: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reputation_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Scoring
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # low/medium/high/critical
    risk_explanation: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Analyst notes
    analyst_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Dependency for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        yield session
