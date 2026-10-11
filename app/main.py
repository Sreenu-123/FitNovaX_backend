import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import resend
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserAccount, UserProfile
from app.schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserLogin,
    UserProfileCreate,
    UserProfileUpdate,
    UserSignup,
)

app = FastAPI(title="FitNovaX API")

resend.api_key = os.getenv("RESEND_API_KEY")


# ============================================================
# PASSWORD HELPERS
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


def verify_password(
    password: str,
    stored_password: str,
) -> bool:
    try:
        salt_hex, stored_hash_hex = stored_password.split(":")
        salt = bytes.fromhex(salt_hex)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000,
        )

        return secrets.compare_digest(
            password_hash.hex(),
            stored_hash_hex,
        )
    except (ValueError, TypeError):
        return False


def find_account(db: Session, user_id: str):
    return (
        db.query(UserAccount)
        .filter(UserAccount.user_id == user_id)
        .first()
    )


def profile_response(profile: UserProfile, email: str):
    return {
        "exists": True,
        "user_id": profile.user_id,
        "name": profile.name,
        "email": email,
        "age": profile.age,
        "date_of_birth": (
            profile.date_of_birth.isoformat()
            if profile.date_of_birth
            else None
        ),
        "gender": profile.gender,
        "phone": profile.phone,
        "country_code": profile.country_code,
        "height": profile.height,
        "weight": profile.weight,
        "profile_image": profile.profile_image,
    }


# ============================================================
# ROOT AND HEALTH
# ============================================================

@app.get("/")
def root():
    return {"message": "FitNovaX Backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


# ============================================================
# SIGN UP
# ============================================================

@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(
    user: UserSignup,
    db: Session = Depends(get_db),
):
    email = user.email.lower().strip()

    existing_user = (
        db.query(UserAccount)
        .filter(UserAccount.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    new_user = UserAccount(
        user_id=str(uuid.uuid4()),
        name=user.name.strip(),
        email=email,
        phone=user.phone,
        country_code=user.country_code,
        password_hash=hash_password(user.password),
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "message": "Account created successfully.",
        "user_id": new_user.user_id,
        "name": new_user.name,
        "email": new_user.email,
    }


# ============================================================
# LOGIN
# ============================================================

@app.post("/auth/login")
def login(
    user: UserLogin,
    db: Session = Depends(get_db),
):
    email = user.email.lower().strip()

    existing_user = (
        db.query(UserAccount)
        .filter(UserAccount.email == email)
        .first()
    )

    if (
        not existing_user
        or not verify_password(
            user.password,
            existing_user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return {
        "success": True,
        "message": "Login successful.",
        "user_id": existing_user.user_id,
        "name": existing_user.name,
        "email": existing_user.email,
    }


# ============================================================
# FORGOT PASSWORD
# ============================================================

@app.post("/auth/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    email = request.email.lower().strip()

    existing_user = (
        db.query(UserAccount)
        .filter(UserAccount.email == email)
        .first()
    )

    if not existing_user:
        # Avoid revealing whether an email is registered.
        return {
            "success": True,
            "message": "If the account exists, a reset email will be sent.",
        }

    reset_token = secrets.token_urlsafe(32)

    existing_user.reset_token = reset_token
    existing_user.reset_token_expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=15)
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Configure this URL to match the reset link your app supports.
    reset_link = (
        f"https://fitnovax.com/reset-password?token={reset_token}"
    )

    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": [existing_user.email],
            "subject": "Reset your FitNovaX password",
            "html": f"""
                <div style="font-family: Arial, sans-serif;">
                    <h2>FitNovaX Password Reset</h2>
                    <p>Use the link below to reset your password.</p>
                    <p>
                        <a href="{reset_link}">
                            Reset Password
                        </a>
                    </p>
                    <p>This link expires in 15 minutes.</p>
                </div>
            """,
        })
    except Exception:
        # Do not return the reset token to the client.
        print("Failed to send password reset email.")
        return {
            "success": False,
            "message": "Failed to send password reset email.",
        }

    return {
        "success": True,
        "message": "Password reset email sent successfully.",
    }


# ============================================================
# RESET PASSWORD
# ============================================================

@app.post("/auth/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    token = request.token.strip()

    existing_user = (
        db.query(UserAccount)
        .filter(UserAccount.reset_token == token)
        .first()
    )

    if not existing_user or not existing_user.reset_token_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    expires_at = existing_user.reset_token_expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    new_password = request.new_password

    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )

    existing_user.password_hash = hash_password(new_password)
    existing_user.reset_token = None
    existing_user.reset_token_expires_at = None

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "message": "Password reset successfully.",
    }


# ============================================================
# CREATE OR SAVE USER PROFILE
# ============================================================

@app.post("/users")
def create_user_profile(
    user: UserProfileCreate,
    db: Session = Depends(get_db),
):
    account = find_account(db, user.user_id)

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user.user_id)
        .first()
    )

    profile_data = user.model_dump(exclude={"user_id"})

    if profile:
        for field, value in profile_data.items():
            setattr(profile, field, value)
    else:
        profile = UserProfile(
            user_id=user.user_id,
            **profile_data,
        )
        db.add(profile)

    if user.name:
        account.name = user.name

    if user.phone is not None:
        account.phone = user.phone

    if user.country_code is not None:
        account.country_code = user.country_code

    try:
        db.commit()
        db.refresh(profile)
    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "message": "User profile saved successfully.",
        "user_id": profile.user_id,
    }


# ============================================================
# GET USER PROFILE
# ============================================================

@app.get("/users/{user_id}")
def get_user_profile(
    user_id: str,
    db: Session = Depends(get_db),
):
    account = find_account(db, user_id)

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id)
        .first()
    )

    if not profile:
        return {
            "exists": False,
            "user_id": account.user_id,
            "name": account.name,
            "email": account.email,
            "age": None,
            "date_of_birth": None,
            "gender": None,
            "phone": account.phone,
            "country_code": account.country_code,
            "height": None,
            "weight": None,
            "profile_image": None,
            "message": "Profile details have not been saved yet.",
        }

    return profile_response(profile, account.email)


# ============================================================
# UPDATE USER PROFILE
# ============================================================

@app.put("/users/{user_id}")
def update_user_profile(
    user_id: str,
    user: UserProfileUpdate,
    db: Session = Depends(get_db),
):
    account = find_account(db, user_id)

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id)
        .first()
    )

    if not profile:
        profile = UserProfile(
            user_id=user_id,
            name=account.name,
        )
        db.add(profile)

    update_data = user.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(profile, field, value)

    if "name" in update_data and update_data["name"] is not None:
        account.name = update_data["name"]

    if "phone" in update_data:
        account.phone = update_data["phone"]

    if "country_code" in update_data:
        account.country_code = update_data["country_code"]

    try:
        db.commit()
        db.refresh(profile)
    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "message": "User profile updated successfully.",
        "user_id": profile.user_id,
        "name": profile.name,
    }