from datetime import date, timedelta
from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from app.database import async_session
from app.services import invoice_service, report_service, slot_service
from app.services.quotation_service import list_quotations


# ── Keyboards ──────────────────────────────────────────────

def report_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💰 Payments", callback_data="rpt_payments"),
                InlineKeyboardButton("📝 Quotations", callback_data="rpt_quotations"),
            ],
            [
                InlineKeyboardButton("📅 Visit Schedule", callback_data="rpt_visits"),
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="rpt_refresh"),
            ],
            [
                InlineKeyboardButton("« Back to Menu", callback_data="back_main"),
            ],
        ]
    )


def report_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("« Back to Report", callback_data="menu_reports")]]
    )


# ── Helpers ────────────────────────────────────────────────

STATUS_EMOJI = {
    "draft": "📝",
    "sent": "📤",
    "accepted": "✅",
    "rejected": "❌",
    "expired": "⏰",
}

PAYMENT_EMOJI = {"unpaid": "🔴", "partial": "🟡", "paid": "🟢"}


def _relative_day(d: date) -> str:
    today = date.today()
    diff = (d - today).days
    if diff == 0:
        return "Today"
    if diff == 1:
        return "Tomorrow"
    return d.strftime("%a %d/%m")


# ── Summary ────────────────────────────────────────────────

async def show_report_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        data = await report_service.get_report_summary(session)

    pp = data["pending_payments"]
    qp = data["quotation_pipeline"]
    uv = data["upcoming_visits"]

    # Pending payments section
    if pp["count_unpaid"] or pp["count_partial"]:
        payment_lines = f"🔴 {pp['count_unpaid']} unpaid  🟡 {pp['count_partial']} partial"
        payment_lines += f"\nOutstanding: *RM{pp['total_outstanding']:,.2f}*"
    else:
        payment_lines = "No pending payments ✅"

    # Quotation pipeline section
    counts = qp["counts"]
    status_parts = []
    for s in ("draft", "sent", "accepted", "rejected", "expired"):
        c = counts.get(s, {}).get("count", 0)
        status_parts.append(f"{STATUS_EMOJI[s]} {c} {s}")
    quot_line1 = "  ".join(status_parts[:3])
    quot_line2 = "  ".join(status_parts[3:])
    pipeline_val = qp["pipeline_value"]

    # Upcoming visits section
    if uv["count"]:
        visit_line = f"{uv['count']} visit{'s' if uv['count'] != 1 else ''} scheduled"
        first = uv["visits"][0]
        cust_name = first.customer.name if first.customer else "—"
        visit_line += f"\nNext: {_relative_day(first.visit_date)} — {cust_name}"
    else:
        visit_line = "No upcoming visits"

    text = (
        "📊 *Business Report*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *Pending Payments*\n{payment_lines}\n\n"
        f"📝 *Quotation Pipeline*\n{quot_line1}\n{quot_line2}\n"
        f"Pipeline value: *RM{pipeline_val:,.2f}*\n\n"
        f"📅 *Upcoming Visits (7 days)*\n{visit_line}"
    )

    await query.edit_message_text(
        text, reply_markup=report_menu_keyboard(), parse_mode="Markdown"
    )


# ── Pending Payments Detail ───────────────────────────────

async def show_pending_payments_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        invoices = await invoice_service.get_unpaid_invoices(session)

    if not invoices:
        text = (
            "💰 *Pending Payments*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "No pending payments ✅"
        )
        await query.edit_message_text(
            text, reply_markup=report_back_keyboard(), parse_mode="Markdown"
        )
        return

    today = date.today()
    total_outstanding = sum(inv.total_amount - inv.amount_paid for inv in invoices)

    lines = [
        "💰 *Pending Payments*",
        "━━━━━━━━━━━━━━━━━━",
        f"Total outstanding: *RM{total_outstanding:,.2f}*",
        "",
    ]

    for inv in invoices[:15]:
        emoji = PAYMENT_EMOJI.get(inv.payment_status, "⚪")
        cust_name = inv.customer.name if inv.customer else "—"
        outstanding = inv.total_amount - inv.amount_paid

        line = f"{emoji} *{inv.invoice_number}* — {cust_name}"
        if inv.payment_status == "partial":
            line += f"\n   RM{outstanding:,.2f} due (paid RM{inv.amount_paid:,.2f})"
        else:
            line += f"\n   RM{outstanding:,.2f} due"

        if inv.due_date:
            due_str = inv.due_date.strftime("%d/%m/%Y")
            if inv.due_date < today:
                line += f" · ⚠️ OVERDUE {due_str}"
            else:
                line += f" · Due {due_str}"

        lines.append(line)
        lines.append("")

    if len(invoices) > 15:
        lines.append(f"_...and {len(invoices) - 15} more_")

    await query.edit_message_text(
        "\n".join(lines), reply_markup=report_back_keyboard(), parse_mode="Markdown"
    )


