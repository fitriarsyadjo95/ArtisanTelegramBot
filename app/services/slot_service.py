from datetime import date, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.site_visit import SiteVisit


async def create_visit(
    session: AsyncSession,
    customer_id: str,
    visit_date: date,
    visit_time: str,
    details: str | None = None,
    google_event_id: str | None = None,
    notes: str | None = None,
) -> SiteVisit:
    visit = SiteVisit(
        customer_id=customer_id,
        visit_date=visit_date,
        visit_time=visit_time,
        details=details,
        google_event_id=google_event_id,
        status="scheduled",
        notes=notes,
    )
    session.add(visit)
    await session.commit()
    await session.refresh(visit)
    return visit


async def get_visits_for_date(
    session: AsyncSession, target_date: date
) -> list[SiteVisit]:
    stmt = (
        select(SiteVisit)
        .options(selectinload(SiteVisit.customer))
        .where(
            and_(
                SiteVisit.visit_date == target_date,
                SiteVisit.status != "cancelled",
            )
        )
        .order_by(SiteVisit.visit_time)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_upcoming_visits(
    session: AsyncSession, days_ahead: int = 7
) -> list[SiteVisit]:
    today = date.today()
    end = today + timedelta(days=days_ahead)

    stmt = (
        select(SiteVisit)
        .options(selectinload(SiteVisit.customer))
        .where(
            and_(
                SiteVisit.visit_date >= today,
                SiteVisit.visit_date <= end,
                SiteVisit.status == "scheduled",
            )
        )
        .order_by(SiteVisit.visit_date, SiteVisit.visit_time)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def cancel_visit(session: AsyncSession, visit_id: str) -> SiteVisit | None:
    visit = await session.get(SiteVisit, visit_id)
    if not visit:
        return None
    visit.status = "cancelled"
    await session.commit()
    await session.refresh(visit)
    return visit
