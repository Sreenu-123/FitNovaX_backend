from pydantic import BaseModel


class UserProfileCreate(BaseModel):
    user_id: str
    name: str
    age: int | None = None
    gender: str | None = None
    height: float | None = None
    weight: float | None = None