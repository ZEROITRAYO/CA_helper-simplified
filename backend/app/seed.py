"""The rule tables and the `flask seed` command.

The demo accounts and businesses are not made here: they are data in backend/demo_data.sql
(see the README). This file seeds the service catalog; the legal rule thresholds, the
obligation templates and the penalty rules of the 7 forms, each with its official source
(values not confirmed yet are marked TODO_VERIFY, see docs/TODO_VERIFY.md); the official NIC
activity codes from content/reference/nic_2008.csv.

Every seed function must be safe to re-run (it adds missing rows and updates the rest, so a
corrected value reaches every database on the next `flask seed`) and must not commit:
run_all_seeds() commits once at the end. Add a new table's seed function to SEEDS.
"""

import csv
import logging
from datetime import date
from decimal import Decimal

import click
from flask_migrate import upgrade
from sqlalchemy import select, text

from app import onboarding
from app.models import (
    CatalogService,
    db,
    FormCode,
    Frequency,
    NicCode,
    ObligationTemplate,
    PenaltyRule,
    RuleThreshold,
    ServiceUnit,
)
from app.utils import REPO_ROOT

log = logging.getLogger(__name__)

SERVICE_CATALOG = [
    (
        "itr_presumptive",
        "ITR filing: presumptive income (ITR-4)",
        "Income tax return for a business or profession on presumptive income.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "itr_business",
        "ITR filing: business or profession (ITR-3)",
        "Income tax return for a proprietor or professional with business income.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "itr_firm_company",
        "ITR filing: firm, LLP or company (ITR-5 / ITR-6)",
        "Income tax return for a partnership firm, LLP or company.",
        ServiceUnit.PER_RETURN,
    ),
    ("gstr_1", "GSTR-1 filing", "Return of outward supplies (sales).", ServiceUnit.PER_RETURN),
    ("gstr_3b", "GSTR-3B filing", "Summary GST return with tax payment.", ServiceUnit.PER_RETURN),
    (
        "cmp_08",
        "CMP-08 filing",
        "Statement for composition-scheme taxpayers.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "gstr_4",
        "GSTR-4 filing",
        "Annual return for composition-scheme taxpayers.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "tds_24q",
        "TDS return 24Q",
        "TDS return for tax deducted on salaries.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "tds_26q",
        "TDS return 26Q",
        "TDS return for tax deducted on other payments.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "gst_registration",
        "GST registration",
        "Getting a new GST registration.",
        ServiceUnit.ONE_TIME,
    ),
    (
        "tax_audit",
        "Tax audit",
        "Tax audit of the accounts for one financial year.",
        ServiceUnit.PER_YEAR,
    ),
    (
        "bookkeeping",
        "Bookkeeping",
        "Keeping the books of accounts up to date.",
        ServiceUnit.PER_MONTH,
    ),
    (
        "income_tax_notice",
        "Reply to an income-tax notice",
        "Reading an income-tax notice and preparing the reply.",
        ServiceUnit.PER_NOTICE,
    ),
]

# Sample prices (rupees) of the sample CAs, by email and service code. Made up for
# development, so Find a CA shows fees. The demo CA gets no prices:
# set them yourself on /ca/services.
SERVICE_FORM_CODES = {
    "itr_presumptive": FormCode.ITR,
    "itr_business": FormCode.ITR,
    "itr_firm_company": FormCode.ITR,
    "gstr_1": FormCode.GSTR_1,
    "gstr_3b": FormCode.GSTR_3B,
    "cmp_08": FormCode.CMP_08,
    "gstr_4": FormCode.GSTR_4,
    "tds_24q": FormCode.TDS_24Q,
    "tds_26q": FormCode.TDS_26Q,
}


