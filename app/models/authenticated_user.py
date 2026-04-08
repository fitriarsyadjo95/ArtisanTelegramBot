from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuthenticatedUser(Base):
    __tablename__ = "authenticated_users"

    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True
    )
