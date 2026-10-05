from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.sql import func

from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(String, unique=True, nullable=False, index=True)

    name = Column(String, nullable=False)

    age = Column(Integer, nullable=True)

    gender = Column(String, nullable=True)

    height = Column(Float, nullable=True)

    weight = Column(Float, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )