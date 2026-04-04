from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.invoice import Invoice
from app.models.line_item import LineItem
from app.models.pattern import Pattern
from app.models.quotation import Quotation


async def get_next_quotation_number(session: AsyncSession) -> str:
    """Generate QUO number in format: QUO25/618/001"""
    year_short = date.today().strftime("%y")  # e.g. "26"
    prefix = f"QUO{year_short}/"
    stmt = (
        select(Quotation.quotation_number)
        .where(Quotation.quotation_number.like(f"{prefix}%"))
        .order_by(Quotation.quotation_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    last = result.scalar_one_or_none()

    if last:
        # Parse QUO25/618/001 -> extract middle seq
        parts = last.replace(prefix, "").split("/")
        seq = int(parts[0]) + 1
    else:
        seq = 1

    return f"{prefix}{seq:03d}/001"


async def create_quotation(
    session: AsyncSession,
    customer_id: str,
    line_items_data: list[dict],
    discount_pct: Decimal = Decimal("0"),
    job_location: str | None = None,
    notes: str | None = None,
    validity_days: int = 7,
) -> Quotation:
    quotation_number = await get_next_quotation_number(session)

    total_area = Decimal("0")
    subtotal = Decimal("0")
    items = []

    for item_data in line_items_data:
        pricing_type = item_data.get("pricing_type", "per_sqft")

        if pricing_type == "custom":
            amount = Decimal(str(item_data["amount"]))
            qty = Decimal(str(item_data.get("quantity", "0")))
            unit_price = Decimal(str(item_data.get("unit_price", "0")))
            items.append(
                LineItem(
                    pattern_id=None,
                    pricing_type="custom",
                    unit=item_data.get("unit"),
                    quantity=qty,
                    unit_price=unit_price,
                    amount=amount,
                    description=item_data.get("description"),
                )
            )
        elif pricing_type == "lumpsum":
            amount = Decimal(str(item_data["amount"]))
            items.append(
                LineItem(
                    pattern_id=item_data.get("pattern_id"),
                    pricing_type="lumpsum",
                    area_sqft=None,
                    rate_per_sqft=None,
                    amount=amount,
                    description=item_data.get("description"),
                )
            )
        else:
            area = Decimal(str(item_data["area_sqft"]))
            rate = Decimal(str(item_data["rate_per_sqft"]))
            amount = area * rate
            total_area += area
            items.append(
                LineItem(
                    pattern_id=item_data.get("pattern_id"),
                    pricing_type="per_sqft",
                    area_sqft=area,
                    rate_per_sqft=rate,
                    amount=amount,
                    description=item_data.get("description"),
                )
            )

        subtotal += amount

    discount_amount = subtotal * discount_pct / Decimal("100")
    total_amount = subtotal - discount_amount

    quotation = Quotation(
        quotation_number=quotation_number,
        customer_id=customer_id,
        job_location=job_location,
        total_area_sqft=total_area,
        subtotal=subtotal,
        discount_pct=discount_pct,
        discount_amount=discount_amount,
        total_amount=total_amount,
        notes=notes,
        status="draft",
        valid_until=date.today() + timedelta(days=validity_days),
    )
    quotation.line_items = items

    session.add(quotation)
    await session.commit()
    await session.refresh(quotation)
    return quotation


async def get_quotation(session: AsyncSession, quotation_id: str) -> Quotation | None:
    stmt = (
        select(Quotation)
        .options(selectinload(Quotation.line_items).selectinload(LineItem.pattern))
        .options(selectinload(Quotation.customer))
        .where(Quotation.id == quotation_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_quotations(
    session: AsyncSession,
    status: str | None = None,
    customer_id: str | None = None,
    limit: int = 20,
) -> list[Quotation]:
    stmt = (
        select(Quotation)
        .options(selectinload(Quotation.customer))
        .order_by(Quotation.created_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(Quotation.status == status)
    if customer_id:
        stmt = stmt.where(Quotation.customer_id == customer_id)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_quotation_status(
    session: AsyncSession, quotation_id: str, status: str
) -> Quotation | None:
    quotation = await session.get(Quotation, quotation_id)
    if not quotation:
        return None
    quotation.status = status
    await session.commit()
    await session.refresh(quotation)
    return quotation


async def get_active_patterns(session: AsyncSession) -> list[Pattern]:
    stmt = select(Pattern).where(Pattern.is_active.is_(True)).order_by(Pattern.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_accepted_quotations_without_invoice(
    session: AsyncSession,
) -> list[Quotation]:
    stmt = (
        select(Quotation)
        .outerjoin(Invoice)
        .options(selectinload(Quotation.customer))
        .where(Quotation.status == "accepted", Invoice.id.is_(None))
        .order_by(Quotation.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
