import io
import urllib.parse
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
from app.bot.keyboards import main_menu_keyboard, quotation_menu_keyboard
from app.bot.states import QuotationStates
from app.config import settings
from app.database import async_session
from app.services import customer_service, quotation_service
from app.services.pdf_service import generate_quotation_pdf


# ─── Helpers ───


def _format_item_line(item: dict) -> str:
    """Format a single line item for display."""
    if item["pricing_type"] == "custom":
        unit = item.get("unit", "")
        qty = item.get("quantity", "0")
        if unit == "LS":
            return f"{item['pattern_name']} — {qty} {unit} = RM{Decimal(item['amount']):,.2f}"
        return (
            f"{item['pattern_name']} — "
            f"{qty} {unit} × RM{Decimal(item.get('unit_price', '0')):,.2f} = "
            f"RM{Decimal(item['amount']):,.2f}"
        )
    elif item["pricing_type"] == "lumpsum":
        return f"{item['pattern_name']} — RM{Decimal(item['amount']):,.2f} (LS)"
    else:
        return (
            f"{item['pattern_name']} — "
            f"{item['area_sqft']} sqft × RM{Decimal(item['rate_per_sqft']):,.2f} = "
            f"RM{Decimal(item['amount']):,.2f}"
        )


def _items_summary(items: list[dict]) -> str:
    """Build a text summary of all current items."""
    subtotal = sum(Decimal(i["amount"]) for i in items)
    lines = [f"Items so far ({len(items)}):"]
    for i, item in enumerate(items, 1):
        lines.append(f"  {i}. {_format_item_line(item)}")
    lines.append(f"\n*Subtotal: RM{subtotal:,.2f}*")
    return "\n".join(lines)


# ─── New Quotation Flow ───


async def new_quotation_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data["quot"] = {"items": []}

    async with async_session() as session:
        customers = await customer_service.list_customers(session, limit=20)

    if not customers:
        await query.edit_message_text(
            "No customers yet. Please create a customer first.",
            reply_markup=quotation_menu_keyboard(),
        )
        return ConversationHandler.END

    buttons = []
    for c in customers:
        buttons.append(
            [InlineKeyboardButton(f"{c.name} — {c.phone}", callback_data=f"qcust_{c.id}")]
        )
    buttons.append(
        [InlineKeyboardButton("🔍 Search", callback_data="qcust_search")]
    )
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="quot_cancel")])

    await query.edit_message_text(
        "📝 *New Quotation*\n━━━━━━━━━━━━━━━━━━\n\nSelect a customer:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )
    return QuotationStates.SELECT_CUSTOMER


async def select_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "qcust_search":
        await query.edit_message_text("🔍 Enter customer name or phone:")
        return QuotationStates.SEARCH_CUSTOMER

    customer_id = query.data.replace("qcust_", "")
    context.user_data["quot"]["customer_id"] = customer_id

    async with async_session() as session:
        customer = await customer_service.get_customer(session, customer_id)

    context.user_data["quot"]["customer_name"] = customer.name

    await query.edit_message_text(
        f"Customer: *{customer.name}*\n\n📍 Enter job location (e.g., KAJANG):",
        parse_mode="Markdown",
    )
    return QuotationStates.ENTER_JOB_LOCATION


async def enter_job_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["quot"]["job_location"] = update.message.text.strip().upper()
    return await _show_pattern_selection(update.message, context)


async def search_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query_text = update.message.text.strip()

    async with async_session() as session:
        customers = await customer_service.search_customers(session, query_text)

    if not customers:
        await update.message.reply_text(f"No results for '{query_text}'. Try again or /cancel:")
        return QuotationStates.SEARCH_CUSTOMER

    buttons = []
    for c in customers:
        buttons.append(
            [InlineKeyboardButton(f"{c.name} — {c.phone}", callback_data=f"qcust_{c.id}")]
        )
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="quot_cancel")])

    await update.message.reply_text(
        f"Found {len(customers)} result(s):",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return QuotationStates.SELECT_CUSTOMER


async def _show_pattern_selection(query_or_message, context):
    """Show service item selection keyboard."""
    async with async_session() as session:
        patterns = await quotation_service.get_active_patterns(session)

    buttons = []
    for p in patterns:
        if p.pricing_type == "lumpsum":
            label = f"{p.name} (lumpsum)"
        elif p.rate_per_sqft > 0:
            label = f"{p.name} — RM{p.rate_per_sqft}/sqft"
        else:
            label = f"{p.name} (rate varies)"
        buttons.append(
            [InlineKeyboardButton(
                label,
                callback_data=f"qpat_{p.id}",
            )]
        )
    buttons.append([InlineKeyboardButton("✏️ Custom Item", callback_data="qpat_custom")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="quot_cancel")])

    items = context.user_data["quot"]["items"]
    quot = context.user_data["quot"]
    if items:
        text = _items_summary(items) + "\n\nSelect next item:"
    else:
        text = (
            f"Customer: *{quot['customer_name']}*\n"
            f"Job: *{quot.get('job_location', '')}*\n\n"
            f"Select a service item:"
        )

    if hasattr(query_or_message, "edit_message_text"):
        await query_or_message.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
        )
    else:
        await query_or_message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
        )

    return QuotationStates.SELECT_PATTERN