# ── Quotation Pipeline Detail ─────────────────────────────

async def show_quotation_pipeline_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        quotations = await list_quotations(session, limit=50)

    if not quotations:
        text = (
            "📝 *Quotation Pipeline*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "No quotations yet"
        )
        await query.edit_message_text(
            text, reply_markup=report_back_keyboard(), parse_mode="Markdown"
        )
        return

    grouped = {}
    for q in quotations:
        grouped.setdefault(q.status, []).append(q)

    lines = [
        "📝 *Quotation Pipeline*",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]

    # Show draft and sent in detail (actionable)
    for status in ("draft", "sent"):
        items = grouped.get(status, [])
        emoji = STATUS_EMOJI[status]
        lines.append(f"{emoji} *{status.title()} ({len(items)})*")
        if items:
            for q in items[:5]:
                cust_name = q.customer.name if q.customer else "—"
                lines.append(f"  {q.quotation_number} — {cust_name} — RM{q.total_amount:,.2f}")
            if len(items) > 5:
                lines.append(f"  _...and {len(items) - 5} more_")
        else:
            lines.append("  None")
        lines.append("")

    # Show others as counts
    other_parts = []
    for status in ("accepted", "rejected", "expired"):
        items = grouped.get(status, [])
        other_parts.append(f"{STATUS_EMOJI[status]} {len(items)} {status}")
    lines.append(" · ".join(other_parts))

    await query.edit_message_text(
        "\n".join(lines), reply_markup=report_back_keyboard(), parse_mode="Markdown"
    )


# ── Upcoming Visits Detail ────────────────────────────────

async def show_upcoming_visits_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        visits = await slot_service.get_upcoming_visits(session, days_ahead=7)

    if not visits:
        text = (
            "📅 *Upcoming Visits*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "No visits in the next 7 days"
        )
        await query.edit_message_text(
            text, reply_markup=report_back_keyboard(), parse_mode="Markdown"
        )
        return

    # Group by date
    by_date = {}
    for v in visits:
        by_date.setdefault(v.visit_date, []).append(v)

    lines = [
        "📅 *Upcoming Visits*",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for d in sorted(by_date.keys()):
        day_label = _relative_day(d)
        date_str = d.strftime("%d/%m/%Y")
        lines.append(f"*{day_label} — {date_str}*")
        for v in by_date[d]:
            cust_name = v.customer.name if v.customer else "—"
            time_str = v.visit_time or "TBC"
            detail = f"  🕐 {time_str} — {cust_name}"
            if v.details:
                detail += f" ({v.details})"
            lines.append(detail)
        lines.append("")

    await query.edit_message_text(
        "\n".join(lines), reply_markup=report_back_keyboard(), parse_mode="Markdown"
    )


# ── Refresh ───────────────────────────────────────────────

async def refresh_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_report_summary(update, context)


# ── Registration ──────────────────────────────────────────

def get_report_handlers() -> list:
    return [
        CallbackQueryHandler(show_report_summary, pattern="^menu_reports$"),
        CallbackQueryHandler(show_pending_payments_detail, pattern="^rpt_payments$"),
        CallbackQueryHandler(show_quotation_pipeline_detail, pattern="^rpt_quotations$"),
        CallbackQueryHandler(show_upcoming_visits_detail, pattern="^rpt_visits$"),
        CallbackQueryHandler(refresh_report, pattern="^rpt_refresh$"),
    ]
