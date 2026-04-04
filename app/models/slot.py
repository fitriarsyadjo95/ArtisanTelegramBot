from datetime import date, time

from sqlalchemy import Date, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (
        UniqueConstraint("date", "start_time", "end_time", name="uq_slot_datetime"),
    )

    date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    max_visits: Mapped[int] = mapped_column(Integer, default=1)

    site_visits = relationship("SiteVisit", back_populates="slot", lazy="selectin")

    @property
    def is_fully_booked(self) -> bool:
        active = [v for v in self.site_visits if v.status != "cancelled"]
        return len(active) >= self.max_visits

    def __repr__(self) -> str:
        return f"<Slot {self.date} {self.start_time}-{self.end_time}>"
