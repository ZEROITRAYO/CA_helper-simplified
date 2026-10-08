# Small helpers the route files share: errors, the logged-in user, money, passwords,
# email, notifications, GSTIN checks and storing uploaded files.

import hashlib
import io
import json
import smtplib
import uuid
from datetime import datetime
from decimal import Decimal
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from flask import current_app, jsonify, render_template, request, send_file
from flask_jwt_extended import get_current_user, jwt_required

import ocr
from models import Business, ComplianceItemDocument, Document, DocumentRequest, Notification, db

REPO = Path(__file__).resolve().parent.parent  # the project folder (content/ is there)


def error(status, code, message):
    """An error answer, e.g. error(404, "FILING_NOT_FOUND", "This filing was not found.")."""
    return jsonify({"error": {"code": code, "message": message}}), status


def role_required(*roles):
    """Only logged-in users with one of these roles may use the route."""

    def decorator(route):
        @wraps(route)
        @jwt_required()
        def check_role(*args, **kwargs):
            if get_current_user().role not in roles:
                return error(403, "FORBIDDEN", "You do not have access to this page.")
            return route(*args, **kwargs)

        return check_role

    return decorator


def current_user():
    return get_current_user()


def my_business():
    """The logged-in user's business, or None before they register one."""
    return Business.query.filter_by(user_id=current_user().id).first()


def as_uuid(value):
    """A UUID from text, or None when the text is not one."""
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def today_in_india():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def india_date(time):
    """The date in India of a stored (UTC) time."""
    return time.astimezone(ZoneInfo("Asia/Kolkata")).date()


def iso(value):
    """A date or time as text for JSON (None stays None)."""
    return value.isoformat() if value is not None else None


def money(value):
    """An amount as text with 2 decimals, e.g. "1250.00" (None stays None)."""
    return None if value is None else f"{Decimal(value):.2f}"


def read_amount(value, lowest, highest):
    """A rupee amount between `lowest` and `highest`, or None if `value` is not one."""
    if isinstance(value, bool):
        return None
    try:
        amount = round(Decimal(str(value)), 2)
        return amount if lowest <= amount <= highest else None
    except Exception:  # not a number at all
        return None


def page_of(query, to_dict):
    """One page of a query (?page=, ?page_size= up to 100) as {items, page, page_size, total}."""
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = min(max(request.args.get("page_size", 20, type=int), 1), 100)
    result = query.paginate(page=page, per_page=page_size, error_out=False)
    items = [to_dict(item) for item in result.items]
    return {"items": items, "page": page, "page_size": page_size, "total": result.total}


def format_inr(amount):
    """Indian digit grouping, e.g. 4500000 -> "₹45,00,000"."""
    digits = str(int(amount))
    head, groups = digits[:-3], [digits[-3:]]
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return "₹" + ",".join(groups)


# --- Passwords (argon2: only the hash is stored) ---

hasher = PasswordHasher()


def hash_password(password):
    return hasher.hash(password)


def check_password(password_hash, password):
    try:
        return hasher.verify(password_hash, password)
    except Exception:
        return False


# --- Email and notifications ---

outbox = []  # emails "sent" while MAIL_SUPPRESS_SEND is on (the tests read it)


