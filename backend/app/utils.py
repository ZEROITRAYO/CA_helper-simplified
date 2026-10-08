"""Helpers every feature uses: errors, reading request fields, access control, email,
passwords, GSTIN checks, amounts and the upload checks.
"""

import json
import logging
import smtplib
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from email.message import EmailMessage
from functools import wraps
from http import HTTPStatus
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from flask import current_app, render_template, request
from flask_jwt_extended import get_current_user, verify_jwt_in_request
from sqlalchemy import select
from werkzeug.exceptions import HTTPException

from app.models import Business, db, UserRole

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
log = logging.getLogger(__name__)


# --- errors ------------------------------------------------------------------------


class ApiError(Exception):
    """An expected error with a specific HTTP status and error code."""

    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def error_body(code, message, details=None):
    """Build the standard error payload."""
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


def register_error_handlers(app):
    """Answer every error in the standard JSON shape."""

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return error_body(error.code, error.message, error.details), error.status

    # 404, 405, 413, ... and 500 (an unexpected exception arrives as InternalServerError,
    # whose text is generic, so the exception's own text never reaches the client).
    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        status = error.code or 500
        return error_body(HTTPStatus(status).name, error.description), status


# --- reading request fields --------------------------------------------------------
# Each reader returns the value or raises 422 VALIDATION_ERROR for the first bad field,
# with details {location: {field: [message]}}.

# The message of a required field that was not sent.
MISSING = "Missing data for required field."


def invalid(field, message, location="json"):
    return ApiError(422, "VALIDATION_ERROR", message, {location: {field: [message]}})


def json_body():
    """The request's JSON object ({} when the body is empty or not a JSON object)."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def read_text(data, field, max_length, required=True, location="json"):
    """A text up to `max_length` characters, stripped; None when optional and not sent."""
    value = data.get(field)
    if value is None and not required:
        return None
    if value is None:
        raise invalid(field, MISSING, location)
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise invalid(field, f"Length must be between 1 and {max_length}.", location)
    return value.strip()


def read_bool(data, field, default=None):
    """True or False; `default` when not sent (None = required)."""
    value = data.get(field, default)
    if value is None:
        raise invalid(field, MISSING)
    if not isinstance(value, bool):
        raise invalid(field, "Not a valid boolean.")
    return value


def read_int(data, field, lowest, highest):
    value = data.get(field)
    if value is None:
        raise invalid(field, MISSING)
    if isinstance(value, bool) or not isinstance(value, int) or not lowest <= value <= highest:
        raise invalid(field, f"Enter a whole number from {lowest} to {highest}.")
    return value


def read_amount(value, lowest, highest):
    """A rupee amount with 2 decimals between `lowest` and `highest`, or None if it is not one."""
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    if isinstance(value, bool) or value is None or not lowest <= amount <= highest:
        return None
    return amount


def read_choice(data, field, choices, required=True, location="json"):
    value = data.get(field)
    if value is None and not required:
        return None
    if value is None:
        raise invalid(field, MISSING, location)
    if value not in list(choices):
        raise invalid(field, f"Must be one of: {', '.join(choices)}.", location)
    return value


def read_uuid(value):
    """A UUID from a request value (text), or None when it is not one."""
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError, AttributeError):
        return None


def read_id(data, field, required=True, location="json"):
    """A UUID field; None when optional and not sent."""
    value = data.get(field)
    if value is None and not required:
        return None
    if read_uuid(value) is None:
        raise invalid(field, MISSING if value is None else "Not a valid UUID.", location)
    return read_uuid(value)


def page_args():
    """?page= (from 1) and ?page_size= (1 to 100, default 20)."""
    try:
        page = max(int(request.args.get("page", 1)), 1)
        return page, min(max(int(request.args.get("page_size", 20)), 1), 100)
    except ValueError:
        raise invalid("page", "Not a valid integer.", "query")


def page_of(stmt, to_dict):
    """One page of `stmt` as {items, page, page_size, total}."""
    page, page_size = page_args()
    result = db.paginate(stmt, page=page, per_page=page_size, error_out=False)
    items = [to_dict(item) for item in result.items]
    return {"items": items, "page": page, "page_size": page_size, "total": result.total}


def iso(value):
    """A date or datetime as ISO text for JSON, e.g. "2026-10-13" (None stays None)."""
    return value.isoformat() if value is not None else None


def money(value):
    """An amount as text with 2 decimals, e.g. "1250.00" (None stays None)."""
    return None if value is None else f"{Decimal(value).quantize(Decimal('0.01')):f}"


def format_inr(amount):
    """Indian digit grouping, e.g. 4500000 -> "₹45,00,000"."""
    digits = str(int(Decimal(amount).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
    head, groups = digits[:-3], [digits[-3:]]
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return "₹" + ",".join(groups)


# --- passwords ---------------------------------------------------------------------------

_hasher = PasswordHasher()


def hash_password(password):
    return _hasher.hash(password)


def verify_password(password_hash, password):
    """True if `password` matches the stored hash. Never raises for a wrong password."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# --- email -------------------------------------------------------------------------