def seed_service_catalog():
    sort_order = 1
    for code, name, description, unit in SERVICE_CATALOG:
        service = db.session.scalar(select(CatalogService).where(CatalogService.code == code))
        if service is None:
            service = CatalogService(
                code=code, name=name, description=description, unit=unit, sort_order=sort_order
            )
            db.session.add(service)
        # Set every time: databases seeded before this column existed get it too.
        service.form_code = SERVICE_FORM_CODES.get(code)
        sort_order = sort_order + 1


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
    (
        "msme.micro.max_investment",
        "25000000",
        "inr",
        "Micro: investment up to ₹2.5 crore",
        MSME_SOURCE,
    ),
    (
        "msme.micro.max_turnover",
        "100000000",
        "inr",
        "Micro: turnover up to ₹10 crore",
        MSME_SOURCE,
    ),
    (
        "msme.small.max_investment",
        "250000000",
        "inr",
        "Small: investment up to ₹25 crore",
        MSME_SOURCE,
    ),
    (
        "msme.small.max_turnover",
        "1000000000",
        "inr",
        "Small: turnover up to ₹100 crore",
        MSME_SOURCE,
    ),
    (
        "msme.medium.max_investment",
        "1250000000",
        "inr",
        "Medium: investment up to ₹125 crore",
        MSME_SOURCE,
    ),
    (
        "msme.medium.max_turnover",
        "5000000000",
        "inr",
        "Medium: turnover up to ₹500 crore",
        MSME_SOURCE,
    ),
    (
        "gst.registration.min_turnover",
        "2000000",
        "inr",
        "GST registration needed above ₹20 lakh (lower limit, for services)",
        "CBIC, 'GST - An Update' (1 May 2019), cbic-gst.gov.in: registration needed above "
        "₹20 lakh for services (₹10 lakh in Manipur, Mizoram, Nagaland, Tripura) and ₹40 lakh "
        "for goods (₹20 lakh in some states); CGST Act s.22, Notification 10/2019-CT",
    ),
    (
        "gst.qrmp.max_turnover",
        "50000000",
        "inr",
        "Quarterly returns (QRMP) allowed up to ₹5 crore",
        "GST portal FAQ 'Quarterly Return and Monthly Payment (QRMP) Scheme' "
        "(tutorial.gst.gov.in/userguide/returns/FAQs_change_profile.htm)",
    ),
    (
        "gst.composition.max_turnover",
        "15000000",
        "inr",
        "Composition scheme allowed up to ₹1.5 crore (goods)",
        "CBIC, 'GST - An Update' (1 May 2019): composition up to ₹1.5 crore for goods "
        "(₹75 lakh in special category states); CGST Act s.10, Notification 14/2019-CT",
    ),
    (
        "itr.presumptive_44ad.max_turnover",
        "20000000",
        "inr",
        "Presumptive scheme (44AD) allowed up to ₹2 crore",
        "incometax.gov.in, File ITR-4 (Sugam) FAQ Q9: s.44AD up to ₹2 crore (₹3 crore when "
        "cash receipts are at most 5%)",
    ),
    (
        "itr.audit_44ab.min_turnover",
        "10000000",
        "inr",
        "Tax audit needed above ₹1 crore",
        "incometax.gov.in, Income Tax Forms FAQ: tax audit above ₹1 crore for a business "
        "(₹10 crore when cash is at most 5%); s.44AB of the 1961 Act, s.63 of the 2025 Act",
    ),
]


def _upsert(model, lookup, values):
    """Add the row found by `lookup`, or give an existing one the current `values`."""
    stmt = select(model)
    for column, value in lookup.items():
        stmt = stmt.where(getattr(model, column) == value)
    row = db.session.scalar(stmt)
    if row is None:
        db.session.add(model(**lookup, **values))
        return
    for column, value in values.items():
        setattr(row, column, value)


def seed_rule_thresholds():
    for key, value, unit, description, source in RULE_THRESHOLDS:
        _upsert(
            RuleThreshold,
            {"key": key, "effective_from": RULES_FROM},
            {
                "value": Decimal(value),
                "unit": unit,
                "description": description,
                "source_reference": source,
            },
        )


