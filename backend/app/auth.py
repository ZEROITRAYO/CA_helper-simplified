"""Accounts: signup with an emailed code, login, passwords and the email switch."""

import re
import secrets
from datetime import timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token
from sqlalchemy import select

from app.models import EmailOtp, OtpPurpose, User, UserRole, db, utcnow
from app.utils import (
    ApiError, current_user, hash_password, invalid, json_body, login_required, read_bool,
    read_text, roles_required, send_email, verify_password,
)

bp = Blueprint("auth", __name__)

# A code works once, for this long (minutes), and only the newest code of a user counts.
CODE_MINUTES = 10

# The password rule. The frontend checks the same rule (frontend/src/lib/passwords.js).
PASSWORD_RULE_TEXT = "Use 8 to 128 characters, with at least one letter and one number."
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Subject and template of each code email.
CODE_EMAILS = {
    OtpPurpose.VERIFY_EMAIL: ("Your CA Helper verification code", "verify_email"),
    OtpPurpose.RESET_PASSWORD: ("Your CA Helper password reset code", "reset_password"),
}


def normalize_email(email):
    """Emails are stored and compared trimmed and lowercased."""
    return email.strip().lower()


def user_to_dict(user):
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role}


def issue_access_token(user):
    """A JWT: `sub` = the user's id, `role` = business | ca | admin."""
    return create_access_token(identity=str(user.id), additional_claims={"role": user.role})


def find_user(data):
    """The user with the request's `email` (any text up to 254 characters), or None."""
    email = read_text(data, "email", 254)
    return db.session.scalar(select(User).where(User.email == normalize_email(email)))


def read_new_password(data, field):
    """Every password we store must follow the rule (signup, reset, change)."""
    password = data.get(field)
    if not (
        isinstance(password, str) and 8 <= len(password) <= 128  # 128: a huge one ties up argon2
        and re.search(r"[A-Za-z]", password) and re.search(r"[0-9]", password)
    ):
        raise invalid(field, PASSWORD_RULE_TEXT)
    return password


def send_code(user, purpose):
    """Add a new code for the user (only its hash is stored), commit and email it."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.session.add(EmailOtp(user=user, purpose=purpose, code_hash=hash_password(code),
                            expires_at=utcnow() + timedelta(minutes=CODE_MINUTES)))
    db.session.commit()
    subject, template = CODE_EMAILS[purpose]
    send_email(user.email, subject, template, name=user.full_name, code=code, minutes=CODE_MINUTES)


def use_code(user, purpose, data):
    """Use the user's newest `purpose` code. 400 OTP_INVALID or OTP_EXPIRED."""
    code = data.get("code")
    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
        raise invalid("code", "Enter the 6-digit code.")
    otp = None
    if user is not None:
        otp = db.session.scalar(
            select(EmailOtp).where(EmailOtp.user_id == user.id, EmailOtp.purpose == purpose)
            .order_by(EmailOtp.created_at.desc()).limit(1)
        )
    if otp is None or otp.used_at is not None or not verify_password(otp.code_hash, code):
        raise ApiError(400, "OTP_INVALID", "This code is not valid. Check it or ask for a new one.")
    if otp.expires_at <= utcnow():
        raise ApiError(400, "OTP_EXPIRED", "This code has expired. Ask for a new one.")
    otp.used_at = utcnow()


def set_password(user, password):
    """Save a new password and tell the owner, so a change they did not make is noticed."""
    user.password_hash = hash_password(password)
    db.session.commit()
    send_email(user.email, "Your CA Helper password was changed", "password_changed",
               name=user.full_name)


# --- Routes ------------------------------------------------------------------------------


