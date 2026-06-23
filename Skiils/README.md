# MailerPro — Bulk Email Sending Platform

Professional bulk email sending platform with affiliate network integration, proxy-per-account management, and Google Cloud Console deployment.

## Tech Stack

- **Backend**: Python 3.11 + FastAPI (async)
- **Database**: PostgreSQL 15 + SQLAlchemy async ORM + Alembic migrations
- **Queue**: Redis 7 + Celery 5 (async task processing)
- **Frontend**: React 18 + TailwindCSS + shadcn/ui
- **Proxy**: Webshare API (GB residential rotation)
- **Deploy**: Google Cloud Run + Cloud SQL (PostgreSQL)
- **Auth**: JWT (access 1h + refresh 7d) + bcrypt

## Project Structure

```
mailer-pro/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── accounts.py        # Sender Gmail/GSuite accounts
│   │   │       ├── groups.py          # Account groups
│   │   │       ├── recipients.py      # Recipient lists
│   │   │       ├── affiliates.py      # Affiliate networks (sponsors)
│   │   │       ├── offers.py          # Offers per affiliate
│   │   │       ├── campaigns.py       # Campaign management
│   │   │       ├── send.py            # Send operations
│   │   │       ├── blacklist.py       # Blacklist management
│   │   │       └── suppression.py     # Suppression lists
│   │   ├── core/
│   │   │   ├── config.py              # Settings & env vars
│   │   │   ├── security.py            # JWT + password hashing
│   │   │   └── database.py            # Async DB connection
│   │   ├── db/
│   │   │   └── models/                # All SQLAlchemy models
│   │   ├── services/
│   │   │   ├── mailer.py              # Core send engine (MX direct)
│   │   │   ├── proxy.py               # Webshare API + health check
│   │   │   ├── tags.py                # Template tag engine
│   │   │   ├── script_gen.py          # Cloud Console Python script generator
│   │   │   ├── affiliate_apis.py      # Everflow, Cake, HitPath, custom APIs
│   │   │   └── lists.py               # Blacklist/Suppression filter
│   │   └── tasks/
│   │       ├── send_tasks.py          # Celery async send tasks
│   │       └── health_tasks.py        # Proxy/account health checks
│   ├── alembic/                       # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Accounts.jsx           # Gmail/GSuite + proxy management
│   │   │   ├── Groups.jsx
│   │   │   ├── Recipients.jsx
│   │   │   ├── Affiliates.jsx         # Affiliate networks CRUD
│   │   │   ├── Offers.jsx             # Offers per affiliate
│   │   │   ├── Campaigns.jsx
│   │   │   ├── Send.jsx               # Main send page
│   │   │   ├── Blacklist.jsx
│   │   │   └── Stats.jsx
│   │   ├── components/
│   │   └── hooks/
│   └── package.json
├── docker-compose.yml
└── docs/
    ├── README.md                      # This file
    ├── SKILL_ACCOUNTS.md              # How to add Gmail/GSuite accounts
    ├── SKILL_AFFILIATES.md            # Affiliate networks integration
    ├── SKILL_OFFERS.md                # How offers work
    ├── SKILL_TAGS.md                  # All template tags reference
    ├── SKILL_SEND.md                  # Send flow guide
    └── SKILL_PROXY.md                 # Proxy setup with Webshare
```
