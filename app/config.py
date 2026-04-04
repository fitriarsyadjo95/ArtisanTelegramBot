from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    TELEGRAM_BOT_TOKEN: str
    ADMIN_CHAT_ID: int
    ALLOWED_USER_IDS: str = ""  # Comma-separated additional user IDs

    # Database (defaults to SQLite for local dev)
    DATABASE_URL: str = "sqlite+aiosqlite:///blackgrid.db"

    # Google Calendar
    GOOGLE_CREDENTIALS_JSON: str = ""
    GOOGLE_CALENDAR_ID: str = ""

    # Company Details
    COMPANY_NAME: str = "Blackgrid"
    COMPANY_PHONE: str = ""
    COMPANY_SSM: str = ""
    COMPANY_ADDRESS: str = ""

    # Authorized Person (for quotation/invoice signature)
    AUTHORIZED_BY: str = "Your Name"

    # Bank Details
    BANK_NAME: str = ""
    BANK_ACCOUNT: str = ""
    BANK_HOLDER: str = ""

    # Bot Password
    BOT_PASSWORD: str = "changeme"

    # Server
    PORT: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