@bp.post("/auth/signup")
def signup():
    """Create a business or CA account; it can log in once its email is verified."""
    data = json_body()
    full_name = read_text(data, "full_name", 200)
    email = data.get("email")
    if not isinstance(email, str) or len(email) > 254 or not EMAIL_PATTERN.match(email):
        raise invalid("email", "Not a valid email address.")
    password = read_new_password(data, "password")
    if data.get("role") not in (UserRole.BUSINESS, UserRole.CA):  # admins never sign up
        raise invalid("role", "Choose business or ca.")
    if data.get("terms_accepted") is not True:
        raise invalid("terms_accepted", "Agree to the Terms and Privacy Policy to sign up.")
    if find_user(data):
        raise ApiError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    user = User(email=normalize_email(email), password_hash=hash_password(password),
                full_name=full_name, role=data["role"], terms_accepted_at=utcnow())
    db.session.add(user)
    send_code(user, OtpPurpose.VERIFY_EMAIL)
    return jsonify(user_to_dict(user)), 201


@bp.post("/auth/verify-email")
def verify_email():
    """Verify the email with the 6-digit code sent at signup."""
    data = json_body()
    user = find_user(data)
    if user is not None and user.email_verified_at is not None:
        raise ApiError(409, "EMAIL_ALREADY_VERIFIED", "This email is already verified. Log in.")
    use_code(user, OtpPurpose.VERIFY_EMAIL, data)
    user.email_verified_at = utcnow()
    db.session.commit()
    return "", 204


def existing_user():
    """The user with the request's email. 404 USER_NOT_FOUND."""
    user = find_user(json_body())
    if user is None:
        raise ApiError(404, "USER_NOT_FOUND", "No account uses this email.")
    return user


@bp.post("/auth/verify-email/resend")
def resend_verification_code():
    """Email a new verification code; it replaces the old one."""
    user = existing_user()
    if user.email_verified_at is not None:
        raise ApiError(409, "EMAIL_ALREADY_VERIFIED", "This email is already verified. Log in.")
    send_code(user, OtpPurpose.VERIFY_EMAIL)
    return "", 204


@bp.post("/auth/forgot-password")
def forgot_password():
    """Email a password reset code (unverified accounts too)."""
    send_code(existing_user(), OtpPurpose.RESET_PASSWORD)
    return "", 204


@bp.post("/auth/login")
def login():
    data = json_body()
    user = find_user(data)
    password = read_text(data, "password", 128)
    if user is None or not verify_password(user.password_hash, password):
        raise ApiError(401, "INVALID_CREDENTIALS", "Wrong email or password.")
    if user.email_verified_at is None:
        raise ApiError(403, "EMAIL_NOT_VERIFIED", "Verify your email before logging in.")
    return jsonify({"access_token": issue_access_token(user), "user": user_to_dict(user)})


@bp.post("/auth/reset-password")
def reset_password():
    """Set a new password with the emailed code (which also verifies the email)."""
    data = json_body()
    user = find_user(data)
    new_password = read_new_password(data, "new_password")
    use_code(user, OtpPurpose.RESET_PASSWORD, data)
    user.email_verified_at = user.email_verified_at or utcnow()
    set_password(user, new_password)
    return "", 204


@bp.post("/auth/change-password")
@login_required
def change_password():
    """Change the password; a wrong current one is 400, not 401 (401 logs out)."""
    data = json_body()
    current_password = read_text(data, "current_password", 128)
    new_password = read_new_password(data, "new_password")
    user = current_user()
    if not verify_password(user.password_hash, current_password):
        raise ApiError(400, "WRONG_PASSWORD", "Your current password is wrong.")
    if new_password == current_password:
        raise ApiError(400, "SAME_PASSWORD", "Choose a password different from your current one.")
    set_password(user, new_password)
    return "", 204


@bp.get("/auth/me")
@login_required
def me():
    return jsonify(user_to_dict(current_user()))


@bp.route("/auth/settings", methods=["GET", "PUT"])
@roles_required(UserRole.BUSINESS, UserRole.CA)
def settings():
    """The notification email switch; PUT turns it on or off. Emails with a code always go out."""
    user = current_user()
    if request.method == "PUT":
        user.email_notifications = read_bool(json_body(), "email_notifications")
        db.session.commit()
    return jsonify({"email_notifications": user.email_notifications})
