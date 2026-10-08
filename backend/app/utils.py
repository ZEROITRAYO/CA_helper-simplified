"""Helpers every feature uses: errors, access control, email, passwords, GSTIN
checks, amounts, the upload checks and the page shapes of list endpoints.
"""

import json
import logging
import smtplib
import uuid
from decimal import Decimal, ROUND_HALF_UP
from email.message import EmailMessage
from functools import wraps
from http import HTTPStatus
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from flask import current_app, request
from flask_jwt_extended import get_current_user, verify_jwt_in_request
from jinja2 import Template
from sqlalchemy import select
from werkzeug.exceptions import HTTPException

from app.models import Business, db, UserRole


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# --- errors ------------------------------------------------------------------------


class ApiError(Exception):
    """An expected error with a specific HTTP status and error code."""

    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def error_body(code, message, details=None):
    """Build the standard error payload."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


def default_code(status):
    """Default error code for an HTTP status, e.g. 404 -> "NOT_FOUND"."""
    if status == 422:
        return "VALIDATION_ERROR"
    try:
        return HTTPStatus(status).name
    except ValueError:
        return "ERROR"


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
        return error_body(default_code(status), error.description or HTTPStatus(status).phrase), status


# The message of a required field that was not sent.
MISSING = "Missing data for required field."


def json_body():
    """The request's JSON object ({} when the body is empty or not a JSON object)."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def validation_error(errors, location="json"):
    """The 422 answer for invalid fields: details {location: {field: [message]}}."""
    return ApiError(422, "VALIDATION_ERROR", "Some fields are invalid.", {location: errors})


PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


def read_page_args(errors):
    """?page= and ?page_size= (1 to 100, default 20); errors go into `errors`."""
    numbers = {}
    for name, default, largest in (("page", 1, None), ("page_size", PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX)):
        text = request.args.get(name)
        numbers[name] = default
        if text is None:
            continue
        try:
            value = int(text)
        except ValueError:
            errors[name] = ["Not a valid integer."]
            continue
        if largest is None and value < 1:
            errors[name] = ["Must be greater than or equal to 1."]
        elif largest is not None and not 1 <= value <= largest:
            errors[name] = [f"Must be greater than or equal to 1 and less than or equal to {largest}."]
        numbers[name] = value
    return numbers["page"], numbers["page_size"]


def read_uuid(value):
    """A UUID from a request value (text), or None when it is not one."""
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def iso(value):
    """A date or datetime as ISO text for JSON, e.g. "2026-10-13" (None stays None)."""
    return value.isoformat() if value is not None else None


def money(value):
    """An amount as text with 2 decimals, e.g. "1250.00" (None stays None)."""
    if value is None:
        return None
    return f"{Decimal(value).quantize(Decimal('0.01')):f}"


# --- pagination --------------------------------------------------------------------------


PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


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


log = logging.getLogger(__name__)

# Messages "sent" while MAIL_SUPPRESS_SEND is on (tests read and clear this list).
outbox: list[EmailMessage] = []

# The text of every email, rendered with Jinja (plain text, no HTML escaping).
EMAIL_TEMPLATES = {
    "ca_rejected": """Hello {{ name }},

We could not verify your CA Helper profile. The reason:

    {{ reason }}

Correct your profile (or upload your Certificate of Practice again) and save it:
it then goes back to the admin for another check.

CA Helper
""",
    "ca_verified": """Hello {{ name }},

Your CA Helper profile is verified. Businesses can now find you under "Find a CA"
and send you requests.

CA Helper
""",
    "engagement_accepted": """Hello {{ owner_name }},

Good news: {{ ca_name }} has accepted your request at their listed prices.
The filings in it are now marked "With CA".

You can see the details in "My engagements" in CA Helper.

CA Helper
""",
    "engagement_declined": """Hello {{ owner_name }},

{{ ca_name }} has declined your request. The filings in it are free again, so you
can request another CA from "Find a CA" in CA Helper.

CA Helper
""",
    "engagement_requested": """Hello {{ ca_name }},

{{ business_name }} has sent you a request for {{ filing_count }} filing{{ "s" if filing_count != 1 }}.

Open "My engagements" in CA Helper to accept it at your listed prices or decline
it.

CA Helper
""",
    "notification": """Hello {{ name }},

{{ title }}

{{ body }}

You can also read it in CA Helper under "Notification settings",
where you can choose which emails you get.

CA Helper
""",
    "password_changed": """Hello {{ name }},

The password of your CA Helper account was just changed.

If this was you, there is nothing to do. If it was not, reset your password at once with
"Forgot password?" on the login page.

CA Helper
""",
    "reminders": """Hello {{ name }},

{% if lines|length == 1 %}One filing needs your attention:{% else %}{{ lines|length }} filings need your attention:{% endif %}
{% for line in lines %}
  - {{ line }}
{%- endfor %}

Open CA Helper to see each filing (your inbox under "Notification settings" lists them too).
To change which emails you get, open "Notification settings".

CA Helper
""",
    "reset_password": """Hello {{ name }},

Someone asked to reset the password of your CA Helper account. Your code is:

    {{ code }}

It expires in {{ minutes }} minutes. Enter it on the "Reset your password" page.

If this was not you, ignore this email: your password stays the same.

CA Helper
""",
    "verify_email": """Hello {{ name }},

Welcome to CA Helper. Your email verification code is:

    {{ code }}

It expires in {{ minutes }} minutes. Enter it on the "Verify your email" page to finish signing up.

If you did not create a CA Helper account, you can ignore this email.

CA Helper
""",
}


