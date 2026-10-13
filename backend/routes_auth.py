# Accounts: sign up with an emailed 6-digit code, log in, passwords, the email switch and
# the notification inbox.

import re
import secrets
from datetime import timedelta

from flask import jsonify, request
from flask_jwt_extended import create_access_token

from app import app
from helpers import (
    check_password, current_user, error, hash_password, iso, page_of, role_required, send_email,
)
from models import EmailOtp, Notification, User, db, now

ALL_ROLES = ("business", "ca", "admin")
PASSWORD_RULE = "Use 8 to 128 characters, with at least one letter and one number."
CODE_MINUTES = 10  # a code works once, for 10 minutes; only the newest code counts


def user_to_dict(user):
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role}


def find_user(email):
    if not isinstance(email, str):
        return None
    return User.query.filter_by(email=email.strip().lower()).first()


def good_password(password):
    """The same rule as the frontend (frontend/src/lib.js)."""
    return (isinstance(password, str) and 8 <= len(password) <= 128
            and re.search(r"[A-Za-z]", password) and re.search(r"[0-9]", password))


def send_code(user, purpose):
    """Email a new 6-digit code ("verify_email" or "reset_password"); only its hash is stored."""
    code = f"{secrets.randbelow(1000000):06d}"
    db.session.add(EmailOtp(user_id=user.id, purpose=purpose, code_hash=hash_password(code),
                            expires_at=now() + timedelta(minutes=CODE_MINUTES)))
    db.session.commit()
    if purpose == "verify_email":
        subject = "Your CA Helper verification code"
    else:
        subject = "Your CA Helper password reset code"
    send_email(user.email, subject, purpose, name=user.full_name, code=code, minutes=CODE_MINUTES)


def code_problem(user, purpose, code):
    """Use the user's newest code; returns an error answer if it is wrong or too old."""
    otp = None
    if user:
        otp = EmailOtp.query.filter_by(user_id=user.id, purpose=purpose).order_by(EmailOtp.created_at.desc()).first()
    if otp is None or otp.used_at or not isinstance(code, str) or not check_password(otp.code_hash, code):
        return error(400, "OTP_INVALID", "This code is not valid. Check it or ask for a new one.")
    if otp.expires_at <= now():
        return error(400, "OTP_EXPIRED", "This code has expired. Ask for a new one.")
    otp.used_at = now()
    return None


