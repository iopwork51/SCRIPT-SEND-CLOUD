from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, func, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    network_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("affiliate_networks.id"))
    external_id: Mapped[str | None] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    tracking_url: Mapped[str | None] = mapped_column(String)
    preview_url: Mapped[str | None] = mapped_column(String)

    payout: Mapped[float | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    suggested_subject: Mapped[str | None] = mapped_column(String)
    suggested_from_name: Mapped[str | None] = mapped_column(String)
    html_creative: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_sends_per_day: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    network: Mapped["AffiliateNetwork | None"] = relationship(back_populates="offers")
    data_fields: Mapped[list["OfferDataField"]] = relationship(back_populates="offer", cascade="all, delete-orphan")
    suppression_entries: Mapped[list["SuppressionEntry"]] = relationship(back_populates="offer", cascade="all, delete-orphan")


class OfferDataField(Base):
    __tablename__ = "offer_data_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offer_id: Mapped[int] = mapped_column(Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False)
    field_key: Mapped[str] = mapped_column(String, nullable=False)
    field_value: Mapped[str | None] = mapped_column(Text)
    data_type: Mapped[str] = mapped_column(String, default="text")  # text|url|number|html
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    offer: Mapped["Offer"] = relationship(back_populates="data_fields")
