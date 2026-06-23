import asyncio
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.send_tasks.update_campaign_stats")
def update_campaign_stats(campaign_id: int, sent: int, failed: int, filtered: int):
    """Update campaign counters after a send batch completes."""
    asyncio.run(_update_stats(campaign_id, sent, failed, filtered))


async def _update_stats(campaign_id: int, sent: int, failed: int, filtered: int):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.db.models.campaigns import Campaign

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if campaign:
            campaign.total_sent += sent
            campaign.total_failed += failed
            campaign.total_filtered += filtered
            await db.commit()
