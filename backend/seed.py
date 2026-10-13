# Fills the rule tables: the service catalog, the legal limits, when each form is due, the
# penalties, and the official NIC codes. Safe to run again: rows are added or updated.
#
#     python seed.py            fill or update the rule tables (and move filings to the rules)
#     python seed.py --reset    empty a LOCAL database first (refuses the shared Neon database)
#
# The demo accounts and businesses are not made here: they are in demo_data.sql (README).

import csv
import sys
from datetime import date
from decimal import Decimal

from app import app
from filings import sync_filings
from helpers import REPO, now
from models import CatalogService, NicCode, ObligationTemplate, PenaltyRule, RegulatoryProfile, RuleThreshold, db

SERVICE_CATALOG = [  # (code, name, description, unit)
    ("itr_presumptive", "ITR filing: presumptive income (ITR-4)",
     "Income tax return for a business or profession on presumptive income.", "per_return"),
    ("itr_business", "ITR filing: business or profession (ITR-3)",
     "Income tax return for a proprietor or professional with business income.", "per_return"),
    ("itr_firm_company", "ITR filing: firm, LLP or company (ITR-5 / ITR-6)",
     "Income tax return for a partnership firm, LLP or company.", "per_return"),
    ("gstr_1", "GSTR-1 filing", "Return of outward supplies (sales).", "per_return"),
    ("gstr_3b", "GSTR-3B filing", "Summary GST return with tax payment.", "per_return"),
    ("cmp_08", "CMP-08 filing", "Statement for composition-scheme taxpayers.", "per_return"),
    ("gstr_4", "GSTR-4 filing", "Annual return for composition-scheme taxpayers.", "per_return"),
    ("tds_24q", "TDS return 24Q", "TDS return for tax deducted on salaries.", "per_return"),
    ("tds_26q", "TDS return 26Q", "TDS return for tax deducted on other payments.", "per_return"),
    ("gst_registration", "GST registration", "Getting a new GST registration.", "one_time"),
    ("tax_audit", "Tax audit", "Tax audit of the accounts for one financial year.", "per_year"),
    ("bookkeeping", "Bookkeeping", "Keeping the books of accounts up to date.", "per_month"),
    ("income_tax_notice", "Reply to an income-tax notice",
     "Reading an income-tax notice and preparing the reply.", "per_notice"),
]


# --- Legal values (from official sources) ----------------------------------------------
# Checked against official sources on 29 Sep 2026 (docs/TODO_VERIFY.md, "Verified values").
# A value whose source_reference still contains TODO_VERIFY is a proposal nobody has
# confirmed from an official text yet. When the law changes, add a row with a new
# effective_from instead of editing the old one.

RULES_FROM = date(2025, 4, 1)  # effective_from of every value below

MSME_SOURCE = (
    "Udyam Registration portal (udyamregistration.gov.in), MSME classification from "
    "1 April 2025 (MSMED Act; notification S.O. 1364(E), 21.03.2025)"
)