@app.route("/api/v1/auth/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    full_name = str(data.get("full_name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    if not full_name or len(full_name) > 200:
        return error(422, "VALIDATION_ERROR", "Enter your name.")
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return error(422, "VALIDATION_ERROR", "Not a valid email address.")
    if not good_password(data.get("password")):
        return error(422, "VALIDATION_ERROR", PASSWORD_RULE)
    if data.get("role") not in ("business", "ca"):  # admins never sign up
        return error(422, "VALIDATION_ERROR", "Choose business or ca.")
    if data.get("terms_accepted") is not True:
        return error(422, "VALIDATION_ERROR", "Agree to the Terms and Privacy Policy to sign up.")
    if find_user(email):
        return error(409, "EMAIL_TAKEN", "An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(data["password"]), full_name=full_name,
                role=data["role"])
    db.session.add(user)
    db.session.flush()
    send_code(user, "verify_email")
    return jsonify(user_to_dict(user)), 201


@app.route("/api/v1/auth/verify-email", methods=["POST"])
def verify_email():
    data = request.get_json(silent=True) or {}
    user = find_user(data.get("email"))
    if user and user.email_verified:
        return error(409, "EMAIL_ALREADY_VERIFIED", "This email is already verified. Log in.")
    problem = code_problem(user, "verify_email", data.get("code"))
    if problem:
        return problem
    user.email_verified = True
    db.session.commit()
    return "", 204


@app.route("/api/v1/auth/verify-email/resend", methods=["POST"])
def resend_code():
    user = find_user((request.get_json(silent=True) or {}).get("email"))
    if user is None:
        return error(404, "USER_NOT_FOUND", "No account uses this email.")
    if user.email_verified:
        return error(409, "EMAIL_ALREADY_VERIFIED", "This email is already verified. Log in.")
    send_code(user, "verify_email")
    return "", 204


@app.route("/api/v1/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    user = find_user(data.get("email"))
    password = data.get("password")
    if user is None or not isinstance(password, str) or not check_password(user.password_hash, password):
        return error(401, "INVALID_CREDENTIALS", "Wrong email or password.")
    if not user.email_verified:
        return error(403, "EMAIL_NOT_VERIFIED", "Verify your email before logging in.")
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return jsonify({"access_token": token, "user": user_to_dict(user)})


@app.route("/api/v1/auth/forgot-password", methods=["POST"])
def forgot_password():
    user = find_user((request.get_json(silent=True) or {}).get("email"))
    if user is None:
        return error(404, "USER_NOT_FOUND", "No account uses this email.")
    send_code(user, "reset_password")
    return "", 204


def save_new_password(user, password):
    """Save it and tell the owner, so a change they did not make does not go unnoticed."""
    user.password_hash = hash_password(password)
    db.session.commit()
    send_email(user.email, "Your CA Helper password was changed", "password_changed", name=user.full_name)


@app.route("/api/v1/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}
    if not good_password(data.get("new_password")):
        return error(422, "VALIDATION_ERROR", PASSWORD_RULE)
    user = find_user(data.get("email"))
    problem = code_problem(user, "reset_password", data.get("code"))
    if problem:
        return problem
    user.email_verified = True  # the emailed code proves the email too
    save_new_password(user, data["new_password"])
    return "", 204


@app.route("/api/v1/auth/change-password", methods=["POST"])
@role_required(*ALL_ROLES)
def change_password():
    data = request.get_json(silent=True) or {}
    user = current_user()
    if not good_password(data.get("new_password")):
        return error(422, "VALIDATION_ERROR", PASSWORD_RULE)
    # A wrong current password is 400, not 401 (a 401 would log the user out).
    current = data.get("current_password")
    if not isinstance(current, str) or not check_password(user.password_hash, current):
        return error(400, "WRONG_PASSWORD", "Your current password is wrong.")
    if data["new_password"] == data["current_password"]:
        return error(400, "SAME_PASSWORD", "Choose a password different from your current one.")
    save_new_password(user, data["new_password"])
    return "", 204


@app.route("/api/v1/auth/me")
@role_required(*ALL_ROLES)
def me():
    return jsonify(user_to_dict(current_user()))


@app.route("/api/v1/auth/settings", methods=["GET", "PUT"])
@role_required("business", "ca")
def settings():
    """The switch for notification emails (emails with a code always go out)."""
    user = current_user()
    if request.method == "PUT":
        value = (request.get_json(silent=True) or {}).get("email_notifications")
        if not isinstance(value, bool):
            return error(422, "VALIDATION_ERROR", "Send email_notifications as true or false.")
        user.email_notifications = value
        db.session.commit()
    return jsonify({"email_notifications": user.email_notifications})


# --- The notification inbox ---


def notification_to_dict(notification):
    return {"id": str(notification.id), "type": notification.type, "title": notification.title,
            "body": notification.body, "link": notification.link, "read_at": iso(notification.read_at),
            "created_at": iso(notification.created_at)}


@app.route("/api/v1/alerts/notifications")
@role_required(*ALL_ROLES)
def list_notifications():
    """The user's notifications, newest first, a page at a time."""
    query = Notification.query.filter_by(user_id=current_user().id)
    query = query.order_by(Notification.created_at.desc(), Notification.id)
    return jsonify(page_of(query, notification_to_dict))


@app.route("/api/v1/alerts/notifications/<uuid:notification_id>/read", methods=["POST"])
@role_required(*ALL_ROLES)
def mark_read(notification_id):
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user().id:
        return error(404, "NOTIFICATION_NOT_FOUND", "This notification was not found.")
    if notification.read_at is None:
        notification.read_at = now()
    db.session.commit()
    return jsonify(notification_to_dict(notification))