async def select_pattern(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    pattern_id = query.data.replace("qpat_", "")

    # ─── Custom Item Flow ───
    if pattern_id == "custom":
        context.user_data["quot"]["custom_item"] = {}
        await query.edit_message_text(
            "✏️ *Custom Item*\n\nEnter item description:",
            parse_mode="Markdown",
        )
        return QuotationStates.CUSTOM_DESCRIPTION

    # ─── Preset Pattern Flow ───
    async with async_session() as session:
        patterns = await quotation_service.get_active_patterns(session)
        pattern = next((p for p in patterns if str(p.id) == pattern_id), None)

    if not pattern:
        await query.edit_message_text("Pattern not found.", reply_markup=quotation_menu_keyboard())
        return ConversationHandler.END

    context.user_data["quot"]["current_pattern"] = {
        "pattern_id": pattern_id,
        "pattern_name": pattern.name,
        "pattern_description": pattern.description or pattern.name,
        "rate_per_sqft": str(pattern.rate_per_sqft),
        "pricing_type": pattern.pricing_type,
    }

    if pattern.pricing_type == "lumpsum":
        await query.edit_message_text(
            f"💰 *{pattern.name}*\n\nEnter lumpsum amount (RM):",
            parse_mode="Markdown",
        )
        return QuotationStates.ENTER_LUMPSUM

    if pattern.rate_per_sqft > 0:
        # Fixed rate — go straight to area
        await query.edit_message_text(
            f"📐 *{pattern.name}* — RM{pattern.rate_per_sqft}/sqft\n\nEnter area in sqft:",
            parse_mode="Markdown",
        )
        return QuotationStates.ENTER_AREA
    else:
        # Variable rate (e.g., Hacking per sqft) — ask for rate first
        await query.edit_message_text(
            f"📐 *{pattern.name}*\n\nEnter rate per sqft (RM):",
            parse_mode="Markdown",
        )
        return QuotationStates.ENTER_RATE


# ─── Custom Item Flow ───

UNIT_OPTIONS = ["SQFT", "UNIT", "METER", "LOT", "SET", "LS", "PCS", "TRIP"]


async def custom_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["quot"]["custom_item"]["description"] = update.message.text.strip()

    buttons = []
    row = []
    for u in UNIT_OPTIONS:
        row.append(InlineKeyboardButton(u, callback_data=f"cunit_{u}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="quot_cancel")])

    await update.message.reply_text(
        "📏 Select unit type:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return QuotationStates.CUSTOM_UNIT


async def custom_unit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    unit = query.data.replace("cunit_", "")
    context.user_data["quot"]["custom_item"]["unit"] = unit

    await query.edit_message_text(
        f"Unit: *{unit}*\n\nEnter quantity:",
        parse_mode="Markdown",
    )
    return QuotationStates.CUSTOM_QTY


async def custom_qty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        qty = Decimal(update.message.text.strip())
        if qty <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Enter a valid positive quantity:")
        return QuotationStates.CUSTOM_QTY

    context.user_data["quot"]["custom_item"]["quantity"] = str(qty)
    unit = context.user_data["quot"]["custom_item"]["unit"]

    if unit == "LS":
        # Lumpsum — ask for total amount directly
        await update.message.reply_text(
            f"Qty: *{qty}* {unit}\n\nEnter total amount (RM):",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"Qty: *{qty}* {unit}\n\nEnter price per {unit.lower()} (RM):",
            parse_mode="Markdown",
        )
    return QuotationStates.CUSTOM_PRICE


async def custom_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = Decimal(update.message.text.strip())
        if price < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Enter a valid positive price:")
        return QuotationStates.CUSTOM_PRICE

    custom = context.user_data["quot"].pop("custom_item")
    qty = Decimal(custom["quantity"])
    unit = custom["unit"]

    if unit == "LS":
        # For lumpsum, price entered IS the total amount
        amount = price
        unit_price = price
    else:
        unit_price = price
        amount = qty * unit_price

    item = {
        "pattern_id": None,
        "pattern_name": custom["description"],
        "pattern_description": custom["description"],
        "pricing_type": "custom",
        "unit": unit,
        "quantity": str(qty),
        "unit_price": str(unit_price),
        "rate_per_sqft": "0",
        "area_sqft": "0",
        "amount": str(amount),
    }
    context.user_data["quot"]["items"].append(item)

    if unit == "LS":
        added = f"✅ Added: {custom['description']} — {qty} {unit} = RM{amount:,.2f}"
    else:
        added = f"✅ Added: {custom['description']} — {qty} {unit} × RM{unit_price:,.2f} = RM{amount:,.2f}"

    return await _show_add_more(update.message, context, added)


async def enter_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom rate entry for variable-rate items."""
    try:
        rate = Decimal(update.message.text.strip())
        if rate <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Enter a valid positive rate per sqft:")
        return QuotationStates.ENTER_RATE

    context.user_data["quot"]["current_pattern"]["rate_per_sqft"] = str(rate)
    pattern_name = context.user_data["quot"]["current_pattern"]["pattern_name"]

    await update.message.reply_text(
        f"📐 *{pattern_name}* — RM{rate}/sqft\n\nEnter area in sqft:",
        parse_mode="Markdown",
    )
    return QuotationStates.ENTER_AREA


async def enter_lumpsum(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle lumpsum amount entry."""
    try:
        amount = Decimal(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Enter a valid positive amount:")
        return QuotationStates.ENTER_LUMPSUM

    pattern = context.user_data["quot"]["current_pattern"]
    item = {
        "pattern_id": pattern["pattern_id"],
        "pattern_name": pattern["pattern_name"],
        "pattern_description": pattern["pattern_description"],
        "pricing_type": "lumpsum",
        "rate_per_sqft": "0",
        "area_sqft": "0",
        "amount": str(amount),
    }
    context.user_data["quot"]["items"].append(item)
    context.user_data["quot"].pop("current_pattern", None)

    return await _show_add_more(update.message, context,
        f"✅ Added: {pattern['pattern_name']} — RM{amount:,.2f} (lumpsum)")


async def enter_area(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        area = Decimal(update.message.text.strip())
        if area <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Please enter a valid positive number for area (sqft):")
        return QuotationStates.ENTER_AREA

    pattern = context.user_data["quot"]["current_pattern"]
    rate = Decimal(pattern["rate_per_sqft"])
    amount = area * rate

    item = {
        "pattern_id": pattern["pattern_id"],
        "pattern_name": pattern["pattern_name"],
        "pattern_description": pattern["pattern_description"],
        "pricing_type": "per_sqft",
        "rate_per_sqft": str(rate),
        "area_sqft": str(area),
        "amount": str(amount),
    }
    context.user_data["quot"]["items"].append(item)
    context.user_data["quot"].pop("current_pattern", None)

    return await _show_add_more(update.message, context,
        f"✅ Added: {pattern['pattern_name']} — {area} sqft × RM{rate} = RM{amount:,.2f}")


async def _show_add_more(message, context, added_text: str) -> int:
    """Show the add more / done prompt after adding an item."""
    items = context.user_data["quot"]["items"]
    text = f"{added_text}\n\n{_items_summary(items)}"

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Add Another Item", callback_data="quot_add_more"),
                InlineKeyboardButton("✅ Done", callback_data="quot_done_items"),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="quot_cancel")],
        ]
    )

    await message.reply_text(text, reply_markup=buttons, parse_mode="Markdown")
    return QuotationStates.ADD_MORE_OR_DONE


async def add_more_or_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "quot_add_more":
        return await _show_pattern_selection(query, context)

    # Done adding items — ask for discount
    await query.edit_message_text(
        "💲 Apply discount? Enter percentage (0 for no discount):"
    )
    return QuotationStates.ENTER_DISCOUNT


async def enter_discount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        discount = Decimal(update.message.text.strip())
        if discount < 0 or discount > 100:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Enter a valid discount percentage (0-100):")
        return QuotationStates.ENTER_DISCOUNT

    context.user_data["quot"]["discount_pct"] = str(discount)

    # Show summary
    quot_data = context.user_data["quot"]
    items = quot_data["items"]
    subtotal = sum(Decimal(i["amount"]) for i in items)
    discount_amount = subtotal * discount / Decimal("100")
    total = subtotal - discount_amount

    text = (
        f"📝 *Quotation Summary*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Customer: {quot_data['customer_name']}\n"
        f"Job: {quot_data.get('job_location', '')}\n\n"
    )
    for i, item in enumerate(items, 1):
        text += f"  {i}. {_format_item_line(item)}\n"

    text += f"\n━━━━━━━━━━━━━━━━━━\n"
    text += f"Subtotal: RM{subtotal:,.2f}\n"
    if discount > 0:
        text += f"Discount ({discount}%): -RM{discount_amount:,.2f}\n"
    text += f"*TOTAL: RM{total:,.2f}*"

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm & Generate PDF", callback_data="quot_confirm"),
            ],
            [
                InlineKeyboardButton("✏️ Edit", callback_data="quot_restart"),
                InlineKeyboardButton("❌ Cancel", callback_data="quot_cancel"),
            ],
        ]
    )

    await update.message.reply_text(text, reply_markup=buttons, parse_mode="Markdown")
    return QuotationStates.CONFIRM