def send_email(to, subject, template, **context):
    """Send one plain-text email. Returns True if it was handed to the SMTP server."""
    config = current_app.config
    message = EmailMessage()
    message["From"] = config["MAIL_DEFAULT_SENDER"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(Template(EMAIL_TEMPLATES[template]).render(**context))

    if config["MAIL_SUPPRESS_SEND"]:
        outbox.append(message)
        return True
    try:
        with smtplib.SMTP(config["MAIL_SERVER"], config["MAIL_PORT"], timeout=10) as smtp:
            smtp.send_message(message)
    except OSError as error:  # smtplib's errors are OSErrors too
        # Only the error type: its text can contain the recipient's address (PII).
        log.error("Could not send the %s email: %s", template, type(error).__name__)
        return False
    return True


# --- access control --------------------------------------------------------------------------


def current_user():
    """The logged-in, active user of this request. Call only behind @roles_required."""
    return get_current_user()


def current_business_or_none():
    """The logged-in business user's registered business, or None before registration."""
    return db.session.scalar(
        select(Business).where(Business.user_id == current_user().id)
    )


def current_business():
    """The logged-in owner's business. 404 BUSINESS_NOT_FOUND before registration."""
    business = current_business_or_none()
    if business is None:
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


def login_required(view):
    """Allow the endpoint for any logged-in, active user (every role)."""
    return roles_required(*UserRole)(view)


def require_ca_access(business_id):
    """404 BUSINESS_NOT_FOUND unless the CA has an active engagement with it."""
    from app import marketplace  # imported here: marketplace imports this module

    ca_profile_id = marketplace.own_profile_id(current_user())
    if ca_profile_id is None or not marketplace.ca_can_see_business(
        ca_profile_id, business_id
    ):
        raise ApiError(404, "BUSINESS_NOT_FOUND", "This business was not found.")


# --- gstin -------------------------------------------------------------------------------


_STATES_FILE = REPO_ROOT / "content" / "reference" / "gst_states.json"
GST_STATES = json.loads(_STATES_FILE.read_text())["states"]
_CODE_OF = {state["name"]: state["code"] for state in GST_STATES}

_CHARACTERS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def state_code(name):
    """The GST code of a state or union territory, e.g. "27" for Maharashtra."""
    return _CODE_OF.get(name)


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


# --- money -------------------------------------------------------------------------------


def format_inr(amount):
    digits = str(int(Decimal(amount).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail])


# --- storage -----------------------------------------------------------------------------


# Allowed file types and the bytes every such file starts with.
ALLOWED_TYPES = {
    "application/pdf": b"%PDF-",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


def check_file(data, mime_type):
    """400 FILE_EMPTY, FILE_TYPE_NOT_ALLOWED or FILE_TOO_LARGE."""
    max_mb = current_app.config["MAX_UPLOAD_MB"]
    if not data:
        raise ApiError(400, "FILE_EMPTY", "The file is empty.")
    start = ALLOWED_TYPES.get(mime_type)
    if start is None or not data.startswith(start):
        raise ApiError(400, "FILE_TYPE_NOT_ALLOWED", "Upload a PDF, JPG or PNG file.")
    if len(data) > max_mb * 1024 * 1024:
        raise ApiError(400, "FILE_TOO_LARGE", f"The file is larger than {max_mb} MB.")