# (key, value, unit, description, source_reference)
RULE_THRESHOLDS = [
    ("msme.micro.max_investment", "25000000", "inr", "Micro: investment up to ₹2.5 crore", MSME_SOURCE),
    ("msme.micro.max_turnover", "100000000", "inr", "Micro: turnover up to ₹10 crore", MSME_SOURCE),
    ("msme.small.max_investment", "250000000", "inr", "Small: investment up to ₹25 crore", MSME_SOURCE),
    ("msme.small.max_turnover", "1000000000", "inr", "Small: turnover up to ₹100 crore", MSME_SOURCE),
    ("msme.medium.max_investment", "1250000000", "inr", "Medium: investment up to ₹125 crore", MSME_SOURCE),
    ("msme.medium.max_turnover", "5000000000", "inr", "Medium: turnover up to ₹500 crore", MSME_SOURCE),
    ("gst.registration.min_turnover", "2000000", "inr",
     "GST registration needed above ₹20 lakh (lower limit, for services)",
     "CBIC, 'GST - An Update' (1 May 2019), cbic-gst.gov.in: registration needed above "
     "₹20 lakh for services (₹10 lakh in Manipur, Mizoram, Nagaland, Tripura) and ₹40 lakh "
     "for goods (₹20 lakh in some states); CGST Act s.22, Notification 10/2019-CT"),
    ("gst.qrmp.max_turnover", "50000000", "inr", "Quarterly returns (QRMP) allowed up to ₹5 crore",
     "GST portal FAQ 'Quarterly Return and Monthly Payment (QRMP) Scheme' "
     "(tutorial.gst.gov.in/userguide/returns/FAQs_change_profile.htm)"),
    ("gst.composition.max_turnover", "15000000", "inr",
     "Composition scheme allowed up to ₹1.5 crore (goods)",
     "CBIC, 'GST - An Update' (1 May 2019): composition up to ₹1.5 crore for goods "
     "(₹75 lakh in special category states); CGST Act s.10, Notification 14/2019-CT"),
    ("itr.presumptive_44ad.max_turnover", "20000000", "inr",
     "Presumptive scheme (44AD) allowed up to ₹2 crore",
     "incometax.gov.in, File ITR-4 (Sugam) FAQ Q9: s.44AD up to ₹2 crore (₹3 crore when "
     "cash receipts are at most 5%)"),
    ("itr.audit_44ab.min_turnover", "10000000", "inr", "Tax audit needed above ₹1 crore",
     "incometax.gov.in, Income Tax Forms FAQ: tax audit above ₹1 crore for a business "
     "(₹10 crore when cash is at most 5%); s.44AB of the 1961 Act, s.63 of the 2025 Act"),
]


# How each form applies and when it is due. Due-date rules (filings.due_date):
#   monthly    {"day": 11}                       the 11th of the next month
#   quarterly  {"quarters": [[7, 13], ...]}      [month, day] for Q1, Q2, Q3, Q4
#   yearly     {"month": 7, "day": 31}           that date after the financial year ends
#              (ITR also has "audit_month" / "audit_day" for businesses with an audit, and
#              "by_itr_form" {"itr_5": [7, 31]}: another date without an audit for that form)
# Applicability: every key must match the regulatory profile, e.g. {"gst_scheme": [...]};
# {} means every business.
# (form, name, frequency, applicability, due_date_rule, source_reference)
GST_FAQ = "tutorial.gst.gov.in/userguide/returns/"
OBLIGATION_TEMPLATES = [
    ("itr", "Income tax return", "yearly", {},
     {"month": 8, "day": 31, "audit_month": 10, "audit_day": 31, "by_itr_form": {"itr_5": [7, 31]}},
     "incometax.gov.in, Income Tax Returns FAQ Q16 and Q24: 31 August for individuals and HUFs "
     "with business or professional income and no audit (31 July only without business "
     "income: no profile of the app), 31 October with an audit; s.139(1) of the 1961 Act, "
     "s.263 of the 2025 Act as amended by Finance Act 2026. TODO_VERIFY: ITR-5 (firms, LLPs) "
     "without audit, 31 July used (sources say 31 July or 31 August; the earlier date)"),
    ("gstr_1", "GSTR-1 (monthly)", "monthly", {"gst_scheme": ["regular_monthly"]},
     {"day": 11}, f"GST portal FAQ 'Form GSTR-1' Q10 ({GST_FAQ}GSTR_1.htm): 11th of the next month"),
    ("gstr_1", "GSTR-1 (quarterly, QRMP)", "quarterly", {"gst_scheme": ["regular_qrmp"]},
     {"quarters": [[7, 13], [10, 13], [1, 13], [4, 13]]},
     f"GST portal FAQ 'Form GSTR-1' Q10 ({GST_FAQ}GSTR_1.htm): 13th after the quarter"),
    ("gstr_3b", "GSTR-3B (monthly)", "monthly", {"gst_scheme": ["regular_monthly"]},
     {"day": 20}, f"GST portal FAQ 'Form GSTR-3B' ({GST_FAQ}GSTR3B.htm): 20th of the next month"),
    ("gstr_3b", "GSTR-3B (quarterly, QRMP)", "quarterly", {"gst_scheme": ["regular_qrmp"]},
     {"quarters": [[7, 22], [10, 22], [1, 22], [4, 22]]},
     f"GST portal FAQ 'Form GSTR-3B' ({GST_FAQ}GSTR3B.htm) and GSTN QRMP advisory Q28: "
     "22nd or 24th after the quarter by state; the app uses the 22nd for every state "
     "(the earlier date, as the team decided on 2026-09-29)"),
    ("cmp_08", "CMP-08", "quarterly", {"gst_scheme": ["composition"]},
     {"quarters": [[7, 18], [10, 18], [1, 18], [4, 18]]},
     f"GST portal FAQ 'Filing Form GST CMP-08' Q3 ({GST_FAQ}FAQs_CMP02.htm): 18th after the quarter"),
    ("gstr_4", "GSTR-4", "yearly", {"gst_scheme": ["composition"]}, {"month": 6, "day": 30},
     "TODO_VERIFY: 30 June after the FY from FY 2024-25 (CGST Rules r.62 as amended by "
     "Notification 12/2024-CT, 10.07.2024; not read, the GST portal FAQ still says the "
     "30th of the month after the FY)"),
    ("tds_24q", "TDS return 24Q (salaries)", "quarterly", {"files_24q": [True]},
     {"quarters": [[7, 31], [10, 31], [1, 31], [5, 31]]},
     "incometax.gov.in, Form 138 (earlier 24Q) user manual: 31 July, 31 October, "
     "31 January, 31 May; shown as Form 138 from tax year 2026-27 (Income-tax Act 2025 "
     "s.392 and Income-tax Rules 2026; filings.RENAMED_FORMS)"),
    ("tds_26q", "TDS return 26Q (other payments)", "quarterly", {"files_26q": [True]},
     {"quarters": [[7, 31], [10, 31], [1, 31], [5, 31]]},
     "incometax.gov.in, Form 140 (earlier 26Q) user manual: 31 July, 31 October, "
     "31 January, 31 May; shown as Form 140 from tax year 2026-27 (Income-tax Act 2025 "
     "s.393 and Income-tax Rules 2026; filings.RENAMED_FORMS)"),
]


