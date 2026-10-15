# Tests that use the API the way the frontend does, plus a few checks of the rules.

import io
import re
from datetime import date

from conftest import BUSINESS_FORM
from filings import FORM_FOLDERS, due_date, form_content, periods_of_year
from helpers import gstin_check_character, outbox
from models import CaProfile, ComplianceItem, ObligationTemplate, db
from ocr import read_proof_fields

PDF = b"%PDF-1.4\n%a tiny test file\n"


def upload(client, headers, url="/api/v1/documents", **fields):
    data = {"doc_type": "other", **fields, "file": (io.BytesIO(PDF), "file.pdf", "application/pdf")}
    return client.post(url, data=data, headers=headers, content_type="multipart/form-data")


def verified_ca(client, login, admin, prices=True):
    """A CA with a verified profile (and a price of ₹500 for every service); returns their header."""
    ca = login("ca", name="Meera Shah")
    profile = {"membership_no": "123456", "cop_number": "COP-1", "city": "Pune", "languages": ["english"],
               "specializations": ["gstr_1", "gstr_3b"], "capacity": 5, "years_experience": 8}
    assert client.put("/api/v1/marketplace/ca-profile", json=profile, headers=ca).status_code == 200
    profile_id = client.get("/api/v1/marketplace/ca-profile", headers=ca).get_json()["id"]
    # An admin can only verify a CA who uploaded their certificate.
    assert client.post(f"/api/v1/admin/cas/{profile_id}/verify", headers=admin).status_code == 409
    assert upload(client, ca, "/api/v1/marketplace/ca-profile/certificate").status_code == 200
    assert client.post(f"/api/v1/admin/cas/{profile_id}/verify", headers=admin).status_code == 200
    if prices:
        services = client.get("/api/v1/marketplace/services", headers=ca).get_json()
        items = [{"service_id": s["id"], "price": "500"} for s in services]
        client.put("/api/v1/marketplace/ca-services", json={"items": items}, headers=ca)
    return ca, profile_id


# --- Accounts ---


def test_health(client):
    assert client.get("/api/health").get_json() == {"status": "ok", "database": "ok"}


def test_signup_verify_and_login(client):
    signup = {"full_name": "Asha", "email": "Asha@Example.com", "password": "Passw0rd1", "role": "business",
              "terms_accepted": True}
    assert client.post("/api/v1/auth/signup", json=signup).status_code == 201
    assert client.post("/api/v1/auth/signup", json=signup).get_json()["error"]["code"] == "EMAIL_TAKEN"
    login = {"email": "asha@example.com", "password": "Passw0rd1"}
    assert client.post("/api/v1/auth/login", json=login).get_json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    code = re.search(r"\b(\d{6})\b", outbox[-1].get_content()).group(1)
    assert client.post("/api/v1/auth/verify-email", json={"email": "asha@example.com", "code": code}).status_code == 204
    response = client.post("/api/v1/auth/login", json=login)
    assert response.status_code == 200 and response.get_json()["user"]["role"] == "business"
    assert client.post("/api/v1/auth/login", json={**login, "password": "wrong"}).status_code == 401


def test_weak_password_and_admin_signup_are_refused(client):
    base = {"full_name": "A", "email": "a@example.com", "password": "short", "role": "business", "terms_accepted": True}
    assert client.post("/api/v1/auth/signup", json=base).status_code == 422
    assert client.post("/api/v1/auth/signup", json={**base, "password": "Passw0rd1", "role": "admin"}).status_code == 422


def test_reset_password(client, login):
    login("business", "me@example.com")
    assert client.post("/api/v1/auth/forgot-password", json={"email": "me@example.com"}).status_code == 204
    code = re.search(r"\b(\d{6})\b", outbox[-1].get_content()).group(1)
    reset = {"email": "me@example.com", "code": code, "new_password": "NewPassw0rd"}
    assert client.post("/api/v1/auth/reset-password", json=reset).status_code == 204
    assert outbox[-1]["Subject"] == "Your CA Helper password was changed"
    assert client.post("/api/v1/auth/reset-password", json=reset).get_json()["error"]["code"] == "OTP_INVALID"
    login_form = {"email": "me@example.com", "password": "NewPassw0rd"}
    assert client.post("/api/v1/auth/login", json=login_form).status_code == 200


