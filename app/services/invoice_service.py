from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.invoice import Invoice
from app.models.line_item import LineItem
from app.models.quotation import Quotation


async def get_next_invoice_number(session: AsyncSession) -> str:
    year = date.today().year
    prefix = f"INV-{year}-"
    stmt = (
        select(Invoice.invoice_number)
        .where(Invoice.invoice_number.like(f"{prefix}%"))
        .order_by(Invoice.invoice_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    last = result.scalar_one_or_none()

    if last:
        seq = int(last.split("-")[-1]) + 1
    else:
        seq = 1

    return f"{prefix}{seq:04d}"


async def create_invoice_from_quotation(
    session: AsyncSession,
    quotation_id: str,
    due_days: int = 14,
    notes: str | None = None,
) -> Invoice:
    quotation = await session.get(Quotation, quotation_id)
    if not quotation:
        raise ValueError("Quotation not found")

    invoice_number = await get_next_invoice_number(session)

    invoice = Invoice(
        invoice_number=invoice_number,
        quotation_id=quotation.id,
        customer_id=quotation.customer_id,
        total_amount=quotation.total_amount,
        amount_paid=Decimal("0"),
        payment_status="unpaid",
        due_date=date.today() + timedelta(days=due_days),
        notes=notes,
    )

    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return invoice


async def get_invoice(session: AsyncSession, invoice_id: str) -> Invoice | None:
    stmt = (
        select(Invoice)
        .options(
            selectinload(Invoice.customer),
            selectinload(Invoice.quotation)
            .selectinload(Quotation.line_items)
            .selectinload(LineItem.pattern),
        )
        .where(Invoice.id == invoice_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_invoices(
    session: AsyncSession,
    payment_status: str | None = None,
    limit: int = 20,
) -> list[Invoice]:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .order_by(Invoice.created_at.desc())
        .limit(limit)
    )
    if payment_status:
        stmt = stmt.where(Invoice.payment_status == payment_status)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def record_payment(
    session: AsyncSession,
    invoice_id: str,
    amount: Decimal,
) -> Invoice:
    invoice = await session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")

    invoice.amount_paid += amount

    if invoice.amount_paid >= invoice.total_amount:
        invoice.payment_status = "paid"
        invoice.paid_at = datetime.now(timezone.utc)
    elif invoice.amount_paid > 0:
        invoice.payment_status = "partial"

    await session.commit()
    await session.refresh(invoice)
    return invoice


async def get_unpaid_invoices(session: AsyncSession) -> list[Invoice]:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .where(Invoice.payment_status.in_(["unpaid", "partial"]))
        .order_by(Invoice.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
