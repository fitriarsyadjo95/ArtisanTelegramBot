from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quotation import Quotation
from app.services import invoice_service, slot_service


async def get_quotation_status_summary(session: AsyncSession) -> dict:
    """Get quotation counts and pipeline value grouped by status."""
    stmt = select(
        Quotation.status,
        func.count().label("count"),
        func.coalesce(func.sum(Quotation.total_amount), 0).label("total"),
    ).group_by(Quotation.status)

    result = await session.execute(stmt)
    rows = result.all()

    summary = {}
    for status, count, total in rows:
        summary[status] = {"count": count, "total": Decimal(str(total))}

    return summary


async def get_report_summary(session: AsyncSession) -> dict:
    """Get complete business report data."""
    unpaid_invoices = await invoice_service.get_unpaid_invoices(session)
    quotation_summary = await get_quotation_status_summary(session)
    upcoming_visits = await slot_service.get_upcoming_visits(session, days_ahead=7)

    total_outstanding = sum(
        (inv.total_amount - inv.amount_paid) for inv in unpaid_invoices
    )
    count_unpaid = sum(1 for inv in unpaid_invoices if inv.payment_status == "unpaid")
    count_partial = sum(1 for inv in unpaid_invoices if inv.payment_status == "partial")

    pipeline_value = Decimal("0")
    for status in ("draft", "sent"):
        if status in quotation_summary:
            pipeline_value += quotation_summary[status]["total"]

    return {
        "pending_payments": {
            "invoices": unpaid_invoices,
            "total_outstanding": total_outstanding,
            "count_unpaid": count_unpaid,
            "count_partial": count_partial,
        },
        "quotation_pipeline": {
            "counts": quotation_summary,
            "pipeline_value": pipeline_value,
        },
        "upcoming_visits": {
            "visits": upcoming_visits,
            "count": len(upcoming_visits),
        },
    }