# One penalty rule per form: (form, amounts, source_reference). Amounts are rupees
# (annual_interest_rate is % a year); a missing amount stays empty (NULL) and the estimator
# says so. Where a fee or cap depends on turnover or income, the value for a small business
# (turnover up to ₹1.5 crore) is stored and the others are named in the source.
# docs/TODO_VERIFY.md, "Penalties", lists what each value rests on.
GST_LATE_FEE = "CBIC Circular 26/26/2017-GST: ₹50 a day (₹25 CGST + ₹25 SGST), nil ₹20"
GST_INTEREST = "TODO_VERIFY: interest 18% a year (CGST Act s.50, Notification 13/2017-CT; not read)"
PENALTY_RULES = [
    ("gstr_1", {"late_fee_per_day": "50", "max_late_fee": "2000", "annual_interest_rate": "0"},
        "TODO_VERIFY: ₹50/₹20 a day as for GSTR-3B (Notification 4/2018-CT; not read). Cap: "
        "Notification 20/2021-CT, CGST ₹1,000 up to ₹1.5 crore (₹250 nil, ₹2,500 up to "
        "₹5 crore), doubled for SGST. No tax is paid with GSTR-1, so no interest.",
    ),
    ("gstr_3b", {"late_fee_per_day": "50", "max_late_fee": "2000", "annual_interest_rate": "18"},
        f"{GST_LATE_FEE}. Cap: Notification 19/2021-CT, CGST ₹1,000 up to ₹1.5 crore (₹250 "
        f"nil, ₹2,500 up to ₹5 crore), doubled for SGST. {GST_INTEREST}",
    ),
    ("cmp_08", {"late_fee_per_day": "0", "max_late_fee": "0", "annual_interest_rate": "18"},
        f"GST portal FAQ 'Filing Form GST CMP-08' Q9: no late fee. {GST_INTEREST}",
    ),
    ("gstr_4", {"late_fee_per_day": "50", "max_late_fee": "2000", "annual_interest_rate": "18"},
        "TODO_VERIFY: ₹50/₹20 a day (Notification 73/2017-CT; not read). Cap: Notification "
        f"21/2021-CT, CGST ₹1,000 (₹250 nil), doubled for SGST. {GST_INTEREST}",
    ),
    ("tds_24q", {"late_fee_per_day": "200", "annual_interest_rate": "0"},
        "TRACES FAQ on late filing fee (tdscpc.gov.in): ₹200 a day (s.234E), at most the TDS "
        "of the statement (not stored). A late statement has no interest (that is for late "
        "deposit).",
    ),
    ("tds_26q", {"late_fee_per_day": "200", "annual_interest_rate": "0"},
        "TRACES FAQ on late filing fee (tdscpc.gov.in): ₹200 a day (s.234E), at most the TDS "
        "of the statement (not stored). A late statement has no interest (that is for late "
        "deposit).",
    ),
    ("itr", {"flat_late_fee": "5000", "annual_interest_rate": "12"},
        "incometax.gov.in, Income Tax Returns FAQ Q25: ₹5,000 (₹1,000 when income is at most "
        "₹5 lakh; s.234F, s.428 of the 2025 Act). TODO_VERIFY: interest 1% a month (s.234A; "
        "not read).",
    ),
]


