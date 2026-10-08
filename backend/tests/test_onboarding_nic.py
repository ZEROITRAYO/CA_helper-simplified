"""NIC activity codes: the official list (ON9), the search and saving the chosen code (ON10)."""

import pytest
from sqlalchemy import func, select

from app.models import NicCode, User, UserRole
from app.seed import seed_nic_codes

SEARCH_URL = "/api/v1/onboarding/nic-codes"
SAVE_URL = "/api/v1/onboarding/business/nic-code"

# A few real codes from content/reference/nic_2008.csv.
SAMPLE_CODES = [
    ("10711", "Manufacture of bread"),
    ("10712", "Manufacture of biscuits, cakes, pastries, rusks etc."),
    ("10719", "Manufacture of other bakery products n.e.c."),
    ("47214", "Retail sale of bakery products, dairy products and eggs"),
    ("56302", "Tea/coffee shops"),
    ("62011", "Writing, modifying, testing of computer program to meet the needs of a client"),
]


@pytest.fixture()
def nic_codes(database):
    for code, description in SAMPLE_CODES:
        database.session.add(NicCode(code=code, description=description))
    database.session.commit()


@pytest.fixture()
def bakery(business_with_filings, database):
    """The business describes itself as a bakery; returns (business, owner)."""
    business = business_with_filings
    business.description = "We bake biscuits and cakes. Contact asha@example.com"
    database.session.commit()
    return business, database.session.get(User, business.user_id)


# --- ON9: the official list -------------------------------------------------------


def test_seed_loads_only_5_digit_codes_with_the_leading_zero_put_back(database):
    seed_nic_codes()
    database.session.commit()

    codes = set(database.session.scalars(select(NicCode.code)))
    assert len(codes) > 1000
    assert "01411" in codes  # "Raising and breeding of cattle" (was 1411 in the PDF)
    assert "14101" in codes  # garments: must not clash with the cattle code
    for code in codes:
        assert len(code) == 5


def test_seed_twice_adds_nothing(database):
    seed_nic_codes()
    database.session.commit()
    first = database.session.scalar(select(func.count(NicCode.id)))

    seed_nic_codes()
    database.session.commit()

    assert database.session.scalar(select(func.count(NicCode.id))) == first


# --- ON10: search and save -------------------------------------------------------


def test_search_by_word_or_code(client, bakery, nic_codes, auth_headers):
    business, owner = bakery
    headers = auth_headers(owner)

    by_word = client.get(SEARCH_URL, query_string={"q": "bakery"}, headers=headers).get_json()
    by_code = client.get(SEARCH_URL, query_string={"q": "5630"}, headers=headers).get_json()
    too_short = client.get(SEARCH_URL, query_string={"q": "b"}, headers=headers).get_json()

    assert [row["code"] for row in by_word] == ["10719", "47214"]
    assert [row["code"] for row in by_code] == ["56302"]
    assert too_short == []


def test_save_a_code_and_read_it_back(client, bakery, nic_codes, auth_headers):
    business, owner = bakery
    headers = auth_headers(owner)

    response = client.put(SAVE_URL, json={"code": "10712"}, headers=headers)

    assert response.status_code == 200
    assert response.get_json()["code"] == "10712"
    mine = client.get("/api/v1/onboarding/business", headers=headers).get_json()
    assert mine["nic_code"]["code"] == "10712"


def test_before_choosing_the_code_is_null(client, bakery, auth_headers):
    business, owner = bakery

    mine = client.get("/api/v1/onboarding/business", headers=auth_headers(owner)).get_json()

    assert mine["nic_code"] is None


def test_an_unknown_code_is_refused(client, bakery, nic_codes, auth_headers):
    business, owner = bakery

    response = client.put(SAVE_URL, json={"code": "12345"}, headers=auth_headers(owner))

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "UNKNOWN_NIC_CODE"


# --- Access -----------------------------------------------------------------------


def test_ca_and_admin_cannot_use_the_nic_endpoints(client, make_user, auth_headers):
    for role in (UserRole.CA, UserRole.ADMIN):
        headers = auth_headers(make_user(role=role))
        search = client.get(SEARCH_URL, query_string={"q": "bread"}, headers=headers)
        assert search.status_code == 403
        assert client.put(SAVE_URL, json={"code": "10711"}, headers=headers).status_code == 403
