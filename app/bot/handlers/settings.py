from decimal import Decimal, InvalidOperation

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot.filters import admin_filter
from app.bot.keyboards import main_menu_keyboard
from app.bot.states import SettingsStates
from app.database import async_session
from app.services.quotation_service import get_active_patterns

from sqlalchemy import select
from app.models.pattern import Pattern


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 View Patterns", callback_data="set_patterns")],
            [InlineKeyboardButton("➕ Add Pattern", callback_data="set_add_pattern")],
            [InlineKeyboardButton("✏️ Edit Rate", callback_data="set_edit_rate")],
            [InlineKeyboardButton("« Back to Menu", callback_data="back_main")],
        ]
    )


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⚙️ *Settings*\n━━━━━━━━━━━━━━━━━━",
        reply_markup=settings_menu_keyboard(),
        parse_mode="Markdown",
    )


async def view_patterns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        patterns = await get_active_patterns(session)

    if not patterns:
        await query.edit_message_text(
            "No patterns configured.", reply_markup=settings_menu_keyboard()
        )
        return

    lines = ["📋 *Concrete Patterns*\n━━━━━━━━━━━━━━━━━━"]
    for p in patterns:
        status = "✅" if p.is_active else "❌"
        lines.append(f"{status} *{p.name}* — RM{p.rate_per_sqft}/sqft")
        if p.description:
            lines.append(f"   _{p.description}_")

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=settings_menu_keyboard(),
        parse_mode="Markdown",
    )


# ─── Add Pattern ───


async def add_pattern_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["new_pattern"] = {}
    await query.edit_message_text("Enter pattern name (e.g., 'European Fan'):")
    return SettingsStates.ADD_PATTERN_NAME


async def add_pattern_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_pattern"]["name"] = update.message.text.strip()
    await update.message.reply_text("Enter rate per sqft (e.g., 8.50):")
    return SettingsStates.ADD_PATTERN_RATE


async def add_pattern_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        rate = Decimal(update.message.text.strip())
        if rate <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Enter a valid positive rate:")
        return SettingsStates.ADD_PATTERN_RATE

    data = context.user_data.pop("new_pattern")

    async with async_session() as session:
        pattern = Pattern(name=data["name"], rate_per_sqft=rate, is_active=True)
        session.add(pattern)
        await session.commit()

    await update.message.reply_text(
        f"✅ Pattern *{data['name']}* added at RM{rate}/sqft",
        reply_markup=settings_menu_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ─── Edit Pattern Rate ───


async def edit_rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        patterns = await get_active_patterns(session)

    buttons = []
    for p in patterns:
        buttons.append(
            [InlineKeyboardButton(
                f"{p.name} — RM{p.rate_per_sqft}/sqft",
                callback_data=f"edit_pat_{p.id}",
            )]
        )
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="set_cancel")])

    await query.edit_message_text(
        "Select pattern to edit:", reply_markup=InlineKeyboardMarkup(buttons)
    )
    return SettingsStates.EDIT_PATTERN_SELECT


async def edit_pattern_select(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    pattern_id = query.data.replace("edit_pat_", "")
    context.user_data["edit_pattern_id"] = pattern_id
    await query.edit_message_text("Enter new rate per sqft:")
    return SettingsStates.EDIT_PATTERN_RATE


async def edit_pattern_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        rate = Decimal(update.message.text.strip())
        if rate <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Enter a valid positive rate:")
        return SettingsStates.EDIT_PATTERN_RATE

    pattern_id = context.user_data.pop("edit_pattern_id")

    async with async_session() as session:
        pattern = await session.get(Pattern, pattern_id)
        if pattern:
            old_rate = pattern.rate_per_sqft
            pattern.rate_per_sqft = rate
            await session.commit()
            await update.message.reply_text(
                f"✅ *{pattern.name}* rate updated: RM{old_rate} → RM{rate}/sqft",
                reply_markup=settings_menu_keyboard(),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "Pattern not found.", reply_markup=settings_menu_keyboard()
            )

    return ConversationHandler.END


# ─── Cancel ───


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("new_pattern", None)
    context.user_data.pop("edit_pattern_id", None)
    if update.message:
        await update.message.reply_text("Cancelled.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Cancelled.", reply_markup=settings_menu_keyboard())
    return ConversationHandler.END


# ─── Register handlers ───


def get_settings_handlers() -> list:
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_pattern_start, pattern="^set_add_pattern$")],
        states={
            SettingsStates.ADD_PATTERN_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, add_pattern_name)
            ],
            SettingsStates.ADD_PATTERN_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, add_pattern_rate)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=300,
    )

    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_rate_start, pattern="^set_edit_rate$")],
        states={
            SettingsStates.EDIT_PATTERN_SELECT: [
                CallbackQueryHandler(edit_pattern_select, pattern=r"^edit_pat_"),
                CallbackQueryHandler(cancel_callback, pattern="^set_cancel$"),
            ],
            SettingsStates.EDIT_PATTERN_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, edit_pattern_rate)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=300,
    )

    return [
        add_conv,
        edit_conv,
        CallbackQueryHandler(settings_menu, pattern="^menu_settings$"),
        CallbackQueryHandler(view_patterns, pattern="^set_patterns$"),
    ]
