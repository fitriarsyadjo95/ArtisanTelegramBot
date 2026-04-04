from datetime import date, timedelta

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
from app.bot.keyboards import calendar_menu_keyboard, main_menu_keyboard
from app.bot.states import CalendarStates
from app.database import async_session
from app.services import calendar_service, customer_service, slot_service


# ─── View Schedule ───


async def view_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    today = date.today()
    buttons = []
    for i in range(7):
        d = today + timedelta(days=i)
        day_label = calendar_service.format_date_malay(d)
        if i == 0:
            day_label += " (Hari Ini)"
        buttons.append(
            [InlineKeyboardButton(day_label, callback_data=f"cal_date_{d.isoformat()}")]
        )
    buttons.append([InlineKeyboardButton("« Back", callback_data="menu_calendar")])

    await query.edit_message_text(
        "📅 *Schedule — Select a Date*\n━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def view_date_visits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    date_str = query.data.replace("cal_date_", "")
    target_date = date.fromisoformat(date_str)

    async with async_session() as session:
        visits = await slot_service.get_visits_for_date(session, target_date)

    date_label = calendar_service.format_date_malay(target_date)
    text = f"📅 *{date_label}*\n━━━━━━━━━━━━━━━━━━\n\n"

    if visits:
        for v in visits:
            text += (
                f"🔴 {v.visit_time} — {v.customer.name}\n"
                f"   _{v.details or 'Site Visit'}_\n\n"
            )
    else:
        text += "🟢 No visits scheduled\n"

    buttons = [
        [InlineKeyboardButton("➕ Book Site Visit", callback_data=f"cal_book_{date_str}")],
        [InlineKeyboardButton("« Back to Dates", callback_data="cal_view")],
    ]

    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


# ─── Book Site Visit Flow ───


async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data["book"] = {}

    # If coming from a specific date
    if query.data.startswith("cal_book_") and query.data != "cal_book":
        date_str = query.data.replace("cal_book_", "")
        context.user_data["book"]["date"] = date_str

    # Show customer selection
    async with async_session() as session:
        customers = await customer_service.list_customers(session, limit=20)

    if not customers:
        await query.edit_message_text(
            "No customers yet. Create a customer first.",
            reply_markup=calendar_menu_keyboard(),
        )
        return ConversationHandler.END

    buttons = []
    for c in customers:
        buttons.append(
            [InlineKeyboardButton(
                f"{c.name} — {c.phone}",
                callback_data=f"book_cust_{c.id}",
            )]
        )
    buttons.append(
        [InlineKeyboardButton("🔍 Search", callback_data="book_cust_search")]
    )
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cal_cancel")])

    await query.edit_message_text(
        "📅 *Book Site Visit*\n━━━━━━━━━━━━━━━━━━\n\nSelect client:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )
    return CalendarStates.SELECT_CUSTOMER


async def select_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "book_cust_search":
        await query.edit_message_text("🔍 Enter client name or phone:")
        return CalendarStates.SEARCH_CUSTOMER

    customer_id = query.data.replace("book_cust_", "")
    context.user_data["book"]["customer_id"] = customer_id

    async with async_session() as session:
        customer = await customer_service.get_customer(session, customer_id)

    context.user_data["book"]["customer_name"] = customer.name
    context.user_data["book"]["customer_phone"] = customer.phone
    context.user_data["book"]["customer_address"] = customer.address or ""

    # If date already selected, skip to time
    if "date" in context.user_data["book"]:
        target_date = date.fromisoformat(context.user_data["book"]["date"])
        await query.edit_message_text(
            f"Client: *{customer.name}*\n"
            f"Date: *{calendar_service.format_date_malay(target_date)}*\n\n"
            f"⏰ Enter visit time (e.g., 11AM, 2PM, 10:30AM):",
            parse_mode="Markdown",
        )
        return CalendarStates.ENTER_TIME

    # Show date picker
    return await _show_date_picker(query, context)


async def search_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query_text = update.message.text.strip()

    async with async_session() as session:
        customers = await customer_service.search_customers(session, query_text)

    if not customers:
        await update.message.reply_text(f"No results for '{query_text}'. Try again or /cancel:")
        return CalendarStates.SEARCH_CUSTOMER

    buttons = []
    for c in customers:
        buttons.append(
            [InlineKeyboardButton(f"{c.name} — {c.phone}", callback_data=f"book_cust_{c.id}")]
        )
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cal_cancel")])

    await update.message.reply_text(
        f"Found {len(customers)} result(s):",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return CalendarStates.SELECT_CUSTOMER


async def _show_date_picker(query, context) -> int:
    today = date.today()
    buttons = []
    for i in range(14):
        d = today + timedelta(days=i)
        day_label = calendar_service.format_date_malay(d)
        if i == 0:
            day_label += " (Hari Ini)"
        buttons.append(
            [InlineKeyboardButton(day_label, callback_data=f"book_date_{d.isoformat()}")]
        )
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cal_cancel")])

    name = context.user_data["book"]["customer_name"]
    await query.edit_message_text(
        f"Client: *{name}*\n\n📅 Select date:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )
    return CalendarStates.SELECT_DATE


async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_str = query.data.replace("book_date_", "")
    context.user_data["book"]["date"] = date_str

    target_date = date.fromisoformat(date_str)
    name = context.user_data["book"]["customer_name"]

    await query.edit_message_text(
        f"Client: *{name}*\n"
        f"Date: *{calendar_service.format_date_malay(target_date)}*\n\n"
        f"⏰ Enter visit time (e.g., 11AM, 2PM, 10:30AM):",
        parse_mode="Markdown",
    )
    return CalendarStates.ENTER_TIME


async def enter_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_input = update.message.text.strip()
    context.user_data["book"]["time"] = time_input

    name = context.user_data["book"]["customer_name"]
    target_date = date.fromisoformat(context.user_data["book"]["date"])

    await update.message.reply_text(
        f"Client: *{name}*\n"
        f"Date: *{calendar_service.format_date_malay(target_date)}*\n"
        f"Time: *{time_input.upper()}*\n\n"
        f"📋 Enter visit details (e.g., LUMSUM 600SQFT, SITE MEASUREMENT):",
        parse_mode="Markdown",
    )
    return CalendarStates.ENTER_DETAILS


async def enter_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    details = update.message.text.strip()
    context.user_data["book"]["details"] = details

    book = context.user_data["book"]
    target_date = date.fromisoformat(book["date"])

    # Generate preview of the broadcast message
    preview = calendar_service.generate_site_visit_message(
        customer_name=book["customer_name"],
        customer_phone=book["customer_phone"],
        customer_address=book["customer_address"],
        visit_date=target_date,
        visit_time=book["time"],
        details=details,
    )

    text = (
        f"📅 *Booking Preview*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{preview}\n\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Confirm & Book", callback_data="book_confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cal_cancel")],
        ]
    )

    await update.message.reply_text(text, reply_markup=buttons, parse_mode="Markdown")
    return CalendarStates.CONFIRM_BOOKING


async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    book = context.user_data.pop("book")
    target_date = date.fromisoformat(book["date"])

    await query.edit_message_text("⏳ Booking and syncing calendar...")

    # Create Google Calendar event
    google_event_id = await calendar_service.create_event(
        event_date=target_date,
        visit_time=book["time"],
        customer_name=book["customer_name"],
        details=book["details"],
        address=book.get("customer_address"),
        customer_phone=book.get("customer_phone"),
    )

    # Save to database
    async with async_session() as session:
        visit = await slot_service.create_visit(
            session,
            customer_id=book["customer_id"],
            visit_date=target_date,
            visit_time=book["time"],
            details=book["details"],
            google_event_id=google_event_id,
        )

    # Generate the broadcast message
    broadcast_msg = calendar_service.generate_site_visit_message(
        customer_name=book["customer_name"],
        customer_phone=book["customer_phone"],
        customer_address=book["customer_address"],
        visit_date=target_date,
        visit_time=book["time"],
        details=book["details"],
    )

    gcal_msg = "\n\n📆 Google Calendar event created!" if google_event_id else ""

    # Send confirmation with the copyable message
    await query.edit_message_text(
        f"✅ *Site visit booked!*{gcal_msg}\n\n"
        f"━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
    )

    # Send the broadcast message as a separate message (easy to forward/copy)
    await query.message.reply_text(
        broadcast_msg,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("« Back to Menu", callback_data="back_main")],
        ]),
    )

    return ConversationHandler.END


