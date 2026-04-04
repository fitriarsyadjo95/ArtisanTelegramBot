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

WELCOME_TEXT = (
    f"🏗 *{settings.COMPANY_NAME} Bot*\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "Business Management\n\n"
    "Select an option below:"
)

# Track authenticated users in memory (resets on bot restart)
_authenticated_users: set[int] = set()


def is_authenticated(user_id: int) -> bool:
    return user_id in _authenticated_users


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
        _authenticated_users.add(user_id)
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
