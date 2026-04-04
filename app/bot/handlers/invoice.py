import io
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
from app.bot.keyboards import invoice_menu_keyboard, main_menu_keyboard
from app.bot.states import InvoiceStates
from app.database import async_session
from app.services import invoice_service, quotation_service
from app.services.pdf_service import generate_invoice_pdf


# ─── Create Invoice from Quotation ───


async def create_invoice_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        quotations = await quotation_service.get_accepted_quotations_without_invoice(session)

    if not quotations:
        await query.edit_message_text(
            "No accepted quotations available for invoicing.\n\n"
            "Accept a quotation first.",
            reply_markup=invoice_menu_keyboard(),
        )
        return ConversationHandler.END

    buttons = []
    for q in quotations:
        buttons.append(
            [InlineKeyboardButton(
                f"{q.quotation_number} — {q.customer.name} — RM{q.total_amount:,.2f}",
                callback_data=f"inv_quot_{q.id}",
            )]
        )
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="inv_cancel")])

    await query.edit_message_text(
        "💰 *Create Invoice*\n━━━━━━━━━━━━━━━━━━\n\nSelect a quotation:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )
    return InvoiceStates.SELECT_QUOTATION


async def select_quotation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    quotation_id = query.data.replace("inv_quot_", "")
    context.user_data["inv_quotation_id"] = quotation_id

    await query.edit_message_text(
        "📅 Enter payment due date (days from now, e.g. 14):"
    )
    return InvoiceStates.SET_DUE_DAYS


async def set_due_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        days = int(update.message.text.strip())
        if days < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid number of days:")
        return InvoiceStates.SET_DUE_DAYS

    context.user_data["inv_due_days"] = days
    quotation_id = context.user_data["inv_quotation_id"]

    async with async_session() as session:
        quotation = await quotation_service.get_quotation(session, quotation_id)

    from datetime import date, timedelta
    due_date = date.today() + timedelta(days=days)

    text = (
        f"💰 *Invoice Summary*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Quotation: {quotation.quotation_number}\n"
        f"Customer: {quotation.customer.name}\n"
        f"Total: RM{quotation.total_amount:,.2f}\n"
        f"Due Date: {due_date.strftime('%d/%m/%Y')}\n"
    )

    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Create Invoice", callback_data="inv_confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="inv_cancel")],
        ]
    )

    await update.message.reply_text(text, reply_markup=buttons, parse_mode="Markdown")
    return InvoiceStates.CONFIRM


async def confirm_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    quotation_id = context.user_data.pop("inv_quotation_id")
    due_days = context.user_data.pop("inv_due_days")

    await query.edit_message_text("⏳ Creating invoice...")

    async with async_session() as session:
        invoice = await invoice_service.create_invoice_from_quotation(
            session, quotation_id, due_days=due_days
        )
        invoice = await invoice_service.get_invoice(session, invoice.id)

        pdf_bytes = generate_invoice_pdf(
            invoice=invoice,
            quotation=invoice.quotation,
            customer=invoice.customer,
            line_items=invoice.quotation.line_items,
        )

    await query.message.reply_document(
        document=io.BytesIO(pdf_bytes),
        filename=f"{invoice.invoice_number}.pdf",
        caption=(
            f"✅ Invoice *{invoice.invoice_number}* created!\n"
            f"Total: RM{invoice.total_amount:,.2f}\n"
            f"Due: {invoice.due_date.strftime('%d/%m/%Y')}"
        ),
        parse_mode="Markdown",
    )

    await query.message.reply_text(
        "What next?", reply_markup=invoice_menu_keyboard()
    )
    return ConversationHandler.END


# ─── Record Payment ───