def save(table, lookup, values):
    """Add the row found by `lookup`, or give the existing row the new values."""
    row = table.query.filter_by(**lookup).first()
    if row is None:
        row = table(**lookup)
        db.session.add(row)
    for column, value in values.items():
        setattr(row, column, value)


def seed():
    for number, (code, name, description, unit) in enumerate(SERVICE_CATALOG, start=1):
        # The filing a service is for: the ITR services are for "itr"; a tax audit is no filing.
        form = None
        if code.startswith("itr_"):
            form = "itr"
        elif code in ("gstr_1", "gstr_3b", "cmp_08", "gstr_4", "tds_24q", "tds_26q"):
            form = code
        save(CatalogService, {"code": code}, {"name": name, "description": description, "unit": unit,
                                              "sort_order": number, "form_code": form})
    for key, value, unit, description, source in RULE_THRESHOLDS:
        save(RuleThreshold, {"key": key, "effective_from": RULES_FROM},
             {"value": Decimal(value), "unit": unit, "description": description, "source_reference": source})
    for form, name, frequency, applicability, rule, source in OBLIGATION_TEMPLATES:
        save(ObligationTemplate, {"form_code": form, "frequency": frequency, "effective_from": RULES_FROM},
             {"name": name, "applicability": applicability, "due_date_rule": rule, "source_reference": source})
    for form, amounts, source in PENALTY_RULES:
        values = {"source_reference": source}
        for column in ("late_fee_per_day", "max_late_fee", "flat_late_fee", "annual_interest_rate"):
            values[column] = Decimal(amounts[column]) if column in amounts else None
        save(PenaltyRule, {"form_code": form, "effective_from": RULES_FROM}, values)

    # The official NIC activity codes (content/reference/nic_2008.csv; lines starting with # are notes).
    known = {nic.code for nic in NicCode.query.all()}
    with open(REPO / "content/reference/nic_2008.csv", encoding="utf-8") as file:
        for row in csv.DictReader(line for line in file if not line.startswith("#")):
            if row["code"] not in known:
                db.session.add(NicCode(code=row["code"], description=row["description"]))
                known.add(row["code"])
    db.session.flush()

    # Filings made under older rules get the current periods and due dates.
    for profile in RegulatoryProfile.query.all():
        sync_filings(profile.business_id, profile, now())
    db.session.commit()
    print("Seeded: service catalog, rule thresholds, obligation templates, penalty rules, NIC codes, "
          "filings synced to the rules")


if __name__ == "__main__":
    with app.app_context():
        if "--reset" in sys.argv:
            if "neon.tech" in app.config["SQLALCHEMY_DATABASE_URI"]:
                sys.exit("--reset is for a local database only, never the shared Neon database.")
            db.drop_all()
            db.create_all()
        seed()
