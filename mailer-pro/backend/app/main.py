from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.api.routes import auth, users, accounts, groups, recipients, affiliates, offers, blacklist, campaigns

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="MailerPro API",
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
