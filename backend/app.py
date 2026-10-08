# CA Helper backend: the Flask app. Start it with
#     flask --app app run --host 0.0.0.0 --port 8000 --debug     (docker compose does this)
# The routes are in the routes_*.py files, imported at the bottom of this file.

import os
import uuid

from flask import Flask, jsonify, redirect
from flask_jwt_extended import JWTManager
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

from models import User, db

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False  # stay logged in until "Log out"
app.config["FIELD_ENCRYPTION_KEY"] = os.environ.get("FIELD_ENCRYPTION_KEY")  # for PAN, GSTIN, TAN, phone
app.config["MAX_UPLOAD_MB"] = 5
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # bigger requests are refused
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "localhost")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", "1025"))
app.config["MAIL_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "CA Helper <no-reply@ca-helper.local>")
app.config["MAIL_SUPPRESS_SEND"] = False  # the tests turn this on

db.init_app(app)
jwt = JWTManager(app)

# Create the tables that do not exist yet (the team shares one database, so this changes
# nothing there once the tables are made).
with app.app_context():
    db.create_all()


# --- Login tokens: any 401 makes the frontend log out ---


@jwt.user_lookup_loader
def load_user(header, payload):
    return db.session.get(User, uuid.UUID(payload["sub"]))  # the token holds the user's id


def token_error(code, message):
    return jsonify({"error": {"code": code, "message": message}}), 401


jwt.unauthorized_loader(lambda reason: token_error("AUTH_REQUIRED", "Please log in."))
jwt.invalid_token_loader(lambda reason: token_error("TOKEN_INVALID", "Please log in again."))
jwt.expired_token_loader(lambda header, payload: token_error("TOKEN_EXPIRED", "Please log in again."))
jwt.user_lookup_error_loader(
    lambda header, payload: token_error("ACCOUNT_INACTIVE", "This account no longer exists.")
)


# --- Errors as JSON, and the health check ---


@app.errorhandler(HTTPException)
def http_error(error):
    """404, 405, 413, 500 ... in the same JSON shape as our own errors."""
    code = error.name.upper().replace(" ", "_")  # e.g. "NOT_FOUND"
    return jsonify({"error": {"code": code, "message": error.description}}), error.code


@app.route("/")
def home():
    return redirect("/api/health")


@app.route("/api/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "ok"})
    except Exception as error:
        print("Health check: database unavailable:", type(error).__name__)
        db.session.rollback()
        return jsonify({"status": "degraded", "database": "unavailable"}), 503


# The routes (they use `app` from this file, so they are imported last).
import routes_admin  # noqa: E402, F401
import routes_auth  # noqa: E402, F401
import routes_business  # noqa: E402, F401
import routes_ca  # noqa: E402, F401
import routes_documents  # noqa: E402, F401
import routes_marketplace  # noqa: E402, F401