async def payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        invoices = await invoice_service.get_unpaid_invoices(session)

    if not invoices:
        await query.edit_message_text(
            "No unpaid invoices.", reply_markup=invoice_menu_keyboard()
        )
        return ConversationHandler.END

    buttons = []
    for inv in invoices:
        outstanding = inv.total_amount - inv.amount_paid
        status = "🟡" if inv.payment_status == "partial" else "🔴"
        buttons.append(
            [InlineKeyboardButton(
                f"{status} {inv.invoice_number} — {inv.customer.name} — RM{outstanding:,.2f} due",
                callback_data=f"inv_pay_{inv.id}",
            )]
        )
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="inv_cancel")])

    await query.edit_message_text(
        "💳 *Record Payment*\n━━━━━━━━━━━━━━━━━━\n\nSelect invoice:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )
    return InvoiceStates.SELECT_INVOICE


async def select_invoice_for_payment(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    invoice_id = query.data.replace("inv_pay_", "")
    context.user_data["pay_invoice_id"] = invoice_id

    async with async_session() as session:
        invoice = await invoice_service.get_invoice(session, invoice_id)

    outstanding = invoice.total_amount - invoice.amount_paid

    await query.edit_message_text(
        f"💳 *{invoice.invoice_number}*\n"
        f"Total: RM{invoice.total_amount:,.2f}\n"
        f"Paid: RM{invoice.amount_paid:,.2f}\n"
        f"Outstanding: RM{outstanding:,.2f}\n\n"
        f"Enter payment amount:",
        parse_mode="Markdown",
    )
    return InvoiceStates.ENTER_PAYMENT


async def enter_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = Decimal(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Enter a valid positive amount:")
        return InvoiceStates.ENTER_PAYMENT

    invoice_id = context.user_data.pop("pay_invoice_id")

    async with async_session() as session:
        invoice = await invoice_service.record_payment(session, invoice_id, amount)

    outstanding = invoice.total_amount - invoice.amount_paid
    status_emoji = {"unpaid": "🔴", "partial": "🟡", "paid": "🟢"}

    text = (
        f"✅ Payment of RM{amount:,.2f} recorded!\n\n"
        f"*{invoice.invoice_number}*\n"
        f"Status: {status_emoji.get(invoice.payment_status, '')} {invoice.payment_status.upper()}\n"
        f"Paid: RM{invoice.amount_paid:,.2f} / RM{invoice.total_amount:,.2f}\n"
    )
    if outstanding > 0:
        text += f"Outstanding: RM{outstanding:,.2f}"

    await update.message.reply_text(
        text, reply_markup=invoice_menu_keyboard(), parse_mode="Markdown"
    )
    return ConversationHandler.END


# ─── List Invoices ───


async def list_invoices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        invoices = await invoice_service.list_invoices(session)

    if not invoices:
        await query.edit_message_text(
            "No invoices yet.", reply_markup=invoice_menu_keyboard()
        )
        return

    status_emoji = {"unpaid": "🔴", "partial": "🟡", "paid": "🟢"}

    lines = ["💰 *All Invoices*\n━━━━━━━━━━━━━━━━━━"]
    buttons = []
    for inv in invoices:
        emoji = status_emoji.get(inv.payment_status, "")
        lines.append(
            f"{emoji} {inv.invoice_number} — {inv.customer.name} — RM{inv.total_amount:,.2f}"
        )
        buttons.append(
            [InlineKeyboardButton(
                f"{inv.invoice_number} — {inv.customer.name}",
                callback_data=f"inv_view_{inv.id}",
            )]
        )
    buttons.append([InlineKeyboardButton("« Back", callback_data="menu_invoices")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def view_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    invoice_id = query.data.replace("inv_view_", "")

    async with async_session() as session:
        invoice = await invoice_service.get_invoice(session, invoice_id)

    if not invoice:
        await query.edit_message_text("Invoice not found.", reply_markup=invoice_menu_keyboard())
        return

    status_emoji = {"unpaid": "🔴", "partial": "🟡", "paid": "🟢"}
    outstanding = invoice.total_amount - invoice.amount_paid

    text = (
        f"💰 *{invoice.invoice_number}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Customer: {invoice.customer.name}\n"
        f"Quotation: {invoice.quotation.quotation_number}\n"
        f"Status: {status_emoji.get(invoice.payment_status, '')} {invoice.payment_status.upper()}\n"
        f"Total: RM{invoice.total_amount:,.2f}\n"
        f"Paid: RM{invoice.amount_paid:,.2f}\n"
        f"Outstanding: RM{outstanding:,.2f}\n"
        f"Due: {invoice.due_date.strftime('%d/%m/%Y') if invoice.due_date else 'N/A'}\n"
    )

    buttons = [
        [InlineKeyboardButton("📄 Download PDF", callback_data=f"inv_pdf_{invoice.id}")],
    ]
    if invoice.payment_status != "paid":
        buttons.append(
            [InlineKeyboardButton("💳 Record Payment", callback_data=f"inv_pay_{invoice.id}")]
        )
    buttons.append([InlineKeyboardButton("« Back", callback_data="inv_list")])

    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def download_invoice_pdf(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer("Generating PDF...")
    invoice_id = query.data.replace("inv_pdf_", "")

    async with async_session() as session:
        invoice = await invoice_service.get_invoice(session, invoice_id)

    if not invoice:
        await query.message.reply_text("Invoice not found.")
        return

    pdf_bytes = generate_invoice_pdf(
        invoice=invoice,
        quotation=invoice.quotation,
        customer=invoice.customer,
        line_items=invoice.quotation.line_items,
    )

    await query.message.reply_document(
        document=io.BytesIO(pdf_bytes),
        filename=f"{invoice.invoice_number}.pdf",
        caption=f"📄 {invoice.invoice_number}",
    )


# ─── Cancel ───


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("inv_quotation_id", None)
    context.user_data.pop("inv_due_days", None)
    context.user_data.pop("pay_invoice_id", None)
    if update.message:
        await update.message.reply_text("Cancelled.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Cancelled.", reply_markup=invoice_menu_keyboard())
    return ConversationHandler.END


# ─── Register handlers ───


def get_invoice_handlers() -> list:
    create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_invoice_start, pattern="^inv_from_quot$")],
        states={
            InvoiceStates.SELECT_QUOTATION: [
                CallbackQueryHandler(select_quotation, pattern=r"^inv_quot_"),
                CallbackQueryHandler(cancel_callback, pattern="^inv_cancel$"),
            ],
            InvoiceStates.SET_DUE_DAYS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, set_due_days),
            ],
            InvoiceStates.CONFIRM: [
                CallbackQueryHandler(confirm_invoice, pattern="^inv_confirm$"),
                CallbackQueryHandler(cancel_callback, pattern="^inv_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=300,
    )

    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment_start, pattern="^inv_payment$")],
        states={
            InvoiceStates.SELECT_INVOICE: [
                CallbackQueryHandler(select_invoice_for_payment, pattern=r"^inv_pay_"),
                CallbackQueryHandler(cancel_callback, pattern="^inv_cancel$"),
            ],
            InvoiceStates.ENTER_PAYMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & admin_filter, enter_payment),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=300,
    )

    return [
        create_conv,
        payment_conv,
        CallbackQueryHandler(list_invoices, pattern="^inv_list$"),
        CallbackQueryHandler(view_invoice, pattern=r"^inv_view_"),
        CallbackQueryHandler(download_invoice_pdf, pattern=r"^inv_pdf_"),
    ]
