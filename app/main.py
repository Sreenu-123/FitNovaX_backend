from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserProfile
from app.schemas import UserProfileCreate

app = FastAPI()


@app.get("/")
def root():
    return {"message": "FitNovaX Backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/users")
def create_user(
    user: UserProfileCreate,
    db: Session = Depends(get_db),
):
    new_user = UserProfile(
        user_id=user.user_id,
        name=user.name,
        age=user.age,
        gender=user.gender,
        height=user.height,
        weight=user.weight,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User profile created successfully",
        "user_id": new_user.user_id,
        "name": new_user.name,
    }