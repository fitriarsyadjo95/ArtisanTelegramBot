from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    invoice_number: Mapped[str] = mapped_column(String(20), unique=True)
    quotation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quotations.id"), unique=True
    )
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid")
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    quotation = relationship("Quotation", back_populates="invoice")
    customer = relationship("Customer", back_populates="invoices")

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} - {self.payment_status}>"
