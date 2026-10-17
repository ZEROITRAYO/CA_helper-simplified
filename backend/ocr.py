# Reading documents on our own server (never sent anywhere): the text of a PDF or photo
# (PyMuPDF + Tesseract) and the facts in it (acknowledgement number, date, form, period,
# document type, and the values to fill the registration form). A file that cannot be read
# raises ValueError with a message that says why.

import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pymupdf

STATES_FILE = Path(__file__).resolve().parent.parent / "content/reference/gst_states.json"
GST_STATES = json.loads(STATES_FILE.read_text())["states"]


# --- ocr ---------------------------------------------------------------------------------


MAX_PAGES = 3
MIN_PAGE_TEXT = 30  # a PDF page with fewer characters is treated as a scanned picture
RENDER_DPI = 200  # picture quality for scanned pages (higher = slower, more accurate)
TESSERACT_TIMEOUT_SECONDS = 30


def _read_picture(picture):
    """The text in a PNG or JPG picture, read by the tesseract program (English)."""
    if shutil.which("tesseract") is None:  # installed in the Docker image and in CI
        raise ValueError("Tesseract is not installed, so pictures cannot be read.")
    try:
        result = subprocess.run(["tesseract", "stdin", "stdout", "-l", "eng"], input=picture,
                                capture_output=True, timeout=TESSERACT_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired as error:
        raise ValueError("Reading the picture took too long.") from error
    if result.returncode != 0:
        raise ValueError("Tesseract could not read the picture.")
    return result.stdout.decode("utf-8", errors="replace")


def extract_text(data, mime_type):
    """The text of a PDF, JPG or PNG file. Raises ValueError when no text could be read.
    For a PDF: the text of the first pages; scanned pages are read as pictures."""
    if mime_type != "application/pdf":
        text = _read_picture(data)
    else:
        try:
            pdf = pymupdf.open(stream=data, filetype="pdf")
        except Exception as error:  # PyMuPDF raises several error types for broken files
            raise ValueError("The PDF could not be opened.") from error
        texts = []
        with pdf:
            for number in range(min(MAX_PAGES, pdf.page_count)):
                page = pdf[number]
                text = page.get_text()
                if len(text.strip()) < MIN_PAGE_TEXT:
                    text = _read_picture(page.get_pixmap(dpi=RENDER_DPI).tobytes("png"))
                texts.append(text)
        text = "\n".join(texts)
    if not text.strip():
        raise ValueError("No text was found in the file.")
    return text


# --- document_text -----------------------------------------------------------------------


MONTHS = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6, "JULY": 7,
    "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9,
    "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}  # fmt: skip

# How each form is named in a document ("GSTR-3B", "GSTR 3B", "Form No. 26Q", "ITR-4").
# Whole words only, so "GSTR-1A" is not GSTR-1 and "ARBITRATION" is not ITR.
FORM_PATTERNS = {
    "gstr_3b": re.compile(r"\bGSTR\s*-?\s*3B\b"),
    "gstr_1": re.compile(r"\bGSTR\s*-?\s*1\b"),
    "cmp_08": re.compile(r"\bCMP\s*-?\s*0?8\b"),
    "gstr_4": re.compile(r"\bGSTR\s*-?\s*4\b"),
    "tds_24q": re.compile(r"\b24\s*Q\b"),
    "tds_26q": re.compile(r"\b26\s*Q\b"),
    "itr": re.compile(r"\bITR\s*-?\s*(?:[1-7]|V)?\b|\bINCOME\s*TAX\s*RETURN\b"),
}

# "ARN: AA2710260123456", "Acknowledgement Number : 123456789012345", "Token No. 1234..."
ACK_NUMBER = re.compile(
    r"(?:\bARN\b|ACKNOWLEDGE?MENT\s*(?:REFERENCE\s*)?(?:NUMBER|NO\b\.?)|\bACK\.?\s*NO\b\.?"
    r"|TOKEN\s*(?:NUMBER|NO\b\.?)|(?:PROVISIONAL\s*)?RECEIPT\s*(?:NUMBER|NO\b\.?))"
    r"\s*[:\-]?\s*([A-Z0-9]{10,20})\b"
)
# A GST ARN without a label: two letters, then 13 letters or digits (e.g. AA2710260123456).
BARE_ARN = re.compile(r"\b(A[A-Z][0-9]{2}[0-9A-Z]{11})\b")
# 20/10/2026, 20-10-2026, 20.10.2026, 20-Oct-2026, 20 October 2026, 2026-10-20.
DAY_MONTH_YEAR = re.compile(
    r"\b([0-3]?[0-9])[/\-. ]([0-1]?[0-9]|[A-Z]{3,9})[/\-. ,]+(20[0-9]{2})\b"
)
YEAR_MONTH_DAY = re.compile(r"\b(20[0-9]{2})-([0-1][0-9])-([0-3][0-9])\b")
# "2026-27", "2026-2027", "2026/27".
FINANCIAL_YEAR = re.compile(r"\b(20[0-9]{2})\s*[-–/]\s*(20)?([0-9]{2})\b")
# "Q2", "Quarter 2", "Quarter: 2".
QUARTER = re.compile(r"\bQ\s*-?\s*([1-4])\b|\bQUARTER\s*[:\-]?\s*([1-4])\b")
# A GST tax period written as digits: "092026", "09/2026", "09-2026".
MONTH_YEAR_DIGITS = re.compile(r"\b(0[1-9]|1[0-2])[/\-]?(20[0-9]{2})\b")

PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
GSTIN = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")

# Words that give a document's type away. The type with the most hits wins.
TYPE_KEYWORDS = {
    "acknowledgement": ["ACKNOWLEDGEMENT", "ACKNOWLEDGMENT", "ARN", "ITR-V", "SUCCESSFULLY FILED"],
    "gst_certificate": ["REG-06", "REGISTRATION CERTIFICATE", "CERTIFICATE OF REGISTRATION"],
    "pan_card": ["PERMANENT ACCOUNT NUMBER", "INCOME TAX DEPARTMENT", "GOVT. OF INDIA"],
    "bank_statement": ["STATEMENT OF ACCOUNT", "OPENING BALANCE", "CLOSING BALANCE", "IFSC"],
    "invoice": ["TAX INVOICE", "INVOICE NO", "INVOICE NUMBER", "BILL TO", "HSN"],
    "sales_register": ["SALES REGISTER", "SALES BOOK"],
    "purchase_register": ["PURCHASE REGISTER", "PURCHASE BOOK"],
    "salary_register": ["SALARY REGISTER", "NET PAY", "BASIC PAY", "PAYSLIP"],
    "tds_challan": ["CHALLAN", "BSR CODE", "ITNS 281"],
    "certificate_of_practice": ["CERTIFICATE OF PRACTICE", "CHARTERED ACCOUNTANTS OF INDIA"],
}

# The "Constitution of Business" on a GST certificate -> our entity types.
CONSTITUTIONS = {
    "PROPRIETORSHIP": "proprietorship",
    "PARTNERSHIP": "partnership",
    "LIMITED LIABILITY PARTNERSHIP": "llp",
    "PRIVATE LIMITED COMPANY": "private_limited",
}


def _clean(text):
    """Upper case with single spaces, so patterns do not care about layout."""
    return re.sub(r"\s+", " ", text.upper())


def _dates(clean, today):
    """Every real date in the text that is not in the future."""
    found = []
    for day, month, year in DAY_MONTH_YEAR.findall(clean):
        month_number = int(month) if month.isdigit() else MONTHS.get(month)
        found.append((int(year), month_number, int(day)))
    for year, month, day in YEAR_MONTH_DAY.findall(clean):
        found.append((int(year), int(month), int(day)))
    dates = []
    for year, month, day in found:
        try:
            value = date(year, month, day)
        except (TypeError, ValueError):  # month None or impossible, e.g. 31/02
            continue
        if value <= today:
            dates.append(value)
    return dates


def guess_document_type(text):
    """The DocumentType code the text most looks like, or None when nothing matches."""
    clean = _clean(text)
    best_type, best_hits = None, 0
    for doc_type, keywords in TYPE_KEYWORDS.items():
        # Whole words only: "ARN" must not match inside "LEARNING".
        hits = sum(1 for keyword in keywords if re.search(rf"\b{re.escape(keyword)}\b", clean))
        if hits > best_hits:
            best_type, best_hits = doc_type, hits
    return best_type


def read_proof_fields(text, today):
    """The non-personal facts an acknowledgement shows, plus a guess of its type."""
    clean = _clean(text)
    # The periods are looked for without the dates, so a filing date "20/10/2026" does
    # not count as the month October.
    without_dates = YEAR_MONTH_DAY.sub(" ", DAY_MONTH_YEAR.sub(" ", clean))

    ack_number = None
    labelled = ACK_NUMBER.search(clean)
    if labelled:
        ack_number = labelled.group(1)
    else:
        bare = BARE_ARN.search(clean)
        if bare:
            ack_number = bare.group(1)

    months = set()  # month numbers named anywhere ("September", "Sep", "09/2026")
    months_with_year = set()  # "2026-09" from digit periods like "092026"
    for word in re.findall(r"[A-Z]+", without_dates):
        if word in MONTHS:
            months.add(MONTHS[word])
    for month, year in MONTH_YEAR_DIGITS.findall(without_dates):
        months.add(int(month))
        months_with_year.add(f"{year}-{month}")

    financial_years = set()
    for start, _, end in FINANCIAL_YEAR.findall(without_dates):
        if int(end) == (int(start) + 1) % 100:  # "2026-27", not "2026-10" (a date)
            financial_years.add(f"{start}-{end}")

    quarters = set()
    for first, second in QUARTER.findall(without_dates):
        quarters.add(int(first or second))

    dates = _dates(clean, today)
    return {
        "acknowledgement_no": ack_number,
        "filing_date": max(dates).isoformat() if dates else None,
        "form_codes": sorted(
            code for code, pattern in FORM_PATTERNS.items() if pattern.search(clean)
        ),
        "months": sorted(months),
        "months_with_year": sorted(months_with_year),
        "financial_years": sorted(financial_years),
        "quarters": sorted(quarters),
        "type_guess": guess_document_type(text),
    }


def read_registration(text):
    clean = _clean(text)
    found = {}
    gstin = GSTIN.search(clean)

    if gstin:
        found["gstin"] = gstin[0]
        found["pan"] = gstin[0][2:12]
        for state in GST_STATES:
            if state["code"] == gstin[0][:2]:
                found["state"] = state["name"]
    else:
        pan = PAN.search(clean)
        if pan:
            found["pan"] = pan[0]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        legal = re.search(r"LEGAL NAME\s*[:\-]?\s*(.*)", line, flags=re.IGNORECASE)
        if legal:
            value = legal.group(1) or next_line
        elif re.fullmatch(r"(?:.*/\s*)?NAME\s*:?", line, flags=re.IGNORECASE):
            value = next_line
        else:
            continue
        if value and not PAN.search(value.upper()):
            found["legal_name"] = value.strip()[:200]
            break

    if "CONSTITUTION OF BUSINESS" in clean:
        for words, entity_type in CONSTITUTIONS.items():
            if words in clean:
                found["entity_type"] = entity_type  # the longest names are checked last
    return found