async def confirm_quotation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "quot_cancel":
        context.user_data.pop("quot", None)
        await query.edit_message_text("Cancelled.", reply_markup=quotation_menu_keyboard())
        return ConversationHandler.END

    if query.data == "quot_restart":
        context.user_data["quot"]["items"] = []
        return await _show_pattern_selection(query, context)

    quot_data = context.user_data.pop("quot")

    await query.edit_message_text("⏳ Generating quotation...")

    # Create quotation in database
    async with async_session() as session:
        line_items_data = []
        for item in quot_data["items"]:
            data = {
                "pattern_id": item.get("pattern_id"),
                "pricing_type": item["pricing_type"],
                "amount": item["amount"],
                "description": item.get("pattern_description", item["pattern_name"]),
            }
            if item["pricing_type"] == "per_sqft":
                data["area_sqft"] = item["area_sqft"]
                data["rate_per_sqft"] = item["rate_per_sqft"]
            elif item["pricing_type"] == "custom":
                data["unit"] = item.get("unit")
                data["quantity"] = item.get("quantity")
                data["unit_price"] = item.get("unit_price")
            line_items_data.append(data)

        quotation = await quotation_service.create_quotation(
            session,
            customer_id=quot_data["customer_id"],
            line_items_data=line_items_data,
            discount_pct=Decimal(quot_data.get("discount_pct", "0")),
            job_location=quot_data.get("job_location"),
        )

        # Reload with relationships
        quotation = await quotation_service.get_quotation(session, quotation.id)

        # Generate PDF
        pdf_bytes = generate_quotation_pdf(
            quotation=quotation,
            customer=quotation.customer,
            line_items=quotation.line_items,
        )

    # Send PDF
    await query.message.reply_document(
        document=io.BytesIO(pdf_bytes),
        filename=f"{quotation.quotation_number}.pdf",
        caption=f"✅ Quotation *{quotation.quotation_number}* created!\nTotal: RM{quotation.total_amount:,.2f}",
        parse_mode="Markdown",
    )

    # WhatsApp share link
    customer = quotation.customer
    if customer.phone:
        phone = customer.phone.replace("-", "").replace(" ", "")
        if not phone.startswith("+") and not phone.startswith("6"):
            phone = "60" + phone.lstrip("0")
        elif phone.startswith("0"):
            phone = "60" + phone[1:]

        wa_text = f"Assalamualaikum {customer.name}, here is your quotation {quotation.quotation_number} from {settings.COMPANY_NAME}."
        wa_url = f"https://wa.me/{phone}?text={urllib.parse.quote(wa_text)}"

        buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📱 Share via WhatsApp", url=wa_url)],
                [InlineKeyboardButton("« Back to Menu", callback_data="back_main")],
            ]
        )
    else:
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("« Back to Menu", callback_data="back_main")]]
        )

    await query.message.reply_text(
        "What would you like to do next?", reply_markup=buttons
    )
    return ConversationHandler.END


