from sqlalchemy import Column, String, Integer, Float, Date, DateTime
from sqlalchemy.sql import func

from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    age = Column(
        Integer,
        nullable=True,
    )

    date_of_birth = Column(
        Date,
        nullable=True,
    )

    gender = Column(
        String,
        nullable=True,
    )

    phone = Column(
        String,
        nullable=True,
    )

    country_code = Column(
        String,
        nullable=True,
    )

    height = Column(
        Float,
        nullable=True,
    )

    weight = Column(
        Float,
        nullable=True,
    )

    profile_image = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    email = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    phone = Column(
        String,
        nullable=True,
    )

    country_code = Column(
        String,
        nullable=True,
    )

    password_hash = Column(
        String,
        nullable=False,
    )

    reset_token = Column(
        String,
        nullable=True,
        unique=True,
        index=True,
    )

    reset_token_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )