from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DB
from app.db.models.campaigns import Campaign, CampaignAccountGroup, CampaignRecipientList, SendLog
from app.db.models.accounts import SenderAccount, SenderGroup
from app.db.models.recipients import Recipient, RecipientList
from app.db.models.suppression import Blacklist, SuppressionEntry
from app.db.models.offers import Offer

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    name: str
    header_template: str | None = None
    body_html: str | None = None
    negative_content: str | None = None
    links: list[str] = []
    offer_id: int | None = None
    group_ids: list[int] = []
    list_ids: list[int] = []
    batch_size: int = 1
    sleep_between: int = 3
    max_workers: int = 5
    send_mode: str = "mx_direct"


class CampaignUpdate(BaseModel):
    name: str | None = None
    header_template: str | None = None
    body_html: str | None = None
    negative_content: str | None = None
    links: list[str] | None = None
    offer_id: int | None = None
    group_ids: list[int] | None = None
    list_ids: list[int] | None = None
    batch_size: int | None = None
    sleep_between: int | None = None
    max_workers: int | None = None
    send_mode: str | None = None


class TestEmailRequest(BaseModel):
    to_email: str


class GenerateScriptRequest(BaseModel):
    direct_recipients: list[str] = []   # pasted emails, bypass lists


def campaign_to_dict(c: Campaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "offer_id": c.offer_id,
        "batch_size": c.batch_size,
        "sleep_between": c.sleep_between,
        "max_workers": c.max_workers,
        "send_mode": c.send_mode,
        "status": c.status,
        "total_recipients": c.total_recipients,
        "total_sent": c.total_sent,
        "total_failed": c.total_failed,
        "total_filtered": c.total_filtered,
        "started_at": c.started_at,
        "completed_at": c.completed_at,
        "created_at": c.created_at,
    }


@router.get("")
async def list_campaigns(db: DB, current_user: CurrentUser, page: int = 1, page_size: int = 50):
    q = select(Campaign).where(Campaign.is_deleted == False)
    if current_user.role != "admin":
        q = q.where(Campaign.user_id == current_user.id)
    q = q.order_by(Campaign.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return [campaign_to_dict(c) for c in result.scalars().all()]


@router.post("", status_code=201)
async def create_campaign(body: CampaignCreate, db: DB, current_user: CurrentUser):
    campaign = Campaign(
        name=body.name,
        header_template=body.header_template,
        body_html=body.body_html,
        negative_content=body.negative_content,
        links=body.links,
        offer_id=body.offer_id,
        batch_size=body.batch_size,
        sleep_between=body.sleep_between,
        max_workers=body.max_workers,
        send_mode=body.send_mode,
        user_id=current_user.id,
    )
    db.add(campaign)
    await db.flush()

    for gid in body.group_ids:
        db.add(CampaignAccountGroup(campaign_id=campaign.id, group_id=gid))
    for lid in body.list_ids:
        db.add(CampaignRecipientList(campaign_id=campaign.id, list_id=lid))

    await db.commit()
    await db.refresh(campaign)
    return campaign_to_dict(campaign)


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(Campaign)
        .where(Campaign.id == campaign_id, Campaign.is_deleted == False)
        .options(selectinload(Campaign.account_groups), selectinload(Campaign.recipient_lists))
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    data = campaign_to_dict(campaign)
    data["group_ids"] = [g.group_id for g in campaign.account_groups]
    data["list_ids"] = [l.list_id for l in campaign.recipient_lists]
    data["header_template"] = campaign.header_template
    data["body_html"] = campaign.body_html
    data["negative_content"] = campaign.negative_content
    data["links"] = campaign.links or []
    return data


@router.put("/{campaign_id}")
async def update_campaign(campaign_id: int, body: CampaignUpdate, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.is_deleted == False))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    for field, value in body.model_dump(exclude_none=True).items():
        if field == "group_ids":
            await db.execute(
                CampaignAccountGroup.__table__.delete().where(CampaignAccountGroup.campaign_id == campaign_id)
            )
            for gid in value:
                db.add(CampaignAccountGroup(campaign_id=campaign_id, group_id=gid))
        elif field == "list_ids":
            await db.execute(
                CampaignRecipientList.__table__.delete().where(CampaignRecipientList.campaign_id == campaign_id)
            )
            for lid in value:
                db.add(CampaignRecipientList(campaign_id=campaign_id, list_id=lid))
        else:
            setattr(campaign, field, value)

    await db.commit()
    return campaign_to_dict(campaign)


@router.post("/{campaign_id}/preview")
async def send_test_email(campaign_id: int, body: TestEmailRequest, db: DB, current_user: CurrentUser):
    from app.services.mailer import send_test_via_account
    from app.core.security import decrypt_secret

    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get first active account
    acc_result = await db.execute(
        select(SenderAccount).where(SenderAccount.status == "active", SenderAccount.is_deleted == False).limit(1)
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=400, detail="No active account available for test")

    account_dict = {
        "email": account.email,
        "password": decrypt_secret(account.password),
        "proxy_host": account.proxy_host,
        "proxy_port": account.proxy_port,
        "proxy_user": account.proxy_user,
        "proxy_pass": decrypt_secret(account.proxy_pass) if account.proxy_pass else None,
    }

    result_data = await send_test_via_account(account_dict, body.to_email, campaign)
    return result_data


