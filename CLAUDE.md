# Blackgrid Bot — Development Guide

## What This Is

A **Telegram bot** for managing a service-based business. Built for quotation creation, invoicing, payment tracking, customer management, scheduling (with Google Calendar sync), and business reporting — all from Telegram.

This is a whitelabel system. The company name, branding, and all business details are configured via environment variables — no code changes needed to rebrand.

## Tech Stack

- **Python 3.12** with async throughout
- **python-telegram-bot 21.6** — Telegram bot framework (PTB)
- **SQLAlchemy 2.x (async)** — ORM with `aiosqlite` (local) / `asyncpg` (production)
- **FastAPI + Uvicorn** — Health check endpoint for Railway
- **WeasyPrint** — PDF generation for quotations and invoices
- **Jinja2** — HTML templates for PDFs
- **Google Calendar API** — Site visit scheduling sync
- **Railway** — Deployment platform (Dockerfile-based)

## Project Structure

```
app/
├── main.py                    # Entry point: DB init, handler registration, bot + API startup
├── config.py                  # Pydantic settings (all env vars)
├── database.py                # SQLAlchemy async engine + session factory
├── bot/
│   ├── filters.py             # admin_filter — restricts bot to allowed user IDs
│   ├── keyboards.py           # All InlineKeyboardMarkup definitions
│   ├── states.py              # IntEnum conversation states per module
│   └── handlers/
│       ├── start.py           # /start, password auth, main menu routing
│       ├── customer.py        # CRUD: search, create, edit, list customers
│       ├── quotation.py       # Multi-step quotation builder with line items
│       ├── invoice.py         # Create from quotation, record payments
│       ├── calendar.py        # Book site visits, Google Calendar sync
│       ├── report.py          # Business dashboard: payments, pipeline, visits
│       └── settings.py        # Manage patterns (add, edit, toggle active)
├── models/                    # SQLAlchemy ORM models
│   ├── base.py                # Base class with UUID id + created_at
│   ├── customer.py            # name, phone, email, address, notes
│   ├── quotation.py           # quotation_number, status, line_items, totals
│   ├── invoice.py             # invoice_number, payment_status, amount_paid
│   ├── line_item.py           # per_sqft / lumpsum / custom pricing
│   ├── pattern.py             # Reusable service templates with rates
│   ├── site_visit.py          # Scheduled visits with Google Calendar sync
│   └── slot.py                # Time slot capacity management
├── services/                  # Business logic (no Telegram imports)
│   ├── customer_service.py
│   ├── quotation_service.py
│   ├── invoice_service.py
│   ├── slot_service.py        # Site visit CRUD + upcoming visits query
│   ├── calendar_service.py    # Google Calendar API + Malay date formatting
│   ├── report_service.py      # Aggregation queries for dashboard
│   └── pdf_service.py         # Jinja2 → WeasyPrint PDF generation
├── pdf/
│   ├── templates/             # quotation.html, invoice.html
│   └── assets/                # stamp.png (company stamp image)
└── api/
    └── routes.py              # GET /health endpoint
```

## Key Patterns — Follow These When Adding Features

### Handler Module Pattern

Every handler module follows the same structure:

1. **Create `app/bot/handlers/<feature>.py`**
2. Define async handler functions (each receives `Update` + `ContextTypes.DEFAULT_TYPE`)
3. For multi-step flows, use `ConversationHandler` with states from `app/bot/states.py`
4. For simple button navigation, use plain `CallbackQueryHandler`
5. Export a `get_<feature>_handlers() -> list` function
6. Register in `app/main.py` → `register_handlers()`

```python
# Callback data prefix convention: use a short prefix per module
# quot_*, inv_*, cal_*, cust_*, rpt_*, set_*

def get_feature_handlers() -> list:
    return [
        ConversationHandler(...),          # Multi-step flows
        CallbackQueryHandler(fn, pattern="^prefix_action$"),  # Button handlers
    ]
```

### Database Access Pattern

Always use the async session factory. Services handle queries, handlers call services.

```python
from app.database import async_session

async def some_handler(update, context):
    async with async_session() as session:
        result = await some_service.some_function(session, ...)
```

### Service Layer Pattern

Services live in `app/services/`. They accept an `AsyncSession` as first argument, use `select()` with `selectinload()` for eager loading, and return model objects or lists.

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

