"""Blacklist + suppression filter for the send pipeline."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.suppression import Blacklist, SuppressionEntry


async def filter_recipients(
    recipients: list[dict],
    offer_id: int | None,
    db: AsyncSession,
) -> tuple[list[dict], int]:
    """
    Remove suppressed and blacklisted recipients.
    Returns (clean_list, filtered_count).
    """
    suppressed_emails: set[str] = set()
    if offer_id:
        sup_result = await db.execute(
            select(SuppressionEntry.email).where(SuppressionEntry.offer_id == offer_id)
        )
        suppressed_emails = {r.email.lower() for r in sup_result.all()}

    bl_result = await db.execute(select(Blacklist.email, Blacklist.domain))
    blacklisted_emails: set[str] = set()
    blacklisted_domains: set[str] = set()
    for row in bl_result.all():
        if row.email:
            blacklisted_emails.add(row.email.lower())
        if row.domain:
            blacklisted_domains.add(row.domain.lower())

    clean = []
    filtered = 0
    for recipient in recipients:
        email = recipient.get("email", "").lower()
        domain = email.split("@")[1] if "@" in email else ""

        if email in suppressed_emails or email in blacklisted_emails or domain in blacklisted_domains:
            filtered += 1
            continue
        clean.append(recipient)

    return clean, filtered