def send_email(to, subject, template, **values):
    """Send one email; its text is templates/email/<template>.txt."""
    message = EmailMessage()
    message["From"] = current_app.config["MAIL_SENDER"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(render_template(f"email/{template}.txt", **values))
    if current_app.config["MAIL_SUPPRESS_SEND"]:
        outbox.append(message)
        return
    try:
        with smtplib.SMTP(current_app.config["MAIL_SERVER"], current_app.config["MAIL_PORT"]) as smtp:
            smtp.send_message(message)
    except OSError as problem:
        print("Could not send the email:", type(problem).__name__)  # never print the address


def notify(user, kind, title, body, link=None):
    """Add a notification to the user's inbox (never put PAN, GSTIN or such in it)."""
    notification = Notification(user_id=user.id, type=kind, title=title, body=body, link=link)
    db.session.add(notification)
    return notification


def email_notice(user, title, body):
    """Email a notification's text, if the user wants emails. Call after the commit."""
    if user.email_notifications:
        send_email(user.email, title, "notification", name=user.full_name, title=title, body=body)


# --- GSTIN ---

GST_STATES = json.loads((REPO / "content/reference/gst_states.json").read_text())["states"]


def state_code(name):
    """The GST code of a state, e.g. "27" for Maharashtra (None if it is not in the list)."""
    for state in GST_STATES:
        if state["name"] == name:
            return state["code"]
    return None


def gstin_check_character(first_14):
    """The 15th character of a GSTIN: each character's value (0-9, A-Z = 0-35) is multiplied
    by 1 and 2 in turn, the base-36 digits of each product are added, and the check
    character makes the total a multiple of 36."""
    characters = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    total = 0
    for index, character in enumerate(first_14):
        product = characters.index(character) * (1 if index % 2 == 0 else 2)
        total += product // 36 + product % 36
    return characters[(36 - total % 36) % 36]


def gstin_error(gstin, pan, state):
    """What is wrong with a GSTIN for this PAN and state, or None."""
    if gstin_check_character(gstin[:14]) != gstin[14]:
        return "This GSTIN is not valid: its last character does not match. Check for a typo."
    code = state_code(state)
    if code and gstin[:2] != code:
        return f"This GSTIN starts with {gstin[:2]}, but the code of {state} is {code}."
    if pan and gstin[2:12] != pan:
        return "The PAN inside this GSTIN (characters 3 to 12) does not match your PAN."
    return None


# --- Uploaded files (stored encrypted in the database) ---

FILE_STARTS = {"application/pdf": b"%PDF-", "image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}


def read_upload():
    """(upload, bytes, None) for the request's "file", or (None, None, error answer)."""
    upload = request.files.get("file")
    if upload is None:
        return None, None, error(422, "VALIDATION_ERROR", "Choose a file to upload.")
    data = upload.read()
    max_mb = current_app.config["MAX_UPLOAD_MB"]
    if not data:
        return None, None, error(400, "FILE_EMPTY", "The file is empty.")
    start = FILE_STARTS.get(upload.mimetype)
    if start is None or not data.startswith(start):  # the bytes must really be a PDF, JPG or PNG
        return None, None, error(400, "FILE_TYPE_NOT_ALLOWED", "Upload a PDF, JPG or PNG file.")
    if len(data) > max_mb * 1024 * 1024:
        return None, None, error(400, "FILE_TOO_LARGE", f"The file is larger than {max_mb} MB.")
    return upload, data, None


def save_document(owner_id, uploader_id, doc_type, upload, data):
    """Store an uploaded file (encrypted) and read it with OCR, keeping only non-personal facts."""
    fernet = Fernet(current_app.config["FIELD_ENCRYPTION_KEY"])
    document = Document(owner_id=owner_id, uploaded_by_id=uploader_id, doc_type=doc_type,
                        original_filename=(upload.filename or "upload")[:255], mime_type=upload.mimetype,
                        content=fernet.encrypt(data), size_bytes=len(data),
                        sha256=hashlib.sha256(data).hexdigest())
    try:
        text = ocr.extract_text(data, upload.mimetype)
        document.ocr_fields = ocr.read_proof_fields(text, today_in_india())
        document.ocr_status = "processed"
    except ValueError as problem:  # the file could not be read; the message says why
        document.ocr_status, document.ocr_fields = "failed", {"error": str(problem)}
    except Exception:  # an unexpected OCR problem must never lose the upload
        document.ocr_status, document.ocr_fields = "failed", {"error": "The file could not be read."}
    db.session.add(document)
    db.session.flush()  # gives document.id
    return document


def send_document(document):
    """The decrypted file as a download."""
    data = Fernet(current_app.config["FIELD_ENCRYPTION_KEY"]).decrypt(document.content)
    return send_file(io.BytesIO(data), mimetype=document.mime_type, download_name=document.original_filename)


def remove_document(document_id):
    """Delete a document and its links (whatever points to it must be cleared first)."""
    ComplianceItemDocument.query.filter_by(document_id=document_id).delete()
    DocumentRequest.query.filter_by(document_id=document_id).update({"document_id": None})
    document = db.session.get(Document, document_id)
    if document:
        db.session.delete(document)
