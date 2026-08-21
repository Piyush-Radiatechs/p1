"""SQLAlchemy models for users, search history, and result tables."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    searches: Mapped[list["Search"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Search(Base):
    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    source: Mapped[str] = mapped_column(String(16), default="file")
    filename: Mapped[str] = mapped_column(String(255), default="")
    requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    queries: Mapped[list] = mapped_column(JSON, default=list)
    searches_run: Mapped[int] = mapped_column(Integer, default=0)
    candidates_found: Mapped[int] = mapped_column(Integer, default=0)
    raw_results_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="searches")
    results: Mapped[list["SearchResult"]] = relationship(
        back_populates="search",
        cascade="all, delete-orphan",
        order_by="SearchResult.display_order",
    )


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id", ondelete="CASCADE"), index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    name_title: Mapped[str] = mapped_column(String(255), default="")
    search_title: Mapped[str] = mapped_column(String(512), default="")
    linkedin_url: Mapped[str] = mapped_column(String(512), default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    found_in_queries: Mapped[list] = mapped_column(JSON, default=list)

    search: Mapped["Search"] = relationship(back_populates="results")
