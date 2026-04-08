import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot.keyboards import (
    calendar_menu_keyboard,
    customer_menu_keyboard,
    invoice_menu_keyboard,
    main_menu_keyboard,
    quotation_menu_keyboard,
)
from app.config import settings
from app.database import async_session
from app.models.authenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    f"🏗 *{settings.COMPANY_NAME} Bot*\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Business Management\n\n"
    "Select an option below:"
)

# In-memory cache to avoid DB lookups on every interaction
_auth_cache: set[int] = set()


async def load_authenticated_users():
    """Load authenticated users from DB into cache on startup."""
    async with async_session() as session:
        result = await session.execute(select(AuthenticatedUser.telegram_user_id))
        for (uid,) in result.all():
            _auth_cache.add(uid)
    logger.info("Loaded %d authenticated users from DB", len(_auth_cache))


async def _persist_auth(user_id: int):
    """Save authenticated user to DB and cache."""
    _auth_cache.add(user_id)
    async with async_session() as session:
        existing = await session.execute(
            select(AuthenticatedUser).where(
                AuthenticatedUser.telegram_user_id == user_id
            )
        )
        if not existing.scalar_one_or_none():
            session.add(AuthenticatedUser(telegram_user_id=user_id))
            await session.commit()


def is_authenticated(user_id: int) -> bool:
    return user_id in _auth_cache


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    if is_authenticated(user_id):
        await update.message.reply_text(
            WELCOME_TEXT,
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"🔐 *{settings.COMPANY_NAME} Bot*\n━━━━━━━━━━━━━━━━━━\n\nEnter password to continue:",
        parse_mode="Markdown",
    )
    return 0  # PASSWORD state


async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    password = update.message.text.strip()

    # Delete the password message for security
    try:
        await update.message.delete()
    except Exception:
        pass

    if password == settings.BOT_PASSWORD:
        await _persist_auth(user_id)
        await update.message.reply_text(
            f"✅ Access granted!\n\n{WELCOME_TEXT}",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ Wrong password. Try again or send /start:",
        )
        return ConversationHandler.END


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not is_authenticated(query.from_user.id):
        await query.edit_message_text("🔐 Please send /start and enter password.")
        return

    await query.edit_message_text(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )


async def menu_customers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "👥 *Customer Management*\n━━━━━━━━━━━━━━━━━━",
        reply_markup=customer_menu_keyboard(),
        parse_mode="Markdown",
    )


async def menu_quotations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📝 *Quotations*\n━━━━━━━━━━━━━━━━━━",
        reply_markup=quotation_menu_keyboard(),
        parse_mode="Markdown",
    )


async def menu_invoices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💰 *Invoices*\n━━━━━━━━━━━━━━━━━━",
        reply_markup=invoice_menu_keyboard(),
        parse_mode="Markdown",
    )


async def menu_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📅 *Calendar & Scheduling*\n━━━━━━━━━━━━━━━━━━",
        reply_markup=calendar_menu_keyboard(),
        parse_mode="Markdown",
    )


def get_start_handlers() -> list:
    login_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
        },
        fallbacks=[CommandHandler("start", start_command)],
    )

    return [
        login_conv,
        CallbackQueryHandler(back_to_main, pattern="^back_main$"),
        CallbackQueryHandler(menu_customers, pattern="^menu_customers$"),
        CallbackQueryHandler(menu_quotations, pattern="^menu_quotations$"),
        CallbackQueryHandler(menu_invoices, pattern="^menu_invoices$"),
        CallbackQueryHandler(menu_calendar, pattern="^menu_calendar$"),
    ]
