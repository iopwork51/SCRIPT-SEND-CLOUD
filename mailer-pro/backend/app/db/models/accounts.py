from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class SenderGroup(Base):
    __tablename__ = "sender_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    accounts: Mapped[list["SenderAccount"]] = relationship(back_populates="group")


class SenderAccount(Base):
    __tablename__ = "sender_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String, nullable=False)  # Fernet-encrypted App Password
    account_type: Mapped[str] = mapped_column(String, default="gmail")  # gmail | gsuite | smtp

    # Proxy config (Webshare GB)
    proxy_host: Mapped[str | None] = mapped_column(String)
    proxy_port: Mapped[int | None] = mapped_column(Integer)
    proxy_user: Mapped[str | None] = mapped_column(String)
    proxy_pass: Mapped[str | None] = mapped_column(String)  # Fernet-encrypted
    proxy_geo: Mapped[str | None] = mapped_column(String(5))
    proxy_type: Mapped[str] = mapped_column(String, default="webshare_gb")

    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sender_groups.id"))
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))

    # Health tracking
    status: Mapped[str] = mapped_column(String, default="testing")  # active|proxy_error|smtp_blocked|auth_failed|testing
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime)
    last_send: Mapped[datetime | None] = mapped_column(DateTime)
    total_sent: Mapped[int] = mapped_column(Integer, default=0)
    daily_sent: Mapped[int] = mapped_column(Integer, default=0)
    daily_reset_at: Mapped[datetime | None] = mapped_column(DateTime)

    max_per_day: Mapped[int] = mapped_column(Integer, default=500)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    group: Mapped["SenderGroup | None"] = relationship(back_populates="accounts")