# ─── List Quotations ───


async def list_quotations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        quotations = await quotation_service.list_quotations(session)

    if not quotations:
        await query.edit_message_text(
            "No quotations yet.", reply_markup=quotation_menu_keyboard()
        )
        return

    status_emoji = {
        "draft": "📝", "sent": "📤", "accepted": "✅", "rejected": "❌", "expired": "⏰"
    }

    lines = ["📋 *All Quotations*\n━━━━━━━━━━━━━━━━━━"]
    buttons = []
    for q in quotations:
        emoji = status_emoji.get(q.status, "📝")
        lines.append(
            f"{emoji} {q.quotation_number} — {q.customer.name} — RM{q.total_amount:,.2f}"
        )
        buttons.append(
            [InlineKeyboardButton(
                f"{q.quotation_number} — {q.customer.name}",
                callback_data=f"quot_view_{q.id}",
            )]
        )
    buttons.append([InlineKeyboardButton("« Back", callback_data="menu_quotations")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def view_quotation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    quotation_id = query.data.replace("quot_view_", "")

    async with async_session() as session:
        quotation = await quotation_service.get_quotation(session, quotation_id)

    if not quotation:
        await query.edit_message_text("Quotation not found.", reply_markup=quotation_menu_keyboard())
        return

    status_emoji = {
        "draft": "📝", "sent": "📤", "accepted": "✅", "rejected": "❌", "expired": "⏰"
    }

    text = (
        f"📝 *{quotation.quotation_number}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Customer: {quotation.customer.name}\n"
        f"Job: {quotation.job_location or 'N/A'}\n"
        f"Status: {status_emoji.get(quotation.status, '')} {quotation.status.upper()}\n"
        f"Total: RM{quotation.total_amount:,.2f}\n"
        f"Valid until: {quotation.valid_until.strftime('%d/%m/%Y') if quotation.valid_until else 'N/A'}\n\n"
        f"Items:\n"
    )
    for item in quotation.line_items:
        # Show short name in Telegram (first line of description)
        desc = (item.description or "Item").split("\n")[0]
        if item.pricing_type == "lumpsum":
            text += f"  • {desc} — RM{item.amount:,.2f} (LS)\n"
        else:
            text += f"  • {item.area_sqft} sqft × RM{item.rate_per_sqft} = RM{item.amount:,.2f}\n"

    buttons = [
        [InlineKeyboardButton("📄 Download PDF", callback_data=f"quot_pdf_{quotation.id}")],
    ]

    if quotation.status == "draft":
        buttons.append([
            InlineKeyboardButton("📤 Mark Sent", callback_data=f"quot_status_{quotation.id}_sent"),
            InlineKeyboardButton("✅ Accept", callback_data=f"quot_status_{quotation.id}_accepted"),
        ])
    elif quotation.status == "sent":
        buttons.append([
            InlineKeyboardButton("✅ Accept", callback_data=f"quot_status_{quotation.id}_accepted"),
            InlineKeyboardButton("❌ Reject", callback_data=f"quot_status_{quotation.id}_rejected"),
        ])

    buttons.append([InlineKeyboardButton("« Back", callback_data="quot_list")])

    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def download_quotation_pdf(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer("Generating PDF...")
    quotation_id = query.data.replace("quot_pdf_", "")

    async with async_session() as session:
        quotation = await quotation_service.get_quotation(session, quotation_id)

    if not quotation:
        await query.message.reply_text("Quotation not found.")
        return

    pdf_bytes = generate_quotation_pdf(
        quotation=quotation,
        customer=quotation.customer,
        line_items=quotation.line_items,
    )

    await query.message.reply_document(
        document=io.BytesIO(pdf_bytes),
        filename=f"{quotation.quotation_number}.pdf",
        caption=f"📄 {quotation.quotation_number}",
    )


async def update_quotation_status(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.replace("quot_status_", "").rsplit("_", 1)
    quotation_id = parts[0]
    new_status = parts[1]

    async with async_session() as session:
        quotation = await quotation_service.update_quotation_status(
            session, quotation_id, new_status
        )

    if quotation:
        await query.edit_message_text(
            f"✅ Quotation {quotation.quotation_number} marked as *{new_status.upper()}*",
            reply_markup=quotation_menu_keyboard(),
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text(
            "Quotation not found.", reply_markup=quotation_menu_keyboard()
        )


async def list_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📝 Draft", callback_data="quot_filter_draft"),
                InlineKeyboardButton("📤 Sent", callback_data="quot_filter_sent"),
            ],
            [
                InlineKeyboardButton("✅ Accepted", callback_data="quot_filter_accepted"),
                InlineKeyboardButton("❌ Rejected", callback_data="quot_filter_rejected"),
            ],
            [InlineKeyboardButton("« Back", callback_data="menu_quotations")],
        ]
    )
    await query.edit_message_text("Filter by status:", reply_markup=buttons)


async def filtered_quotations(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    status = query.data.replace("quot_filter_", "")

    async with async_session() as session:
        quotations = await quotation_service.list_quotations(session, status=status)

    if not quotations:
        await query.edit_message_text(
            f"No {status} quotations.",
            reply_markup=quotation_menu_keyboard(),
        )
        return

    lines = [f"📋 *{status.upper()} Quotations*\n━━━━━━━━━━━━━━━━━━"]
    buttons = []
    for q in quotations:
        lines.append(f"• {q.quotation_number} — {q.customer.name} — RM{q.total_amount:,.2f}")
        buttons.append(
            [InlineKeyboardButton(
                f"{q.quotation_number} — {q.customer.name}",
                callback_data=f"quot_view_{q.id}",
            )]
        )
    buttons.append([InlineKeyboardButton("« Back", callback_data="quot_by_status")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


# ─── Cancel fallback ───


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("quot", None)
    if update.message:
        await update.message.reply_text("Cancelled.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("quot", None)
    await query.edit_message_text("Cancelled.", reply_markup=quotation_menu_keyboard())
    return ConversationHandler.END


# ─── Register handlers ───


def get_quotation_handlers() -> list:
    create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_quotation_start, pattern="^quot_new$")],
        states={
            QuotationStates.SELECT_CUSTOMER: [
                CallbackQueryHandler(select_customer, pattern=r"^qcust_"),
                CallbackQueryHandler(cancel_callback, pattern="^quot_cancel$"),
            ],
            QuotationStates.SEARCH_CUSTOMER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, search_customer),
            ],
            QuotationStates.ENTER_JOB_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, enter_job_location),
            ],
            QuotationStates.SELECT_PATTERN: [
                CallbackQueryHandler(select_pattern, pattern=r"^qpat_"),
                CallbackQueryHandler(cancel_callback, pattern="^quot_cancel$"),
            ],
            QuotationStates.ENTER_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, enter_rate),
            ],
            QuotationStates.ENTER_AREA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, enter_area),
            ],
            QuotationStates.ENTER_LUMPSUM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, enter_lumpsum),
            ],
            QuotationStates.CUSTOM_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, custom_description),
            ],
            QuotationStates.CUSTOM_UNIT: [
                CallbackQueryHandler(custom_unit, pattern=r"^cunit_"),
                CallbackQueryHandler(cancel_callback, pattern="^quot_cancel$"),
            ],
            QuotationStates.CUSTOM_QTY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, custom_qty),
            ],
            QuotationStates.CUSTOM_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, custom_price),
            ],
            QuotationStates.ADD_MORE_OR_DONE: [
                CallbackQueryHandler(add_more_or_done, pattern=r"^quot_(add_more|done_items)$"),
                CallbackQueryHandler(cancel_callback, pattern="^quot_cancel$"),
            ],
            QuotationStates.ENTER_DISCOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, enter_discount),
            ],
            QuotationStates.CONFIRM: [
                CallbackQueryHandler(confirm_quotation, pattern=r"^quot_(confirm|cancel|restart)$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_callback, pattern="^quot_cancel$"),
        ],
        conversation_timeout=300,
    )

    return [
        create_conv,
        CallbackQueryHandler(list_quotations, pattern="^quot_list$"),
        CallbackQueryHandler(view_quotation, pattern=r"^quot_view_"),
        CallbackQueryHandler(download_quotation_pdf, pattern=r"^quot_pdf_"),
        CallbackQueryHandler(update_quotation_status, pattern=r"^quot_status_"),
        CallbackQueryHandler(list_by_status, pattern="^quot_by_status$"),
        CallbackQueryHandler(filtered_quotations, pattern=r"^quot_filter_"),
    ]