# How each form applies and when it is due. Due-date rules (compliance_service.due_date):
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
    (
        FormCode.ITR,
        "Income tax return",
        Frequency.YEARLY,
        {},
        {
            "month": 8,
            "day": 31,
            "audit_month": 10,
            "audit_day": 31,
            "by_itr_form": {"itr_5": [7, 31]},
        },
        "incometax.gov.in, Income Tax Returns FAQ Q16 and Q24: 31 August for individuals and HUFs "
        "with business or professional income and no audit (31 July only without business "
        "income: no profile of the app), 31 October with an audit; s.139(1) of the 1961 Act, "
        "s.263 of the 2025 Act as amended by Finance Act 2026. TODO_VERIFY: ITR-5 (firms, LLPs) "
        "without audit, 31 July used (sources say 31 July or 31 August; the earlier date)",
    ),
    (
        FormCode.GSTR_1,
        "GSTR-1 (monthly)",
        Frequency.MONTHLY,
        {"gst_scheme": ["regular_monthly"]},
        {"day": 11},
        f"GST portal FAQ 'Form GSTR-1' Q10 ({GST_FAQ}GSTR_1.htm): 11th of the next month",
    ),
    (
        FormCode.GSTR_1,
        "GSTR-1 (quarterly, QRMP)",
        Frequency.QUARTERLY,
        {"gst_scheme": ["regular_qrmp"]},
        {"quarters": [[7, 13], [10, 13], [1, 13], [4, 13]]},
        f"GST portal FAQ 'Form GSTR-1' Q10 ({GST_FAQ}GSTR_1.htm): 13th after the quarter",
    ),
    (
        FormCode.GSTR_3B,
        "GSTR-3B (monthly)",
        Frequency.MONTHLY,
        {"gst_scheme": ["regular_monthly"]},
        {"day": 20},
        f"GST portal FAQ 'Form GSTR-3B' ({GST_FAQ}GSTR3B.htm): 20th of the next month",
    ),
    (
        FormCode.GSTR_3B,
        "GSTR-3B (quarterly, QRMP)",
        Frequency.QUARTERLY,
        {"gst_scheme": ["regular_qrmp"]},
        {"quarters": [[7, 22], [10, 22], [1, 22], [4, 22]]},
        f"GST portal FAQ 'Form GSTR-3B' ({GST_FAQ}GSTR3B.htm) and GSTN QRMP advisory Q28: "
        "22nd or 24th after the quarter by state; the app uses the 22nd for every state "
        "(the earlier date, as the team decided on 2026-09-29)",
    ),
    (
        FormCode.CMP_08,
        "CMP-08",
        Frequency.QUARTERLY,
        {"gst_scheme": ["composition"]},
        {"quarters": [[7, 18], [10, 18], [1, 18], [4, 18]]},
        f"GST portal FAQ 'Filing Form GST CMP-08' Q3 ({GST_FAQ}FAQs_CMP02.htm): 18th after "
        "the quarter",
    ),
    (
        FormCode.GSTR_4,
        "GSTR-4",
        Frequency.YEARLY,
        {"gst_scheme": ["composition"]},
        {"month": 6, "day": 30},
        "TODO_VERIFY: 30 June after the FY from FY 2024-25 (CGST Rules r.62 as amended by "
        "Notification 12/2024-CT, 10.07.2024; not read, the GST portal FAQ still says the "
        "30th of the month after the FY)",
    ),
    (
        FormCode.TDS_24Q,
        "TDS return 24Q (salaries)",
        Frequency.QUARTERLY,
        {"files_24q": [True]},
        {"quarters": [[7, 31], [10, 31], [1, 31], [5, 31]]},
        "incometax.gov.in, Form 138 (earlier 24Q) user manual: 31 July, 31 October, "
        "31 January, 31 May; shown as Form 138 from tax year 2026-27 (Income-tax Act 2025 "
        "s.392 and Income-tax Rules 2026; compliance_service.RENAMED_FORMS)",
    ),
    (
        FormCode.TDS_26Q,
        "TDS return 26Q (other payments)",
        Frequency.QUARTERLY,
        {"files_26q": [True]},
        {"quarters": [[7, 31], [10, 31], [1, 31], [5, 31]]},
        "incometax.gov.in, Form 140 (earlier 26Q) user manual: 31 July, 31 October, "
        "31 January, 31 May; shown as Form 140 from tax year 2026-27 (Income-tax Act 2025 "
        "s.393 and Income-tax Rules 2026; compliance_service.RENAMED_FORMS)",
    ),
]


def seed_obligation_templates():
    for form, name, frequency, applicability, rule, source in OBLIGATION_TEMPLATES:
        _upsert(
            ObligationTemplate,
            {"form_code": form, "frequency": frequency, "effective_from": RULES_FROM},
            {
                "name": name,
                "applicability": applicability,
                "due_date_rule": rule,
                "source_reference": source,
            },
        )


