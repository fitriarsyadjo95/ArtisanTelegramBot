from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LineItem(Base):
    __tablename__ = "line_items"

    quotation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quotations.id", ondelete="CASCADE")
    )
    pattern_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("patterns.id"), nullable=True
    )
    pricing_type: Mapped[str] = mapped_column(String(20), default="per_sqft")  # per_sqft, lumpsum, custom
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # sqft, unit, meter, lot, set, LS
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    # Keep legacy columns for backward compat with existing per_sqft items
    area_sqft: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    rate_per_sqft: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    quotation = relationship("Quotation", back_populates="line_items")
    pattern = relationship("Pattern", lazy="selectin")

    def __repr__(self) -> str:
        return f"<LineItem {self.description} - RM{self.amount}>"
