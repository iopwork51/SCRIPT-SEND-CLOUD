from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Blacklist(Base):
    __tablename__ = "blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str | None] = mapped_column(String, index=True)
    domain: Mapped[str | None] = mapped_column(String, index=True)
    reason: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="manual")  # manual|bounce|import|offer
    offer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("offers.id"))
    added_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SuppressionEntry(Base):
    __tablename__ = "suppression_list"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    offer_id: Mapped[int] = mapped_column(Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    offer: Mapped["Offer"] = relationship(back_populates="suppression_entries")

    __table_args__ = (
        Index("idx_suppression_email_offer", "email", "offer_id"),
    )
