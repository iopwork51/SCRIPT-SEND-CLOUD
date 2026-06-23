from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class AffiliateNetwork(Base):
    __tablename__ = "affiliate_networks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    affiliate_id: Mapped[str | None] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="activated")  # activated | deactivated
    website_url: Mapped[str | None] = mapped_column(String)

    username: Mapped[str | None] = mapped_column(String)
    password: Mapped[str | None] = mapped_column(String)

    api_platform: Mapped[str] = mapped_column(String, default="none")  # none|everflow|cake|hitpath|custom
    network_id: Mapped[str | None] = mapped_column(String)
    company_name: Mapped[str | None] = mapped_column(String)
    api_key: Mapped[str | None] = mapped_column(String)
    api_username: Mapped[str | None] = mapped_column(String)
    api_password: Mapped[str | None] = mapped_column(String)

    # {"sub1": ["mailer_id", "list_id"], "sub2": ["process_id"], "sub3": ["email_id"]}
    sub_config: Mapped[dict] = mapped_column(JSONB, default=dict)

    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    offers: Mapped[list["Offer"]] = relationship(back_populates="network")
