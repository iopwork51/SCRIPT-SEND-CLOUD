from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.db.models.users import User
from app.api.routes import auth, users, accounts, groups, recipients, affiliates, offers, blacklist, campaigns

limiter = Limiter(key_func=get_remote_address)


async def seed_admin():
    import sys
    import logging
    logger = logging.getLogger("mailerpro.seed")
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == "admin@mailerpro.com"))
            existing = result.scalar_one_or_none()
            hashed = hash_password("admin123")
            if not existing:
                db.add(User(
                    email="admin@mailerpro.com",
                    password_hash=hashed,
                    full_name="Admin",
                    role="admin",
                    is_active=True,
                ))
                await db.commit()
                logger.warning("SEED: admin user created")
            else:
                # Always reset password to ensure it's correct
                from sqlalchemy import update
                await db.execute(
                    update(User).where(User.email == "admin@mailerpro.com").values(
                        password_hash=hashed, is_active=True, role="admin"
                    )
                )
                await db.commit()
                logger.warning("SEED: admin user password reset")
    except Exception as e:
        logger.error(f"SEED ERROR: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_admin()
    yield


app = FastAPI(
    title="MailerPro API",
    lifespan=lifespan,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(groups.router, prefix="/api")
app.include_router(recipients.router, prefix="/api")
app.include_router(affiliates.router, prefix="/api")
app.include_router(offers.router, prefix="/api")
app.include_router(blacklist.router, prefix="/api")
app.include_router(blacklist.suppression_router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