def test_each_role_sees_only_its_pages(client, login):
    assert client.get("/api/v1/auth/me").status_code == 401  # no token
    business, ca, admin = login("business"), login("ca"), login("admin")
    assert client.get("/api/v1/admin/stats", headers=business).status_code == 403
    assert client.get("/api/v1/compliance/items", headers=ca).status_code == 403
    assert client.get("/api/v1/ca-workspace/clients", headers=admin).status_code == 403
    assert client.get("/api/v1/admin/stats", headers=admin).status_code == 200


def test_email_switch(client, login):
    headers = login("business")
    assert client.get("/api/v1/auth/settings", headers=headers).get_json() == {"email_notifications": True}
    client.put("/api/v1/auth/settings", json={"email_notifications": False}, headers=headers)
    assert client.get("/api/v1/auth/settings", headers=headers).get_json() == {"email_notifications": False}


# --- Registering a business and its filings ---


def test_register_works_out_the_profile_and_the_filings(client, owner):
    page = client.get("/api/v1/onboarding/business", headers=owner).get_json()
    assert page["business"]["pan"] == "ABCDE1234F"
    assert page["profile"]["msme_tier"] == "micro"
    assert page["profile"]["gst_scheme"] == "regular_qrmp"
    assert page["profile"]["itr_form"] == "itr_4"
    forms = {item["form_code"] for item in client.get("/api/v1/compliance/items", headers=owner).get_json()}
    assert forms == {"itr", "gstr_1", "gstr_3b"}  # no TDS: the business does not deduct TDS
    assert client.post("/api/v1/onboarding/business", json=BUSINESS_FORM, headers=owner).status_code == 409


def test_the_pan_is_stored_encrypted(owner):
    stored = db.session.execute(db.text("SELECT pan FROM businesses")).scalar()
    assert stored != "ABCDE1234F"


def test_a_wrong_gstin_is_explained(client, login):
    headers = login("business")
    response = client.post("/api/v1/onboarding/business", json={**BUSINESS_FORM, "gstin": "27ABCDE1234F1Z5"},
                           headers=headers)
    assert response.status_code == 422
    assert "last character" in response.get_json()["error"]["message"]


def test_editing_adds_tds_filings_and_says_what_changed(client, owner):
    form = {**BUSINESS_FORM, "deducts_tds": True, "tan": "MUMA12345B"}
    page = client.put("/api/v1/onboarding/business", json=form, headers=owner).get_json()
    assert page["changes"]["filings"]["added"] == 4  # the four quarters of 26Q
    assert {"line": "files_26q", "old": False, "new": True} in page["changes"]["profile"]


def test_due_dates_and_periods():
    template = ObligationTemplate(frequency="quarterly", due_date_rule={"quarters": [[7, 13], [10, 13], [1, 13], [4, 13]]})
    quarters = periods_of_year("quarterly", date(2026, 4, 1))
    assert [label for label, *_ in quarters] == ["Q1 2026-27", "Q2 2026-27", "Q3 2026-27", "Q4 2026-27"]
    assert due_date(template, quarters[3][2], 4) == date(2027, 4, 13)
    monthly = ObligationTemplate(frequency="monthly", due_date_rule={"day": 20})
    assert due_date(monthly, date(2026, 12, 31)) == date(2027, 1, 20)  # December -> January


def test_gstin_check_character():
    assert gstin_check_character("27ABCDE1234F1Z") == "0"


def test_every_form_has_its_texts():
    for form_code in FORM_FOLDERS:
        content = form_content(form_code)
        assert content["explanation"].startswith("# ") and content["instructions"].startswith("# ")
        assert content["checklist"]


def test_nic_search_and_save(client, owner):
    found = client.get("/api/v1/onboarding/nic-codes?q=bread", headers=owner).get_json()
    assert found
    response = client.put("/api/v1/onboarding/business/nic-code", json={"code": found[0]["code"]}, headers=owner)
    assert response.get_json()["code"] == found[0]["code"]


# --- The filing page ---


def first_filing(client, owner):
    return client.get("/api/v1/compliance/items", headers=owner).get_json()[0]


def test_ticking_the_checklist_changes_the_status(client, owner):
    item = first_filing(client, owner)
    page = client.get(f"/api/v1/compliance/items/{item['id']}", headers=owner).get_json()
    assert page["explanation"] and page["checklist"]
    for entry in page["checklist"]:
        page = client.post(f"/api/v1/compliance/items/{item['id']}/checklist", json={"key": entry["key"], "ticked": True},
                           headers=owner).get_json()
    if page["filing"]["status"] != "overdue":
        assert page["filing"]["status"] == "ready"