# Messages "sent" while MAIL_SUPPRESS_SEND is on (tests read and clear this list).
outbox = []


def send_email(to, subject, template, **context):
    """Send one plain-text email (the text is templates/email/<template>.txt). Returns True
    if it was handed to the SMTP server."""
    config = current_app.config
    message = EmailMessage()
    message["From"] = config["MAIL_DEFAULT_SENDER"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(render_template(f"email/{template}.txt", **context))
    if config["MAIL_SUPPRESS_SEND"]:
        outbox.append(message)
        return True
    try:
        with smtplib.SMTP(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=10) as smtp:
            smtp.send_message(message)
        return True
    except OSError as error:  # smtplib's errors are OSErrors too
        # Only the error type: its text can contain the recipient's address (PII).
        log.error("Could not send the %s email: %s", template, type(error).__name__)
        return False


# --- access control --------------------------------------------------------------------------


def current_user():
    """The logged-in, active user of this request. Call only behind @roles_required."""
    return get_current_user()


def current_business(required=True):
    """The logged-in owner's business. 404 BUSINESS_NOT_FOUND before registration."""
    business = db.session.scalar(select(Business).where(Business.user_id == current_user().id))
    if business is None and required:
        raise ApiError(404, "BUSINESS_NOT_FOUND", "Register your business first.")
    return business


def roles_required(*roles):
    """Allow the endpoint only for logged-in users with one of `roles`."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            # Raises for a missing/bad token; loads the user and rejects inactive ones.
            verify_jwt_in_request()
            if current_user().role not in roles:
                raise ApiError(403, "FORBIDDEN", "You do not have access to this page.")
            return view(*args, **kwargs)

        return wrapper

    return decorator


login_required = roles_required(*UserRole)  # any logged-in user


# --- gstin -------------------------------------------------------------------------------

GST_STATES = json.loads((REPO_ROOT / "content/reference/gst_states.json").read_text())["states"]
_CHARACTERS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def state_code(name):
    """The GST code of a state or union territory, e.g. "27" for Maharashtra."""
    for state in GST_STATES:
        if state["name"] == name:
            return state["code"]
    return None


def gstin_check_character(first_14):
    """The 15th character of a GSTIN: every character's value (0-9, A-Z = 0-35) is
    multiplied by 1 and 2 in turn; the digits of each product in base 36 are added up;
    the check character makes the total a multiple of 36."""
    total = 0
    for index, character in enumerate(first_14):
        product = _CHARACTERS.index(character) * (1 if index % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _CHARACTERS[(36 - total % 36) % 36]


def gstin_error(gstin, pan, state):
    """What is wrong with a (well-formed) GSTIN for this PAN and state, or None."""
    if gstin_check_character(gstin[:14]) != gstin[14]:
        return "This GSTIN is not valid: its last character does not match. Check for a typo."
    code = state_code(state)
    if code is not None and gstin[:2] != code:
        return f"This GSTIN starts with {gstin[:2]}, but the code of {state} is {code}."
    if pan and gstin[2:12] != pan:
        return "The PAN inside this GSTIN (characters 3 to 12) does not match your PAN."
    return None


# --- storage -----------------------------------------------------------------------------

# Allowed file types and the bytes every such file starts with.
ALLOWED_TYPES = {
    "application/pdf": b"%PDF-",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


def read_upload(field="file"):
    """The uploaded file's bytes. 422 when missing; 400 FILE_EMPTY, FILE_TYPE_NOT_ALLOWED
    or FILE_TOO_LARGE."""
    upload = request.files.get(field)
    if upload is None:
        raise invalid(field, MISSING, "files")
    data = upload.read()
    max_mb = current_app.config["MAX_UPLOAD_MB"]
    if not data:
        raise ApiError(400, "FILE_EMPTY", "The file is empty.")
    start = ALLOWED_TYPES.get(upload.mimetype)
    if start is None or not data.startswith(start):
        raise ApiError(400, "FILE_TYPE_NOT_ALLOWED", "Upload a PDF, JPG or PNG file.")
    if len(data) > max_mb * 1024 * 1024:
        raise ApiError(400, "FILE_TOO_LARGE", f"The file is larger than {max_mb} MB.")
    return upload, data
