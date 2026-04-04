import asyncio
import logging

import uvicorn
from telegram.ext import ApplicationBuilder

from app.api.routes import app as fastapi_app
from app.bot.handlers.start import get_start_handlers
from app.bot.handlers.customer import get_customer_handlers
from app.bot.handlers.quotation import get_quotation_handlers
from app.bot.handlers.invoice import get_invoice_handlers
from app.bot.handlers.calendar import get_calendar_handlers
from app.bot.handlers.report import get_report_handlers
from app.bot.handlers.settings import get_settings_handlers
from app.config import settings
from app.database import engine
from app.models import Base

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def register_handlers(application):
    """Register all bot handlers."""
    for handler in get_start_handlers():
        application.add_handler(handler)

    for handler in get_customer_handlers():
        application.add_handler(handler)

    for handler in get_quotation_handlers():
        application.add_handler(handler)

    for handler in get_invoice_handlers():
        application.add_handler(handler)

    for handler in get_calendar_handlers():
        application.add_handler(handler)

    for handler in get_report_handlers():
        application.add_handler(handler)

    for handler in get_settings_handlers():
        application.add_handler(handler)


async def init_db():
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")


async def seed_patterns():
    """Seed default concrete patterns if none exist."""
    from sqlalchemy import select
    from app.database import async_session
    from app.models.pattern import Pattern

    async with async_session() as session:
        result = await session.execute(select(Pattern).limit(1))
        if result.scalars().first():
            return

        default_patterns = [
            Pattern(
                name="Imprint Stamping (Klang Valley)",
                rate_per_sqft=12.50,
                pricing_type="per_sqft",
                description=(
                    "- To supply material & labour to install formwork.\n"
                    "- To supply material & labour to lay BRC A10 (cq) 1 layer.\n"
                    "- To supply material & labour to lay 50 - 100mm thickness Ready Mixed Concrete grade 25N.\n"
                    "- To supply material & labour to install Imprint stamping works including "
                    "Dryshake Color Hardener at the rate 3-4kg/m2, Color Releaser at 0.1-0.13kg/m2 "
                    "and emboss to require pattern.\n"
                    "- To supply material & labour to wash and apply sealer (2 layer)"
                ),
            ),
            Pattern(
                name="Imprint Stamping (Outside KV)",
                rate_per_sqft=13.50,
                pricing_type="per_sqft",
                description=(
                    "- To supply material & labour to install formwork.\n"
                    "- To supply material & labour to lay BRC A10 (cq) 1 layer.\n"
                    "- To supply material & labour to lay 50 - 100mm thickness Ready Mixed Concrete grade 25N.\n"
                    "- To supply material & labour to install Imprint stamping works including "
                    "Dryshake Color Hardener at the rate 3-4kg/m2, Color Releaser at 0.1-0.13kg/m2 "
                    "and emboss to require pattern.\n"
                    "- To supply material & labour to wash and apply sealer (2 layer)"
                ),
            ),
            Pattern(
                name="Hacking / Soilwork",
                rate_per_sqft=0,
                pricing_type="lumpsum",
                description=(
                    "- To supply equipment & labour for site preperation, hacking, "
                    "soil leveling & ground compact works including usage of waste disposal "
                    "bin & backhoe machine (if any)"
                ),
            ),
            Pattern(
                name="Crusher Run & Compact",
                rate_per_sqft=0,
                pricing_type="lumpsum",
                description=(
                    "-To supply & lay crusher run layer including compact works "
                    "at all selected area. (To be confirm before work start)"
                ),
            ),
        ]
        session.add_all(default_patterns)
        await session.commit()
        logger.info("Seeded %d default patterns", len(default_patterns))


async def error_handler(update, context):
    """Global error handler for the bot."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    if update and update.effective_message:
        error_msg = f"{type(context.error).__name__}: {context.error}"
        await update.effective_message.reply_text(
            f"⚠️ Error: {error_msg}"
        )


async def main():
    await init_db()
    await seed_patterns()

    bot_app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    register_handlers(bot_app)
    bot_app.add_error_handler(error_handler)

    async with bot_app:
        await bot_app.start()
        await bot_app.updater.start_polling()
        logger.info("Bot started polling")

        config = uvicorn.Config(
            fastapi_app, host="0.0.0.0", port=settings.PORT, log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

        await bot_app.updater.stop()
        await bot_app.stop()


if __name__ == "__main__":
    asyncio.run(main())
