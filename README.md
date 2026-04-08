# Artisan Telegram Bot

A whitelabel Telegram bot for managing a service-based business. Handle quotations, invoices, payments, customers, scheduling, and reporting — all from Telegram.

Built for contractors, service providers, and small businesses who need a lightweight business management tool without a full web app.

## Features

- **Customer Management** — Create, search, edit, and list customers
- **Quotation Builder** — Multi-step quotation creation with line items (per sqft, lumpsum, custom pricing), PDF generation, and WhatsApp sharing
- **Invoice Management** — Create invoices from accepted quotations, record payments, track outstanding balances
- **Calendar & Scheduling** — Book site visits with Google Calendar sync, broadcast-ready messages
- **Business Reports** — Dashboard with payment summaries, quotation pipeline, and upcoming visits
- **PDF Generation** — Professional quotation and invoice PDFs with company branding
- **Whitelabel** — All company details configured via environment variables, no code changes needed

## Tech Stack

- Python 3.12 (async)
- [python-telegram-bot 21.6](https://python-telegram-bot.org/)
- SQLAlchemy 2.x (async) with SQLite (local) or PostgreSQL (production)
- FastAPI + Uvicorn (health check endpoint)
- WeasyPrint (PDF generation)
- Jinja2 (PDF templates)
- Google Calendar API (optional)

## Quick Start

### Prerequisites

- Python 3.12+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Your Telegram user ID (get it from [@userinfobot](https://t.me/userinfobot))
- WeasyPrint system dependencies:
  - **macOS:** `brew install pango`
  - **Ubuntu/Debian:** `apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev libcairo2`

### Setup

```bash
# Clone the repo
git clone https://github.com/your-username/ArtisanTelegramBot.git
cd ArtisanTelegramBot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values (at minimum: TELEGRAM_BOT_TOKEN and ADMIN_CHAT_ID)
```

### Run Locally

```bash
python -m app.main
```

The bot uses SQLite by default for local development. Send `/start` to your bot on Telegram and enter the password (default: `changeme`).

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and fill in your values:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `ADMIN_CHAT_ID` | Yes | — | Your Telegram user ID |
| `ALLOWED_USER_IDS` | No | — | Comma-separated additional user IDs |
| `BOT_PASSWORD` | No | `changeme` | Password to access the bot |
| `DATABASE_URL` | No | SQLite (local) | PostgreSQL URL for production |
| `COMPANY_NAME` | No | `Blackgrid` | Shown in bot messages and PDFs |
| `COMPANY_PHONE` | No | — | Shown on PDF documents |
| `COMPANY_SSM` | No | — | Business registration number |
| `COMPANY_ADDRESS` | No | — | Shown on PDF documents |
| `AUTHORIZED_BY` | No | `Your Name` | Name on quotation/invoice signatures |
| `BANK_NAME` | No | — | For invoice payment details |
| `BANK_ACCOUNT` | No | — | Bank account number |
| `BANK_HOLDER` | No | — | Account holder name |
| `GOOGLE_CREDENTIALS_JSON` | No | — | Google service account JSON for Calendar API |
| `GOOGLE_CALENDAR_ID` | No | — | Google Calendar ID for site visit sync |
| `PORT` | No | `8000` | Health check server port |

## Deploy to Railway

1. Fork this repo and push to your GitHub
2. Create a new project on [Railway](https://railway.app)
3. Add a **PostgreSQL** plugin to your project
4. Connect your GitHub repo as a service
5. Set environment variables:
   - `TELEGRAM_BOT_TOKEN` — your bot token
   - `ADMIN_CHAT_ID` — your Telegram user ID
   - `DATABASE_URL` — reference the PostgreSQL plugin (`${{Postgres.DATABASE_URL}}`)
   - Any other variables you want to customize
6. Railway auto-detects the Dockerfile and deploys
7. Health check at `/health` confirms the service is running

### Railway Notes

- Use the **public** PostgreSQL URL or the Railway reference variable (`${{Postgres.DATABASE_URL}}`), not the `*.railway.internal` hostname, to avoid DNS resolution issues during startup
- The `railway.toml` in this repo configures the health check and restart policy

## Project Structure

```
app/
├── main.py                    # Entry point: DB init, handler registration, startup
├── config.py                  # Pydantic settings (all env vars)
├── database.py                # SQLAlchemy async engine + session factory
├── bot/
│   ├── filters.py             # Admin filter — restricts bot to allowed user IDs
│   ├── keyboards.py           # All inline keyboard definitions
│   ├── states.py              # Conversation states per module
│   └── handlers/
│       ├── start.py           # /start, password auth, main menu
│       ├── customer.py        # Customer CRUD
│       ├── quotation.py       # Quotation builder with line items
│       ├── invoice.py         # Invoice creation and payment recording
│       ├── calendar.py        # Site visit booking with Google Calendar sync
│       ├── report.py          # Business dashboard
│       └── settings.py        # Pattern management
├── models/                    # SQLAlchemy ORM models
│   ├── base.py                # Base class (UUID id + created_at)
│   ├── authenticated_user.py  # Persistent auth sessions
│   ├── customer.py
│   ├── quotation.py
│   ├── invoice.py
│   ├── line_item.py
│   ├── pattern.py             # Reusable service templates
│   ├── site_visit.py
│   └── slot.py
├── services/                  # Business logic layer
│   ├── customer_service.py
│   ├── quotation_service.py
│   ├── invoice_service.py
│   ├── slot_service.py
│   ├── calendar_service.py    # Google Calendar API integration
│   ├── report_service.py
│   └── pdf_service.py         # Jinja2 + WeasyPrint PDF generation
├── pdf/
│   ├── templates/             # quotation.html, invoice.html
│   └── assets/                # stamp.png (company stamp image)
└── api/
    └── routes.py              # GET /health endpoint
```

## Customization

### Rebranding

Change environment variables — no code edits needed:
- `COMPANY_NAME`, `COMPANY_PHONE`, `COMPANY_SSM`, `COMPANY_ADDRESS` for bot messages and PDFs
- `BANK_NAME`, `BANK_ACCOUNT`, `BANK_HOLDER` for invoice payment details
- `AUTHORIZED_BY` for the signature name on documents
- Replace `app/pdf/assets/stamp.png` with your company stamp

### PDF Templates

Edit the Jinja2 HTML templates in `app/pdf/templates/` to customize the look of quotations and invoices.

### Default Patterns

The bot seeds default service patterns on first run (see `seed_patterns()` in `app/main.py`). Users can add, edit, and manage patterns through the Settings menu in the bot.

## Adding Features

1. Create a handler module at `app/bot/handlers/yourfeature.py`
2. Add conversation states to `app/bot/states.py` if needed
3. Add keyboards to `app/bot/keyboards.py` if needed
4. Export a `get_yourfeature_handlers()` function
5. Register it in `app/main.py` → `register_handlers()`

See the [CLAUDE.md](CLAUDE.md) file for detailed development patterns and conventions.

## License

[MIT](LICENSE)
