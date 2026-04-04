from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Pattern(Base):
    __tablename__ = "patterns"

    name: Mapped[str] = mapped_column(String(100))
    rate_per_sqft: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    pricing_type: Mapped[str] = mapped_column(String(20), default="per_sqft")  # per_sqft or lumpsum
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        if self.pricing_type == "lumpsum":
            return f"<Pattern {self.name} (lumpsum)>"
        return f"<Pattern {self.name} @ RM{self.rate_per_sqft}/sqft>"
