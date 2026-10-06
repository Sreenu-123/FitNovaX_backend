from datetime import date

from pydantic import BaseModel


class UserSignup(BaseModel):
    name: str
    email: str
    phone: str
    country_code: str
    password: str


class UserProfileCreate(BaseModel):
    user_id: str
    name: str
    age: int | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    phone: str | None = None
    country_code: str | None = None
    height: float | None = None
    weight: float | None = None
    profile_image: str | None = None

class UserLogin(BaseModel):
    email: str
    password: str