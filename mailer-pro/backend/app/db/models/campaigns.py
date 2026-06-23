from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, func, Text, ARRAY, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))

    header_template: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    negative_content: Mapped[str | None] = mapped_column(Text)
    links: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    offer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("offers.id"))

    batch_size: Mapped[int] = mapped_column(Integer, default=1)
    sleep_between: Mapped[int] = mapped_column(Integer, default=3)
    max_workers: Mapped[int] = mapped_column(Integer, default=5)
    send_mode: Mapped[str] = mapped_column(String, default="mx_direct")  # mx_direct|smtp

    status: Mapped[str] = mapped_column(String, default="draft")  # draft|running|paused|completed|failed
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    total_sent: Mapped[int] = mapped_column(Integer, default=0)
    total_failed: Mapped[int] = mapped_column(Integer, default=0)
    total_filtered: Mapped[int] = mapped_column(Integer, default=0)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account_groups: Mapped[list["CampaignAccountGroup"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    recipient_lists: Mapped[list["CampaignRecipientList"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    logs: Mapped[list["SendLog"]] = relationship(back_populates="campaign")


class CampaignAccountGroup(Base):
    __tablename__ = "campaign_account_groups"

    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("sender_groups.id"), primary_key=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="account_groups")


class CampaignRecipientList(Base):
    __tablename__ = "campaign_recipient_lists"

    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id"), primary_key=True)
    list_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipient_lists.id"), primary_key=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="recipient_lists")


class SendLog(Base):
    __tablename__ = "send_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("campaigns.id"))
    account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sender_accounts.id"))
    recipient_email: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # sent|failed|bounced|filtered
    mx_server: Mapped[str | None] = mapped_column(String)
    proxy_host: Mapped[str | None] = mapped_column(String)
    message_id: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    campaign: Mapped["Campaign | None"] = relationship(back_populates="logs")

    __table_args__ = (
        Index("idx_send_logs_campaign", "campaign_id"),
        Index("idx_send_logs_status", "status"),
    )