async def get_thing(session: AsyncSession, thing_id: str):
    stmt = (
        select(Thing)
        .options(selectinload(Thing.related))
        .where(Thing.id == thing_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
```

### Message Formatting

- Always use `parse_mode="Markdown"`
- Headers: `"📊 *Title*\n━━━━━━━━━━━━━━━━━━"`
- Money: `f"RM{amount:,.2f}"`
- Status emojis are standard throughout the app

### Adding to Main Menu

1. Add button in `app/bot/keyboards.py` → `main_menu_keyboard()`
2. Add handler registration in `app/main.py`
3. The callback pattern `menu_<feature>` is handled by the feature's own handler module

## Data Model Quick Reference

### Statuses

| Model     | Statuses                                         |
|-----------|--------------------------------------------------|
| Quotation | `draft` → `sent` → `accepted` / `rejected` / `expired` |
| Invoice   | `unpaid` → `partial` → `paid`                   |
| SiteVisit | `scheduled` / `cancelled`                        |

### Relationships

- **Customer** → has many Quotations, Invoices, SiteVisits
- **Quotation** → has many LineItems, has one Invoice (optional)
- **Invoice** → belongs to one Quotation and one Customer
- **LineItem** → belongs to Quotation, optionally references a Pattern
- **SiteVisit** → belongs to Customer

### Pricing Types (LineItem)

- `per_sqft` — area_sqft × rate_per_sqft
- `lumpsum` — fixed amount
- `custom` — quantity × unit_price, with selectable unit (SQFT, UNIT, METER, LOT, SET, LS, PCS, TRIP)

## Environment Variables

All config is in `app/config.py`. Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | From @BotFather |
| `ADMIN_CHAT_ID` | Yes | Primary admin's Telegram user ID |
| `ALLOWED_USER_IDS` | No | Comma-separated additional user IDs |
| `BOT_PASSWORD` | No | Password to access bot (default: `changeme`) |
| `DATABASE_URL` | No | Defaults to local SQLite; use `postgresql+asyncpg://` in production |
| `COMPANY_NAME` | No | Your company name (shown in bot and PDFs) |
| `COMPANY_PHONE` | No | Shown on PDF documents |
| `COMPANY_SSM` | No | Business registration number |
| `COMPANY_ADDRESS` | No | Shown on PDF documents |
| `AUTHORIZED_BY` | No | Name on quotation/invoice signatures |
| `BANK_NAME` | No | For invoice payment details |
| `BANK_ACCOUNT` | No | Bank account number |
| `BANK_HOLDER` | No | Account holder name |
| `GOOGLE_CREDENTIALS_JSON` | No | Service account JSON for Calendar API |
| `GOOGLE_CALENDAR_ID` | No | Google Calendar ID for site visit sync |
| `PORT` | No | Server port (default: 8000) |

## Running Locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Fill in TELEGRAM_BOT_TOKEN and ADMIN_CHAT_ID at minimum
python -m app.main
```

Note: WeasyPrint requires system libraries (Pango, Cairo). On macOS: `brew install pango`. The Dockerfile handles this for production.

## Deploying to Railway

1. Push to GitHub
2. Connect repo in Railway
3. Set all required env vars (at minimum: `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID`, `DATABASE_URL`)
4. Railway auto-detects the Dockerfile and deploys
5. Health check at `/health` confirms the service is running

## Common Tasks

### Adding a new handler module
1. Create `app/bot/handlers/myfeature.py`
2. Add states to `app/bot/states.py` if using ConversationHandler
3. Add keyboard(s) to `app/bot/keyboards.py` if needed
4. Add `get_myfeature_handlers()` export
5. Import and register in `app/main.py`

### Adding a new model
1. Create `app/models/mymodel.py` inheriting from `Base` (in `app/models/base.py`)
2. Import it in `app/models/__init__.py` so `Base.metadata.create_all` picks it up
3. Create `app/services/mymodel_service.py` for queries

### Modifying PDF templates
- Templates are in `app/pdf/templates/` (Jinja2 HTML)
- Company stamp image at `app/pdf/assets/stamp.png`
- All company/bank details come from env vars via `pdf_service.py`
- Test by generating a quotation or invoice through the bot

### Customizing default patterns
- Default patterns are seeded in `app/main.py` → `seed_patterns()`
- These only seed once (skips if any patterns exist)
- Users can add/edit/toggle patterns via the Settings menu in the bot
