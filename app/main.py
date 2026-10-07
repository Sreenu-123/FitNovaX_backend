import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import resend
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserAccount, UserProfile
from app.schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserLogin,
    UserProfileCreate,
    UserSignup,
)


app = FastAPI()


# ============================================================
# RESEND CONFIGURATION
# ============================================================

resend.api_key = os.getenv("RESEND_API_KEY")


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
            UserAccount.email == user.email.lower().strip()
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
        email=user.email.lower().strip(),
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
            UserAccount.email == user.email.lower().strip()
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
        .filter(
            UserAccount.email == email
        )
        .first()
    )

    # --------------------------------------------------------
    # ACCOUNT DOES NOT EXIST
    # --------------------------------------------------------

    if not existing_user:
        return {
            "success": False,
            "message": "No account found with this email.",
        }

    # --------------------------------------------------------
    # GENERATE RESET TOKEN
    # --------------------------------------------------------

    reset_token = secrets.token_urlsafe(32)

    reset_token_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=15)
    )

    # --------------------------------------------------------
    # SAVE RESET TOKEN
    # --------------------------------------------------------

    existing_user.reset_token = reset_token
    existing_user.reset_token_expires_at = (
        reset_token_expires_at
    )

    db.commit()
    db.refresh(existing_user)

    # --------------------------------------------------------
    # CREATE RESET LINK
    # --------------------------------------------------------

    reset_link = (
        f"fitnovax://reset-password"
        f"?token={reset_token}"
    )

    # --------------------------------------------------------
    # SEND RESET EMAIL
    # --------------------------------------------------------

    try:
        resend.Emails.send(
            {
                "from": "onboarding@resend.dev",
                "to": [existing_user.email],
                "subject": "Reset your FitNovaX password",
                "html": f"""
                    <div style="font-family: Arial, sans-serif;">

                        <h2>FitNovaX Password Reset</h2>

                        <p>
                            We received a request to reset your
                            FitNovaX password.
                        </p>

                        <p>
                            Click the button below to create
                            a new password.
                        </p>

                        <p>
                            <a
                                href="{reset_link}"
                                style="
                                    display: inline-block;
                                    padding: 12px 20px;
                                    background-color: #2196F3;
                                    color: white;
                                    text-decoration: none;
                                    border-radius: 6px;
                                "
                            >
                                Reset Password
                            </a>
                        </p>

                        <p>
                            This link will expire in 15 minutes.
                        </p>

                        <p>
                            If you did not request a password reset,
                            you can safely ignore this email.
                        </p>

                    </div>
                """,
            }
        )

    except Exception as error:
        print("RESEND ERROR:", error)

        return {
            "success": False,
            "message": "Failed to send password reset email.",
        }

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

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
    # --------------------------------------------------------
    # CLEAN TOKEN
    # --------------------------------------------------------

    token = request.token.strip()

    # --------------------------------------------------------
    # FIND USER USING RESET TOKEN
    # --------------------------------------------------------

    existing_user = (
        db.query(UserAccount)
        .filter(
            UserAccount.reset_token == token
        )
        .first()
    )

    # --------------------------------------------------------
    # INVALID TOKEN
    # --------------------------------------------------------

    if not existing_user:
        return {
            "success": False,
            "message": "Invalid or expired reset token.",
        }

    # --------------------------------------------------------
    # CHECK TOKEN EXISTS
    # --------------------------------------------------------

    if not existing_user.reset_token:
        return {
            "success": False,
            "message": "Invalid or expired reset token.",
        }

    # --------------------------------------------------------
    # CHECK TOKEN EXPIRY
    # --------------------------------------------------------

    expires_at = existing_user.reset_token_expires_at

    if not expires_at:
        return {
            "success": False,
            "message": "Invalid or expired reset token.",
        }

    # PostgreSQL can return timezone-aware or naive datetime
    # depending on configuration, so normalize it safely.

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    current_time = datetime.now(timezone.utc)

    if expires_at <= current_time:
        return {
            "success": False,
            "message": "Invalid or expired reset token.",
        }

    # --------------------------------------------------------
    # VALIDATE NEW PASSWORD
    # --------------------------------------------------------

    new_password = request.new_password.strip()

    if len(new_password) < 8:
        return {
            "success": False,
            "message": "Password must be at least 8 characters long.",
        }

    # --------------------------------------------------------
    # HASH NEW PASSWORD
    # --------------------------------------------------------

    new_password_hash = hash_password(
        new_password
    )

    # --------------------------------------------------------
    # UPDATE PASSWORD
    # --------------------------------------------------------

    existing_user.password_hash = new_password_hash

    # --------------------------------------------------------
    # CLEAR RESET TOKEN
    # --------------------------------------------------------

    existing_user.reset_token = None
    existing_user.reset_token_expires_at = None

    db.commit()
    db.refresh(existing_user)

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    return {
        "success": True,
        "message": "Password reset successfully.",
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


# ============================================================
# GET USER PROFILE
# ============================================================

@app.get("/users/{user_id}")
def get_user_profile(
    user_id: str,
    db: Session = Depends(get_db),
):
    existing_profile = (
        db.query(UserProfile)
        .filter(
            UserProfile.user_id == user_id
        )
        .first()
    )

    # --------------------------------------------------------
    # PROFILE DOES NOT EXIST
    # --------------------------------------------------------

    if not existing_profile:
        return {
            "exists": False,
            "message": "User profile not found.",
        }

    # --------------------------------------------------------
    # PROFILE EXISTS
    # --------------------------------------------------------

    return {
        "exists": True,
        "user_id": existing_profile.user_id,
        "name": existing_profile.name,
        "age": existing_profile.age,
        "date_of_birth": (
            existing_profile.date_of_birth.isoformat()
            if existing_profile.date_of_birth
            else None
        ),
        "gender": existing_profile.gender,
        "phone": existing_profile.phone,
        "country_code": existing_profile.country_code,
        "height": existing_profile.height,
        "weight": existing_profile.weight,
        "profile_image": existing_profile.profile_image,
    }