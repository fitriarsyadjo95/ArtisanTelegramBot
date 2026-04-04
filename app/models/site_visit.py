from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SiteVisit(Base):
    __tablename__ = "site_visits"

    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"))
    visit_date: Mapped[date] = mapped_column(Date)
    visit_time: Mapped[str] = mapped_column(String(20))  # e.g., "11AM", "2PM"
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # e.g., "LUMSUM 600SQFT"
    google_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    customer = relationship("Customer", back_populates="site_visits")

    def __repr__(self) -> str:
        return f"<SiteVisit {self.visit_date} {self.visit_time} - {self.status}>"
