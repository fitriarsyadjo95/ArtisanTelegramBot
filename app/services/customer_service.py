from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


async def create_customer(
    session: AsyncSession,
    name: str,
    phone: str,
    address: str | None = None,
    email: str | None = None,
    notes: str | None = None,
) -> Customer:
    customer = Customer(
        name=name, phone=phone, address=address, email=email, notes=notes
    )
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return customer


async def get_customer(session: AsyncSession, customer_id: str) -> Customer | None:
    return await session.get(Customer, customer_id)


async def search_customers(session: AsyncSession, query: str) -> list[Customer]:
    stmt = select(Customer).where(
        Customer.name.ilike(f"%{query}%") | Customer.phone.ilike(f"%{query}%")
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_customers(
    session: AsyncSession, limit: int = 20, offset: int = 0
) -> list[Customer]:
    stmt = select(Customer).order_by(Customer.name).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_customer(
    session: AsyncSession, customer_id: str, **kwargs
) -> Customer | None:
    customer = await session.get(Customer, customer_id)
    if not customer:
        return None
    for key, value in kwargs.items():
        if hasattr(customer, key):
            setattr(customer, key, value)
    await session.commit()
    await session.refresh(customer)
    return customer


async def count_customers(session: AsyncSession) -> int:
    stmt = select(Customer)
    result = await session.execute(stmt)
    return len(result.scalars().all())