# One penalty rule per form: (form, amounts, source_reference). Amounts are rupees
# (annual_interest_rate is % a year); a missing amount stays empty (NULL) and the estimator
# says so. Where a fee or cap depends on turnover or income, the value for a small business
# (turnover up to ₹1.5 crore) is stored and the others are named in the source.
# docs/TODO_VERIFY.md, "Penalties", lists what each value rests on.
GST_LATE_FEE = "CBIC Circular 26/26/2017-GST: ₹50 a day (₹25 CGST + ₹25 SGST), nil ₹20"
GST_INTEREST = "TODO_VERIFY: interest 18% a year (CGST Act s.50, Notification 13/2017-CT; not read)"
PENALTY_RULES = [
    (
        FormCode.GSTR_1,
        {
            "late_fee_per_day": "50",
            "max_late_fee": "2000",
            "annual_interest_rate": "0",
        },
        "TODO_VERIFY: ₹50/₹20 a day as for GSTR-3B (Notification 4/2018-CT; not read). Cap: "
        "Notification 20/2021-CT, CGST ₹1,000 up to ₹1.5 crore (₹250 nil, ₹2,500 up to "
        "₹5 crore), doubled for SGST. No tax is paid with GSTR-1, so no interest.",
    ),
    (
        FormCode.GSTR_3B,
        {
            "late_fee_per_day": "50",
            "max_late_fee": "2000",
            "annual_interest_rate": "18",
        },
        f"{GST_LATE_FEE}. Cap: Notification 19/2021-CT, CGST ₹1,000 up to ₹1.5 crore (₹250 "
        f"nil, ₹2,500 up to ₹5 crore), doubled for SGST. {GST_INTEREST}",
    ),
    (
        FormCode.CMP_08,
        {"late_fee_per_day": "0", "max_late_fee": "0", "annual_interest_rate": "18"},
        f"GST portal FAQ 'Filing Form GST CMP-08' Q9: no late fee. {GST_INTEREST}",
    ),
    (
        FormCode.GSTR_4,
        {
            "late_fee_per_day": "50",
            "max_late_fee": "2000",
            "annual_interest_rate": "18",
        },
        "TODO_VERIFY: ₹50/₹20 a day (Notification 73/2017-CT; not read). Cap: Notification "
        f"21/2021-CT, CGST ₹1,000 (₹250 nil), doubled for SGST. {GST_INTEREST}",
    ),
    (
        FormCode.TDS_24Q,
        {"late_fee_per_day": "200", "annual_interest_rate": "0"},
        "TRACES FAQ on late filing fee (tdscpc.gov.in): ₹200 a day (s.234E), at most the TDS "
        "of the statement (not stored). A late statement has no interest (that is for late "
        "deposit).",
    ),
    (
        FormCode.TDS_26Q,
        {"late_fee_per_day": "200", "annual_interest_rate": "0"},
        "TRACES FAQ on late filing fee (tdscpc.gov.in): ₹200 a day (s.234E), at most the TDS "
        "of the statement (not stored). A late statement has no interest (that is for late "
        "deposit).",
    ),
    (
        FormCode.ITR,
        {"flat_late_fee": "5000", "annual_interest_rate": "12"},
        "incometax.gov.in, Income Tax Returns FAQ Q25: ₹5,000 (₹1,000 when income is at most "
        "₹5 lakh; s.234F, s.428 of the 2025 Act). TODO_VERIFY: interest 1% a month (s.234A; "
        "not read).",
    ),
]

PENALTY_COLUMNS = (
    "late_fee_per_day",
    "max_late_fee",
    "flat_late_fee",
    "annual_interest_rate",
)


def seed_penalty_rules():
    for form, amounts, source in PENALTY_RULES:
        values = {"source_reference": source}
        for column in PENALTY_COLUMNS:
            amount = amounts.get(column)
            values[column] = Decimal(amount) if amount is not None else None
        _upsert(PenaltyRule, {"form_code": form, "effective_from": RULES_FROM}, values)


# The official NIC activity codes: reference data, never typed by hand.
NIC_FILE = REPO_ROOT / "content" / "reference" / "nic_2008.csv"


def seed_nic_codes():
    """Add the NIC codes from content/reference/nic_2008.csv that are not in the table yet."""
    if not NIC_FILE.exists():
        log.warning("Skipping NIC codes: %s is missing", NIC_FILE)
        return

    existing = set(db.session.scalars(select(NicCode.code)))
    with open(NIC_FILE, encoding="utf-8") as handle:
        lines = []
        for line in handle:
            if not line.startswith("#"):  # the source notes at the top
                lines.append(line)
    for row in csv.DictReader(lines):
        if row["code"] not in existing:
            db.session.add(NicCode(code=row["code"], description=row["description"]))
            existing.add(row["code"])


def seed_filing_dates():
    """Give filings created earlier the dates of the rules seeded above."""
    onboarding.resync_all_filings()


# (name, function) in dependency order: users first, other data may refer to them.
SEEDS = [
    ("service catalog", seed_service_catalog),
    ("rule thresholds", seed_rule_thresholds),
    ("obligation templates", seed_obligation_templates),
    ("penalty rules", seed_penalty_rules),
    ("NIC codes", seed_nic_codes),
    ("filings synced to the rules", seed_filing_dates),  # last: needs the templates above
]


def run_all_seeds():
    """Run every seed function, then commit once. Returns the names that ran."""
    for _, seed in SEEDS:
        seed()
    db.session.commit()
    return [name for name, _ in SEEDS]


def register_commands(app):
    @app.cli.command("seed")
    def seed_command():
        """Insert or update the rule tables. Safe to re-run."""
        click.echo(f"Seeded: {', '.join(run_all_seeds())}")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="Delete every table and all data in DATABASE_URL?")
    def reset_db_command():
        """Drop every table, create them again with the migrations, then run the seed."""
        # Never on the team's shared database.
        if "neon.tech" in db.engine.url.render_as_string():
            raise click.ClickException("reset-db is for a local database only, not Neon.")
        # Dropping the whole schema also removes tables that no longer have a model.
        with db.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        upgrade()  # flask db upgrade: the migrations in backend/migrations/versions/
        click.echo(f"Seeded: {', '.join(run_all_seeds())}")