# ─── Cancel ───


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("book", None)
    if update.message:
        await update.message.reply_text("Cancelled.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("book", None)
    await query.edit_message_text("Cancelled.", reply_markup=calendar_menu_keyboard())
    return ConversationHandler.END


# ─── Register handlers ───


def get_calendar_handlers() -> list:
    book_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(book_start, pattern=r"^cal_book"),
        ],
        states={
            CalendarStates.SELECT_CUSTOMER: [
                CallbackQueryHandler(select_customer, pattern=r"^book_cust_"),
                CallbackQueryHandler(cancel_callback, pattern="^cal_cancel$"),
            ],
            CalendarStates.SEARCH_CUSTOMER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, search_customer),
            ],
            CalendarStates.SELECT_DATE: [
                CallbackQueryHandler(select_date, pattern=r"^book_date_"),
                CallbackQueryHandler(cancel_callback, pattern="^cal_cancel$"),
            ],
            CalendarStates.ENTER_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, enter_time),
            ],
            CalendarStates.ENTER_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, enter_details),
            ],
            CalendarStates.CONFIRM_BOOKING: [
                CallbackQueryHandler(confirm_booking, pattern="^book_confirm$"),
                CallbackQueryHandler(cancel_callback, pattern="^cal_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_callback, pattern="^cal_cancel$"),
        ],
        conversation_timeout=300,
    )

    return [
        book_conv,
        CallbackQueryHandler(view_schedule, pattern="^cal_view$"),
        CallbackQueryHandler(view_date_visits, pattern=r"^cal_date_"),
    ]