@router.post("/{campaign_id}/generate-script")
async def generate_script(
    campaign_id: int,
    db: DB,
    current_user: CurrentUser,
    body: GenerateScriptRequest | None = None,
):
    from app.services.script_gen import generate_campaign_script
    from app.core.security import decrypt_secret

    result = await db.execute(
        select(Campaign)
        .where(Campaign.id == campaign_id)
        .options(selectinload(Campaign.account_groups), selectinload(Campaign.recipient_lists))
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    mode = (campaign.send_mode or "mx_direct").lower()

    # Collect accounts from groups (only needed for proxy/smtp modes)
    group_ids = [g.group_id for g in campaign.account_groups]
    accounts_data = []
    if group_ids:
        acc_result = await db.execute(
            select(SenderAccount)
            .where(SenderAccount.group_id.in_(group_ids), SenderAccount.status == "active", SenderAccount.is_deleted == False)
        )
        accounts = acc_result.scalars().all()
        accounts_data = [
            {
                "id": a.id,
                "email": a.email,
                "password": decrypt_secret(a.password),
                "proxy_host": a.proxy_host,
                "proxy_port": a.proxy_port,
                "proxy_user": a.proxy_user,
                "proxy_pass": decrypt_secret(a.proxy_pass) if a.proxy_pass else None,
                "proxy_geo": a.proxy_geo,
            }
            for a in accounts
        ]

    # Proxy/smtp modes require at least one account with a proxy
    if mode in ("smtp", "mx_proxy", "gmail_api") and not accounts_data:
        raise HTTPException(
            status_code=400,
            detail="This send mode needs sender accounts with proxies. Select a Server group, or switch to MX Direct (basic) which needs none.",
        )

    # Collect recipients from lists
    list_ids = [l.list_id for l in campaign.recipient_lists]
    recipients = []
    if list_ids:
        rec_result = await db.execute(
            select(Recipient.email, Recipient.name)
            .where(Recipient.list_id.in_(list_ids), Recipient.status == "active")
        )
        recipients = [{"email": r.email, "name": r.name} for r in rec_result.all()]

    # Merge pasted direct recipients
    if body and body.direct_recipients:
        seen = {r["email"].lower() for r in recipients}
        for raw in body.direct_recipients:
            em = raw.strip()
            if em and "@" in em and em.lower() not in seen:
                recipients.append({"email": em, "name": None})
                seen.add(em.lower())

    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients — select a list or paste direct recipients.")

    # Filter suppression + blacklist
    if campaign.offer_id:
        sup_result = await db.execute(
            select(SuppressionEntry.email).where(SuppressionEntry.offer_id == campaign.offer_id)
        )
        suppressed = {r.email for r in sup_result.all()}
    else:
        suppressed = set()

    bl_result = await db.execute(select(Blacklist.email, Blacklist.domain))
    bl_emails = set()
    bl_domains = set()
    for row in bl_result.all():
        if row.email:
            bl_emails.add(row.email)
        if row.domain:
            bl_domains.add(row.domain)

    clean_recipients = []
    for r in recipients:
        email = r["email"].lower()
        domain = email.split("@")[1] if "@" in email else ""
        if email in suppressed or email in bl_emails or domain in bl_domains:
            continue
        clean_recipients.append(r)

    script = generate_campaign_script(campaign, accounts_data, clean_recipients)
    return {
        "script": script,
        "total_recipients": len(recipients),
        "filtered_count": len(recipients) - len(clean_recipients),
        "final_count": len(clean_recipients),
        "accounts_count": len(accounts_data),
        "cloud_console_url": "https://console.cloud.google.com/cloudshelleditor",
    }


@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "running"
    campaign.started_at = datetime.now(timezone.utc)
    await db.commit()
    return {"detail": "Campaign started", "status": "running"}


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = "paused"
    await db.commit()
    return {"detail": "Campaign paused"}


@router.get("/{campaign_id}/stats")
async def campaign_stats(campaign_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    domain_result = await db.execute(
        select(
            func.split_part(SendLog.recipient_email, "@", 2).label("domain"),
            func.count().label("count"),
        )
        .where(SendLog.campaign_id == campaign_id, SendLog.status == "sent")
        .group_by("domain")
        .order_by(func.count().desc())
        .limit(10)
    )

    return {
        "total_recipients": campaign.total_recipients,
        "total_sent": campaign.total_sent,
        "total_failed": campaign.total_failed,
        "total_filtered": campaign.total_filtered,
        "status": campaign.status,
        "top_domains": [{"domain": r.domain, "count": r.count} for r in domain_result.all()],
    }


@router.get("/{campaign_id}/logs")
async def campaign_logs(campaign_id: int, db: DB, current_user: CurrentUser, page: int = 1, page_size: int = 50):
    result = await db.execute(
        select(SendLog)
        .where(SendLog.campaign_id == campaign_id)
        .order_by(SendLog.sent_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "recipient_email": l.recipient_email,
            "status": l.status,
            "mx_server": l.mx_server,
            "proxy_host": l.proxy_host,
            "message_id": l.message_id,
            "error_message": l.error_message,
            "sent_at": l.sent_at,
        }
        for l in logs
    ]
