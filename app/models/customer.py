from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Customer(Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    quotations = relationship("Quotation", back_populates="customer", lazy="selectin")
    invoices = relationship("Invoice", back_populates="customer", lazy="selectin")
    site_visits = relationship("SiteVisit", back_populates="customer", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Customer {self.name} ({self.phone})>"
