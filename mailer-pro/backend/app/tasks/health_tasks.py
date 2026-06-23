import asyncio
from datetime import datetime, timezone
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.health_tasks.check_all_accounts")
def check_all_accounts():
    asyncio.run(_check_all_accounts_async())


async def _check_all_accounts_async():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.core.security import decrypt_secret
    from app.db.models.accounts import SenderAccount
    from app.services.proxy import full_account_health_check, rotate_account_proxy

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SenderAccount).where(SenderAccount.is_deleted == False)
        )
        accounts = result.scalars().all()

        for account in accounts:
            account_dict = {
                "email": account.email,
                "password": decrypt_secret(account.password) if account.password else "",
                "proxy_host": account.proxy_host,
                "proxy_port": account.proxy_port,
                "proxy_user": account.proxy_user,
                "proxy_pass": decrypt_secret(account.proxy_pass) if account.proxy_pass else None,
                "proxy_geo": account.proxy_geo,
            }

            health = await full_account_health_check(account_dict)
            account.status = health["status"]
            account.last_health_check = datetime.now(timezone.utc)

            if health["status"] == "proxy_error" and health.get("recommended_action") == "rotate_proxy":
                await rotate_account_proxy(account.id, account.proxy_geo or "US", db)

        await db.commit()
        print(f"[Health] Checked {len(accounts)} accounts at {datetime.now(timezone.utc)}")


@celery_app.task(name="app.tasks.health_tasks.reset_daily_counters")
def reset_daily_counters():
    asyncio.run(_reset_daily_counters_async())


async def _reset_daily_counters_async():
    from sqlalchemy import update
    from app.core.database import AsyncSessionLocal
    from app.db.models.accounts import SenderAccount

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(SenderAccount).values(daily_sent=0, daily_reset_at=datetime.now(timezone.utc))
        )
        await db.commit()
