from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ProxyProvider(Base):
    __tablename__ = "proxy_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)   # webshare | dataimpulse
    label: Mapped[str] = mapped_column(String, nullable=False)  # display name
    api_key: Mapped[str | None] = mapped_column(String)         # encrypted
    api_user: Mapped[str | None] = mapped_column(String)
    api_pass: Mapped[str | None] = mapped_column(String)        # encrypted (DataImpulse dashboard pass)
    # Rotating proxy gateway (DataImpulse)
    proxy_host: Mapped[str | None] = mapped_column(String)
    proxy_port: Mapped[int | None] = mapped_column(Integer)
    proxy_username: Mapped[str | None] = mapped_column(String)
    proxy_password: Mapped[str | None] = mapped_column(String)  # encrypted
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    proxies: Mapped[list["Proxy"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )


class Proxy(Base):
    __tablename__ = "proxies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("proxy_providers.id", ondelete="SET NULL")
    )
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String)
    password: Mapped[str | None] = mapped_column(String)  # encrypted
    geo: Mapped[str | None] = mapped_column(String(5))
    proxy_type: Mapped[str] = mapped_column(String, default="http")  # http | socks5
    is_rotating: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="untested")  # active | failed | untested
    last_tested: Mapped[datetime | None] = mapped_column(DateTime)
    exit_ip: Mapped[str | None] = mapped_column(String)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    provider: Mapped["ProxyProvider | None"] = relationship(back_populates="proxies")
