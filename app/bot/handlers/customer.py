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
from app.bot.keyboards import customer_menu_keyboard, main_menu_keyboard
from app.bot.states import CustomerStates
from app.database import async_session
from app.services import customer_service


# ─── List all customers ───


async def list_customers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        customers = await customer_service.list_customers(session, limit=20)

    if not customers:
        await query.edit_message_text(
            "No customers yet.\n\nUse *New Customer* to add one.",
            reply_markup=customer_menu_keyboard(),
            parse_mode="Markdown",
        )
        return

    lines = ["👥 *All Customers*\n━━━━━━━━━━━━━━━━━━"]
    buttons = []
    for c in customers:
        lines.append(f"• {c.name} — {c.phone}")
        buttons.append(
            [InlineKeyboardButton(f"{c.name}", callback_data=f"cust_view_{c.id}")]
        )
    buttons.append([InlineKeyboardButton("« Back", callback_data="menu_customers")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


# ─── View customer detail ───


async def view_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    customer_id = query.data.replace("cust_view_", "")

    async with async_session() as session:
        customer = await customer_service.get_customer(session, customer_id)

    if not customer:
        await query.edit_message_text("Customer not found.", reply_markup=customer_menu_keyboard())
        return

    text = (
        f"👤 *{customer.name}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📱 Phone: {customer.phone}\n"
        f"📧 Email: {customer.email or 'N/A'}\n"
        f"📍 Address: {customer.address or 'N/A'}\n"
        f"📝 Notes: {customer.notes or 'N/A'}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Quotations: {len(customer.quotations)}\n"
        f"Invoices: {len(customer.invoices)}\n"
        f"Site Visits: {len(customer.site_visits)}"
    )

    buttons = [
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f"cust_edit_{customer.id}"),
            InlineKeyboardButton("📝 Quotations", callback_data=f"cust_quots_{customer.id}"),
        ],
        [InlineKeyboardButton("« Back", callback_data="cust_list")],
    ]

    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


# ─── Search customer conversation ───


async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔍 Enter customer name or phone number:")
    return CustomerStates.SEARCH_INPUT


async def search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query_text = update.message.text.strip()

    async with async_session() as session:
        customers = await customer_service.search_customers(session, query_text)

    if not customers:
        await update.message.reply_text(
            f"No customers found for '{query_text}'.\nTry again or /cancel.",
        )
        return CustomerStates.SEARCH_INPUT

    buttons = []
    for c in customers:
        buttons.append(
            [InlineKeyboardButton(f"{c.name} — {c.phone}", callback_data=f"cust_view_{c.id}")]
        )
    buttons.append([InlineKeyboardButton("« Back", callback_data="menu_customers")])

    await update.message.reply_text(
        f"Found {len(customers)} result(s):",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return ConversationHandler.END


# ─── Create customer conversation ───


async def create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("➕ *New Customer*\n\nEnter customer name:", parse_mode="Markdown")
    context.user_data["new_customer"] = {}
    return CustomerStates.CREATE_NAME


async def create_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_customer"]["name"] = update.message.text.strip()
    await update.message.reply_text("📱 Enter phone number:")
    return CustomerStates.CREATE_PHONE


async def create_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_customer"]["phone"] = update.message.text.strip()
    await update.message.reply_text(
        "📍 Enter address (or type 'skip'):"
    )
    return CustomerStates.CREATE_ADDRESS


async def create_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.lower() != "skip":
        context.user_data["new_customer"]["address"] = text
    await update.message.reply_text("📧 Enter email (or type 'skip'):")
    return CustomerStates.CREATE_EMAIL


async def create_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.lower() != "skip":
        context.user_data["new_customer"]["email"] = text

    data = context.user_data["new_customer"]
    text = (
        f"✅ *Confirm New Customer*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Name: {data['name']}\n"
        f"Phone: {data['phone']}\n"
        f"Address: {data.get('address', 'N/A')}\n"
        f"Email: {data.get('email', 'N/A')}"
    )

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Save", callback_data="cust_save"),
                InlineKeyboardButton("❌ Cancel", callback_data="cust_cancel_create"),
            ]
        ]
    )

    await update.message.reply_text(text, reply_markup=buttons, parse_mode="Markdown")
    return CustomerStates.CONFIRM_CREATE


async def create_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cust_cancel_create":
        await query.edit_message_text(
            "Cancelled.",
            reply_markup=customer_menu_keyboard(),
        )
        context.user_data.pop("new_customer", None)
        return ConversationHandler.END

    data = context.user_data.pop("new_customer", {})

    async with async_session() as session:
        customer = await customer_service.create_customer(
            session,
            name=data["name"],
            phone=data["phone"],
            address=data.get("address"),
            email=data.get("email"),
        )

    await query.edit_message_text(
        f"✅ Customer *{customer.name}* created!",
        reply_markup=customer_menu_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ─── Edit customer conversation ───


async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    customer_id = query.data.replace("cust_edit_", "")
    context.user_data["edit_customer_id"] = customer_id

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Name", callback_data="edit_field_name"),
                InlineKeyboardButton("Phone", callback_data="edit_field_phone"),
            ],
            [
                InlineKeyboardButton("Address", callback_data="edit_field_address"),
                InlineKeyboardButton("Email", callback_data="edit_field_email"),
            ],
            [InlineKeyboardButton("« Back", callback_data="menu_customers")],
        ]
    )

    await query.edit_message_text("Which field to edit?", reply_markup=buttons)
    return CustomerStates.EDIT_FIELD


async def edit_field_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    field = query.data.replace("edit_field_", "")
    context.user_data["edit_field"] = field
    await query.edit_message_text(f"Enter new {field}:")
    return CustomerStates.EDIT_VALUE


async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.pop("edit_field")
    customer_id = context.user_data.pop("edit_customer_id")
    value = update.message.text.strip()

    async with async_session() as session:
        customer = await customer_service.update_customer(
            session, customer_id, **{field: value}
        )

    if customer:
        await update.message.reply_text(
            f"✅ Updated {field} to: {value}",
            reply_markup=customer_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            "Customer not found.",
            reply_markup=customer_menu_keyboard(),
        )
    return ConversationHandler.END


# ─── Cancel fallback ───


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.message:
        await update.message.reply_text(
            "Cancelled.", reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END


# ─── Register handlers ───


def get_customer_handlers() -> list:
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_start, pattern="^cust_search$")],
        states={
            CustomerStates.SEARCH_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, search_input)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=300,
    )

    create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_start, pattern="^cust_new$")],
        states={
            CustomerStates.CREATE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, create_name)
            ],
            CustomerStates.CREATE_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, create_phone)
            ],
            CustomerStates.CREATE_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, create_address)
            ],
            CustomerStates.CREATE_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, create_email)
            ],
            CustomerStates.CONFIRM_CREATE: [
                CallbackQueryHandler(create_confirm, pattern="^cust_(save|cancel_create)$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=300,
    )

    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_start, pattern=r"^cust_edit_")],
        states={
            CustomerStates.EDIT_FIELD: [
                CallbackQueryHandler(edit_field_select, pattern=r"^edit_field_")
            ],
            CustomerStates.EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, edit_value)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=300,
    )

    return [
        search_conv,
        create_conv,
        edit_conv,
        CallbackQueryHandler(list_customers, pattern="^cust_list$"),
        CallbackQueryHandler(view_customer, pattern=r"^cust_view_"),
    ]
