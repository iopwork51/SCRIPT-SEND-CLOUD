from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class RecipientList(Base):
    __tablename__ = "recipient_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    active_count: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    recipients: Mapped[list["Recipient"]] = relationship(back_populates="list", cascade="all, delete-orphan")


class Recipient(Base):
    __tablename__ = "recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String)
    list_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipient_lists.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")  # active|unsubscribed|bounced|suppressed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    list: Mapped["RecipientList"] = relationship(back_populates="recipients")

    __table_args__ = (
        Index("idx_recipients_list_id", "list_id"),
    )