def test_mark_filed_and_undo(client, owner):
    item = first_filing(client, owner)
    url = f"/api/v1/compliance/items/{item['id']}"
    page = client.post(url + "/mark-filed", data={"acknowledgement_no": "aa123"}, headers=owner).get_json()
    assert page["filing"]["status"] == "filed" and page["filing"]["acknowledgement_no"] == "AA123"
    assert client.post(url + "/mark-filed", headers=owner).get_json()["error"]["code"] == "ALREADY_FILED"
    page = client.post(url + "/unmark-filed", headers=owner).get_json()
    assert page["filing"]["status"] in ("upcoming", "overdue")


def test_an_acknowledgement_is_read_by_ocr():
    fields = read_proof_fields("GSTR-3B Acknowledgement ARN: AA2707260123456 Date of filing 20/07/2026 "
                               "Financial Year 2026-27 Tax Period Q1", date(2026, 10, 1))
    assert fields["acknowledgement_no"] == "AA2707260123456"
    assert fields["form_codes"] == ["gstr_3b"] and fields["filing_date"] == "2026-07-20"


def test_dashboard_and_penalties(client, owner):
    dashboard = client.get("/api/v1/compliance/dashboard", headers=owner).get_json()
    assert dashboard["registered"] is True
    exposure = client.get("/api/v1/alerts/penalties", headers=owner).get_json()
    assert exposure["overdue_count"] == dashboard["overdue"]
    item = first_filing(client, owner)
    estimate = client.get(f"/api/v1/alerts/penalties/{item['id']}?tax_due=1000", headers=owner).get_json()
    assert estimate["status"] in ("estimated", "not_late", "pending")


# --- Documents ---


def test_upload_link_and_delete(client, owner):
    item = first_filing(client, owner)
    document = upload(client, owner).get_json()
    assert document["ocr_status"] in ("processed", "failed")
    key = client.get(f"/api/v1/compliance/items/{item['id']}", headers=owner).get_json()["checklist"][0]["key"]
    linked = client.post(f"/api/v1/documents/{document['id']}/links",
                         json={"compliance_item_id": item["id"], "checklist_key": key}, headers=owner).get_json()
    assert linked["links"][0]["checklist_key"] == key
    listed = client.get(f"/api/v1/documents?compliance_item_id={item['id']}", headers=owner).get_json()
    assert listed["total"] == 1
    assert client.get(f"/api/v1/documents/{document['id']}/file", headers=owner).data == PDF
    assert client.delete(f"/api/v1/documents/{document['id']}", headers=owner).status_code == 204


def test_only_real_pdf_jpg_and_png_files(client, owner):
    data = {"doc_type": "other", "file": (io.BytesIO(b"not a pdf"), "x.pdf", "application/pdf")}
    response = client.post("/api/v1/documents", data=data, headers=owner, content_type="multipart/form-data")
    assert response.get_json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"


# --- Find a CA, requests and the CA's work ---


def test_find_a_ca_request_accept_and_finish(client, owner, login):
    admin = login("admin")
    ca, profile_id = verified_ca(client, login, admin)
    cas = client.get("/api/v1/marketplace/cas?service=gstr_3b", headers=owner).get_json()
    assert cas["items"][0]["full_name"] == "Meera Shah" and cas["items"][0]["price"] == "500.00"

    filings = client.get(f"/api/v1/marketplace/cas/{profile_id}/requestable-filings", headers=owner).get_json()
    gst = [f for f in filings if f["form_code"] == "gstr_3b" and f["blocked_reason"] is None][0]
    body = {"ca_profile_id": profile_id, "items": [{"compliance_item_id": gst["id"],
                                                    "service_id": gst["options"][0]["service_id"]}]}
    first = client.post("/api/v1/marketplace/engagements", json=body, headers=owner).get_json()
    again = client.post("/api/v1/marketplace/engagements", json=body, headers=owner)
    assert again.get_json()["error"]["code"] == "FILING_ALREADY_REQUESTED"
    assert client.post(f"/api/v1/marketplace/engagements/{first['id']}/withdraw", headers=owner).status_code == 200

    engagement = client.post("/api/v1/marketplace/engagements", json=body, headers=owner).get_json()
    accepted = client.post(f"/api/v1/marketplace/engagements/{engagement['id']}/accept", headers=ca).get_json()
    assert accepted["status"] == "active" and accepted["items"][0]["agreed_price"] == "500.00"
    assert db.session.get(ComplianceItem, gst["id"]).status == "with_ca"

    # The CA asks for a document; the business answers with one from its vault.
    clients = client.get("/api/v1/ca-workspace/clients", headers=ca).get_json()
    business_id = clients[0]["business_id"]
    asked = client.post(f"/api/v1/ca-workspace/clients/{business_id}/document-requests",
                        json={"compliance_item_id": gst["id"], "message": "Please send the invoices"}, headers=ca)
    assert asked.status_code == 201
    todo = client.get("/api/v1/ca-workspace/document-requests", headers=owner).get_json()
    assert todo[0]["ca_name"] == "Meera Shah"
    document = upload(client, owner).get_json()
    fulfilled = client.post(f"/api/v1/ca-workspace/document-requests/{todo[0]['id']}/fulfil",
                            json={"document_id": document["id"]}, headers=owner)
    assert fulfilled.get_json()["status"] == "fulfilled"
    assert client.get(f"/api/v1/documents/{document['id']}/file", headers=ca).status_code == 200

    # The CA files it: the engagement is completed and the business can rate it once.
    page = client.get(f"/api/v1/ca-workspace/clients/{business_id}", headers=ca).get_json()
    assert page["business"]["legal_name"] == "Asha Traders"
    filed = client.post(f"/api/v1/ca-workspace/clients/{business_id}/filings/{gst['id']}/mark-filed",
                        data={"acknowledgement_no": "AB1"}, headers=ca).get_json()
    assert filed["engagement_completed"] is True
    rating = {"stars": 5, "review": "Quick"}
    url = f"/api/v1/marketplace/engagements/{engagement['id']}/rating"
    assert client.post(url, json=rating, headers=owner).get_json()["rating"]["stars"] == 5
    assert client.post(url, json=rating, headers=owner).get_json()["error"]["code"] == "ALREADY_RATED"
    assert client.get(f"/api/v1/marketplace/cas/{profile_id}", headers=owner).get_json()["rating_average"] == 5.0


