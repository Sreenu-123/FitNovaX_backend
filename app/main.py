import hashlib
import secrets
import uuid

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserAccount, UserProfile
from app.schemas import (
    UserLogin,
    UserProfileCreate,
    UserSignup,
)


app = FastAPI()


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100000,
    )

    return f"{salt.hex()}:{password_hash.hex()}"


# ============================================================
# PASSWORD VERIFICATION
# ============================================================

def verify_password(
    password: str,
    stored_password: str,
) -> bool:
    salt_hex, stored_hash_hex = stored_password.split(":")

    salt = bytes.fromhex(salt_hex)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100000,
    )

    return password_hash.hex() == stored_hash_hex


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "FitNovaX Backend is running"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


# ============================================================
# SIGN UP
# ============================================================

@app.post("/auth/signup", status_code=201)
def signup(
    user: UserSignup,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(UserAccount)
        .filter(
            UserAccount.email == user.email.lower()
        )
        .first()
    )

    if existing_user:
        return {
            "message": "An account with this email already exists.",
            "user_id": None,
        }

    new_user_id = str(uuid.uuid4())

    new_user = UserAccount(
        user_id=new_user_id,
        name=user.name,
        email=user.email.lower(),
        phone=user.phone,
        country_code=user.country_code,
        password_hash=hash_password(user.password),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Account created successfully.",
        "user_id": new_user.user_id,
    }


# ============================================================
# LOGIN
# ============================================================

@app.post("/auth/login")
def login(
    user: UserLogin,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(UserAccount)
        .filter(
            UserAccount.email == user.email.lower()
        )
        .first()
    )

    if not existing_user:
        return {
            "success": False,
            "message": "Invalid email or password.",
        }

    if not verify_password(
        user.password,
        existing_user.password_hash,
    ):
        return {
            "success": False,
            "message": "Invalid email or password.",
        }

    return {
        "success": True,
        "message": "Login successful.",
        "user_id": existing_user.user_id,
        "name": existing_user.name,
        "email": existing_user.email,
    }


# ============================================================
# CREATE USER PROFILE
# ============================================================

@app.post("/users")
def create_user(
    user: UserProfileCreate,
    db: Session = Depends(get_db),
):
    new_user = UserProfile(
        user_id=user.user_id,
        name=user.name,
        age=user.age,
        date_of_birth=user.date_of_birth,
        gender=user.gender,
        phone=user.phone,
        country_code=user.country_code,
        height=user.height,
        weight=user.weight,
        profile_image=user.profile_image,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User profile created successfully",
        "user_id": new_user.user_id,
        "name": new_user.name,
    }