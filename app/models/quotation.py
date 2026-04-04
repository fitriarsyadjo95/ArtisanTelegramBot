from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Quotation(Base):
    __tablename__ = "quotations"

    quotation_number: Mapped[str] = mapped_column(String(30), unique=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"))
    job_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_area_sqft: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer = relationship("Customer", back_populates="quotations")
    line_items = relationship(
        "LineItem", back_populates="quotation", lazy="selectin", cascade="all, delete-orphan"
    )
    invoice = relationship("Invoice", back_populates="quotation", uselist=False)

    def __repr__(self) -> str:
        return f"<Quotation {self.quotation_number} - RM{self.total_amount}>"