def test_a_ca_can_decline(client, owner, login):
    ca, profile_id = verified_ca(client, login, login("admin"))
    filings = client.get(f"/api/v1/marketplace/cas/{profile_id}/requestable-filings", headers=owner).get_json()
    free = [f for f in filings if f["blocked_reason"] is None][0]
    body = {"ca_profile_id": profile_id, "items": [{"compliance_item_id": free["id"],
                                                    "service_id": free["options"][0]["service_id"]}]}
    engagement = client.post("/api/v1/marketplace/engagements", json=body, headers=owner).get_json()
    declined = client.post(f"/api/v1/marketplace/engagements/{engagement['id']}/decline", headers=ca).get_json()
    assert declined["status"] == "declined"
    assert outbox[-1]["Subject"] == "Your CA declined your request"
    inbox = client.get("/api/v1/alerts/notifications", headers=owner).get_json()["items"]
    assert inbox[0]["title"] == "Your CA declined your request"
    read = client.post(f"/api/v1/alerts/notifications/{inbox[0]['id']}/read", headers=owner).get_json()
    assert read["read_at"] is not None


def test_an_unverified_ca_is_not_listed(client, owner, login):
    ca = login("ca")
    profile = {"membership_no": "654321", "cop_number": "C", "city": "Delhi", "languages": ["hindi"],
               "specializations": ["itr"], "capacity": 1, "years_experience": 1}
    client.put("/api/v1/marketplace/ca-profile", json=profile, headers=ca)
    assert client.get("/api/v1/marketplace/cas", headers=owner).get_json()["total"] == 0


def test_admin_rejects_a_ca_and_lists_users(client, login):
    admin, ca = login("admin"), login("ca")
    profile = {"membership_no": "111111", "cop_number": "C", "city": "Delhi", "languages": ["hindi"],
               "specializations": ["itr"], "capacity": 1, "years_experience": 1}
    client.put("/api/v1/marketplace/ca-profile", json=profile, headers=ca)
    profile_id = CaProfile.query.first().id
    rejected = client.post(f"/api/v1/admin/cas/{profile_id}/reject", json={"reason": "Wrong number"}, headers=admin)
    assert rejected.get_json()["verification_status"] == "rejected"
    users = client.get("/api/v1/admin/users?role=ca", headers=admin).get_json()
    assert users["total"] == 1


def test_reminders_are_sent_once(owner):
    from reminders import send_reminders

    filing = ComplianceItem.query.order_by(ComplianceItem.due_date.desc()).first()
    day = filing.due_date  # the due date itself: a "due today" reminder
    assert send_reminders(day) >= 1
    assert send_reminders(day) == 0  # nothing new the second time


def test_the_seed_can_run_again():
    from seed import seed

    before = ObligationTemplate.query.count()
    seed()
    assert ObligationTemplate.query.count() == before

