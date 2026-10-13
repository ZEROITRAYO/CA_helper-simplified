# Test setup (pytest reads this file first). The tests use their own database,
# TEST_DATABASE_URL (docker-compose.yml and CI set it), never the shared Neon database.

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

# Point the app at the test database BEFORE app.py is imported (it connects at import).
TEST_URL = os.environ["TEST_DATABASE_URL"]
os.environ["DATABASE_URL"] = TEST_URL
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-that-is-long-enough"
os.environ["FIELD_ENCRYPTION_KEY"] = "Z5radg25qAqquvqRiPO960hRLtJmVhE0P3dYa_T1Mk8="

# Create the test database the first time.
server = create_engine(make_url(TEST_URL).set(database="postgres"), isolation_level="AUTOCOMMIT")
with server.connect() as connection:
    name = make_url(TEST_URL).database
    if not connection.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).scalar():
        connection.execute(text(f'CREATE DATABASE "{name}"'))
server.dispose()

from app import app  # noqa: E402
from helpers import hash_password, outbox  # noqa: E402
from models import User, db  # noqa: E402
from seed import seed  # noqa: E402

app.config["MAIL_SUPPRESS_SEND"] = True
RULE_TABLES = ("service_catalog", "rule_thresholds", "obligation_templates", "penalty_rules", "nic_codes")
PASSWORD = "Correct-Horse-9"


@pytest.fixture(scope="session", autouse=True)
def rules():
    """Fresh tables with the rule tables filled once for the whole test run."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed()
    yield


@pytest.fixture(autouse=True)
def clean():
    """Every test starts with no users, businesses, filings ... (the rules stay)."""
    outbox.clear()
    with app.app_context():
        yield
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            if table.name not in RULE_TABLES:
                db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture()
def login(client):
    """login("business") makes a verified user with that role and returns their auth header."""

    def make(role, email=None, name="Test User"):
        email = email or f"{role}{User.query.count()}@example.com"
        db.session.add(User(email=email, password_hash=hash_password(PASSWORD), full_name=name, role=role,
                            email_verified=True))
        db.session.commit()
        token = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).get_json()
        return {"Authorization": "Bearer " + token["access_token"]}

    return make


BUSINESS_FORM = {
    "legal_name": "Asha Traders", "entity_type": "proprietorship", "state": "Maharashtra",
    "address": "1 MG Road, Pune", "description": "We sell shoes", "annual_turnover": "4500000",
    "investment_amount": "1000000", "pan": "ABCDE1234F", "phone": "9876543210", "gst_registered": True,
    "gstin": "27ABCDE1234F1Z0", "gst_qrmp": True, "deducts_tds": False, "pays_salary_above_limit": False,
}


@pytest.fixture()
def owner(client, login):
    """The auth header of a business owner who registered Asha Traders (a QRMP business)."""
    headers = login("business", "owner@example.com", "Asha Rao")
    response = client.post("/api/v1/onboarding/business", json=BUSINESS_FORM, headers=headers)
    assert response.status_code == 201
    return headers
