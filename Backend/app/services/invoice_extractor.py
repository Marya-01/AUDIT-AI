
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
import re
import csv
import io
import logging

import fitz
import pytesseract
import pandas as pd

from PIL import Image, ImageOps, ImageEnhance


# =========================================================
# إعدادات OCR
# =========================================================

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

OCR_LANGUAGES = "ara+eng"

logger = logging.getLogger(__name__)


# =========================================================
# أدوات مساعدة للنصوص
# =========================================================

def normalize_digits(text: str) -> str:
    """تحويل الأرقام العربية والفارسية إلى أرقام إنجليزية."""

    if not text:
        return ""

    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"

    translation = {}

    for index, digit in enumerate(arabic_digits):
        translation[ord(digit)] = str(index)

    for index, digit in enumerate(persian_digits):
        translation[ord(digit)] = str(index)

    return text.translate(translation)


def normalize_text(text: str) -> str:
    """تنظيف النص المستخرج."""

    text = normalize_digits(text or "")
    text = text.replace("\u200f", "")
    text = text.replace("\u200e", "")
    text = text.replace("\ufeff", "")

    return text.strip()


def normalize_label(text: str) -> str:
    """توحيد الكلمات العربية والإنجليزية لتسهيل البحث."""

    text = normalize_text(text).lower()

    text = re.sub(r"[\u064b-\u065f]", "", text)

    text = text.replace("أ", "ا")
    text = text.replace("إ", "ا")
    text = text.replace("آ", "ا")

    text = re.sub(r"[\s:：_\-]+", " ", text)

    return text.strip()


# =========================================================
# قراءة الصور
# =========================================================

def prepare_image(image: Image.Image) -> Image.Image:
    """تحسين الصورة قبل OCR."""

    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    image = ImageOps.grayscale(image)

    image = ImageEnhance.Contrast(image).enhance(1.8)

    return image


def extract_text_from_image(image_path: Path) -> str:
    """استخراج النص من صورة باستخدام Tesseract."""

    if not Path(TESSERACT_PATH).exists():
        raise FileNotFoundError(
            f"Tesseract غير موجود في المسار: {TESSERACT_PATH}"
        )

    with Image.open(image_path) as image:
        prepared = prepare_image(image)

        text = pytesseract.image_to_string(
            prepared,
            lang=OCR_LANGUAGES,
            config="--psm 6"
        )

    return normalize_text(text)


# =========================================================
# قراءة PDF
# =========================================================

def extract_text_from_pdf(pdf_path: Path) -> str:
    """قراءة النص من PDF مع OCR للصفحات الممسوحة."""

    all_text = []

    with fitz.open(pdf_path) as document:

        for page_number, page in enumerate(document):

            text = page.get_text("text") or ""

            # إذا لم يوجد نص كافٍ، نستخدم OCR
            if len(text.strip()) < 30:

                logger.info(
                    "استخدام OCR لصفحة PDF رقم %s",
                    page_number + 1
                )

                pix = page.get_pixmap(
                    matrix=fitz.Matrix(2.5, 2.5),
                    alpha=False
                )

                image = Image.frombytes(
                    "RGB",
                    [pix.width, pix.height],
                    pix.samples
                )

                image = prepare_image(image)

                text = pytesseract.image_to_string(
                    image,
                    lang=OCR_LANGUAGES,
                    config="--psm 6"
                )

            all_text.append(text)

    return normalize_text("\n".join(all_text))


def extract_pdf_pages(pdf_path: str | Path) -> list[dict]:
    """استخراج النص من كل صفحة في PDF مع دعم OCR للصفحات الممسوحة."""

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError("ملف PDF غير موجود")

    pages_data = []

    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):

            text = page.get_text("text") or ""

            if len(text.strip()) < 30:
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(2.5, 2.5),
                    alpha=False,
                )

                image = Image.frombytes(
                    "RGB",
                    [pix.width, pix.height],
                    pix.samples,
                )

                image = prepare_image(image)

                text = pytesseract.image_to_string(
                    image,
                    lang=OCR_LANGUAGES,
                    config="--psm 6",
                )

            pages_data.append({
                "page_number": page_number,
                "raw_text": normalize_text(text),
            })

    return pages_data
# =========================================================
# قراءة Excel و CSV
# =========================================================

def extract_text_from_excel(file_path: Path) -> str:
    """قراءة جميع أوراق Excel."""

    sheets = pd.read_excel(
        file_path,
        sheet_name=None,
        dtype=str
    )

    output = []

    for sheet_name, dataframe in sheets.items():

        output.append(f"Sheet: {sheet_name}")

        dataframe = dataframe.fillna("")

        output.append(
            dataframe.to_string(index=False)
        )

    return normalize_text("\n".join(output))


def extract_text_from_csv(file_path: Path) -> str:
    """قراءة ملف CSV مع محاولة دعم الترميزات المختلفة."""

    encodings = ["utf-8-sig", "utf-8", "cp1256", "latin1"]

    content = None

    for encoding in encodings:

        try:
            content = file_path.read_text(
                encoding=encoding
            )
            break

        except UnicodeDecodeError:
            continue

    if content is None:
        raise ValueError("تعذر قراءة ترميز ملف CSV")

    return normalize_text(content)


# =========================================================
# استخراج النص حسب نوع الملف
# =========================================================

def extract_raw_text(file_path: str | Path) -> str:
    """اختيار طريقة القراءة حسب امتداد الملف."""

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError("الملف غير موجود")

    extension = file_path.suffix.lower()

    if extension == ".pdf":
        text = extract_text_from_pdf(file_path)

    elif extension in {".png", ".jpg", ".jpeg"}:
        text = extract_text_from_image(file_path)

    elif extension in {".xlsx", ".xls"}:
        text = extract_text_from_excel(file_path)

    elif extension == ".csv":
        text = extract_text_from_csv(file_path)

    else:
        raise ValueError(
            f"نوع الملف غير مدعوم: {extension}"
        )

    if not text.strip():
        raise ValueError(
            "لم يتمكن النظام من استخراج نص من الملف"
        )

    return text


# =========================================================
# استخراج رقم الفاتورة
# =========================================================

def extract_invoice_number(text: str) -> str | None:
    lines = [line.strip() for line in normalize_text(text).splitlines()]

    labels = re.compile(
        r"^(?:invoice\s*(?:number|no\.?|#)|bill\s*(?:number|no\.?)|"
        r"\u0631\u0642\u0645\s*\u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629|"
        r"\u0641\u0627\u062a\u0648\u0631\u0629\s*\u0631\u0642\u0645)"
        r"\s*[:?#\-]?\s*(.*)$",
        re.IGNORECASE,
    )

    for index, line in enumerate(lines):
        match = labels.match(line)
        if not match:
            continue

        value = match.group(1).strip()
        if not value and index + 1 < len(lines):
            value = lines[index + 1].strip()

        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_\- ]{2,40}", value):
            if not value.upper().startswith("DRAFT"):
                return value

    return None


def extract_supplier_name(text: str) -> str | None:
    lines = [line.strip() for line in normalize_text(text).splitlines()]

    labels = re.compile(
        r"^(?:supplier|vendor|seller|"
        r"\u0627\u0633\u0645\s*\u0627\u0644\u0645\u0648\u0631\u062f|"
        r"\u0627\u0644\u0645\u0648\u0631\u062f|"
        r"\u0627\u0644\u0628\u0627\u0626\u0639)"
        r"\s*[:?\-]?\s*(.*)$",
        re.IGNORECASE,
    )

    ignored = re.compile(
        r"^(?:document\s*reference|reference|invoice|sample|"
        r"document|date|invoice\s*number|description|test\s*label)\b",
        re.IGNORECASE,
    )

    for index, line in enumerate(lines):
        match = labels.match(line)
        if not match:
            continue

        value = match.group(1).strip()
        if not value and index + 1 < len(lines):
            value = lines[index + 1].strip()

        if value and not ignored.match(value):
            if not re.fullmatch(r"[\d\s./\-]+", value):
                return value[:200]

    return None


def extract_invoice_date(text: str) -> date | None:

    patterns = [
        r"(?:invoice\s*date|date|"
        r"تاريخ\s*الفاتورة|التاريخ|تاريخ)"
        r"\s*[:：\-]?\s*"
        r"(\d{1,4}[./\-]\d{1,2}[./\-]\d{1,4})"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if not match:
            continue

        value = match.group(1)

        parts = re.split(r"[./\-]", value)

        try:

            if len(parts[0]) == 4:

                year = int(parts[0])
                month = int(parts[1])
                day = int(parts[2])

            else:

                first = int(parts[0])
                second = int(parts[1])
                third = int(parts[2])

                # التاريخ بصيغة DD/MM/YYYY
                if third >= 1000:
                    day = first
                    month = second
                    year = third

                else:
                    continue

            return date(year, month, day)

        except (ValueError, IndexError):
            continue

    return None


# =========================================================
# استخراج المبلغ والضريبة
# =========================================================

def parse_decimal(value: str) -> Decimal | None:

    value = normalize_digits(value)

    value = value.replace(",", "")
    value = value.replace("٬", "")
    value = value.replace("٫", ".")

    value = re.sub(
        r"[^\d.\-]",
        "",
        value
    )

    try:

        if not value:
            return None

        return Decimal(value)

    except InvalidOperation:
        return None



def extract_amount(text: str) -> Decimal | None:
    lines = [line.strip() for line in normalize_text(text).splitlines()]

    labels = re.compile(
        r"^(?:invoice\s*total|grand\s*total|total\s*due|"
        r"total\s*amount|net\s*total|"
        r"\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a\s*\u0627\u0644\u0645\u0633\u062a\u062d\u0642|"
        r"\u0627\u0644\u0645\u0628\u0644\u063a\s*\u0627\u0644\u0645\u0633\u062a\u062d\u0642|"
        r"\u0625\u062c\u0645\u0627\u0644\u064a\s*\u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629|"
        r"\u0627\u0644\u0645\u062c\u0645\u0648\u0639\s*\u0627\u0644\u0643\u0644\u064a|total)"
        r"\s*[:?\-]?\s*(.*)$",
        re.IGNORECASE,
    )

    number_pattern = re.compile(
        r"(?<!\d)(\d[\d,\u066c\u066b]*(?:\.\d{1,3})?)(?!\d)"
    )

    for index in range(len(lines) - 1, -1, -1):
        match = labels.match(lines[index])
        if not match:
            continue

        candidates = [match.group(1).strip()]
        if index + 1 < len(lines):
            candidates.append(lines[index + 1].strip())

        for candidate in candidates:
            if "%" in candidate:
                continue

            number_match = number_pattern.search(candidate)
            if number_match:
                value = parse_decimal(number_match.group(1))
                if value is not None and value >= 0:
                    return value

    return None


def extract_tax_amount(text: str) -> Decimal | None:
    lines = [line.strip() for line in normalize_text(text).splitlines()]

    labels = re.compile(
        r"^(?:tax(?:\s*\([^)]*\))?|vat|"
        r"\u0645\u0628\u0644\u063a\s*\u0627\u0644\u0636\u0631\u064a\u0628\u0629|"
        r"\u0636\u0631\u064a\u0628\u0629\s*\u0627\u0644\u0642\u064a\u0645\u0629\s*\u0627\u0644\u0645\u0636\u0627\u0641\u0629|"
        r"\u0627\u0644\u0642\u064a\u0645\u0629\s*\u0627\u0644\u0645\u0636\u0627\u0641\u0629|"
        r"\u0627\u0644\u0636\u0631\u064a\u0628\u0629)"
        r"\s*[:?\-]?\s*(.*)$",
        re.IGNORECASE,
    )

    number_pattern = re.compile(
        r"(?<!\d)(\d[\d,\u066c\u066b]*(?:\.\d{1,3})?)(?!\d)"
    )

    for index, line in enumerate(lines):
        match = labels.match(line)
        if not match:
            continue

        candidates = [match.group(1).strip()]
        if index + 1 < len(lines):
            candidates.append(lines[index + 1].strip())

        for candidate in candidates:
            if "%" in candidate:
                continue

            number_match = number_pattern.search(candidate)
            if number_match:
                value = parse_decimal(number_match.group(1))
                if value is not None and value >= 0:
                    return value

    return None


def extract_currency(text: str) -> str | None:

    currency_patterns = [
        (r"\bYER\b|ر\.?\s*ي|ريال\s*يمني", "YER"),
        (r"\bSAR\b|ر\.?\s*س|ريال\s*سعودي", "SAR"),
        (r"\bUSD\b|\$", "USD"),
        (r"\bEUR\b|€", "EUR"),
        (r"\bAED\b|درهم\s*إماراتي", "AED"),
    ]

    for pattern, currency in currency_patterns:

        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        ):
            return currency

    return None


# =========================================================
# الدالة الرئيسية
# =========================================================

def extract_invoice_data(file_path: str | Path) -> dict:
    """
    استخراج بيانات الفاتورة من ملف.

    ترجع البيانات بصيغة Dictionary جاهزة
    للاستخدام داخل FastAPI.
    """

    file_path = Path(file_path)

    raw_text = extract_raw_text(file_path)

    invoice_number = extract_invoice_number(raw_text)
    supplier_name = extract_supplier_name(raw_text)
    invoice_date = extract_invoice_date(raw_text)
    amount = extract_amount(raw_text)
    tax_amount = extract_tax_amount(raw_text)
    currency = extract_currency(raw_text)

    missing_fields = []

    if not invoice_number:
        missing_fields.append("invoice_number")

    if not supplier_name:
        missing_fields.append("supplier_name")

    if not invoice_date:
        missing_fields.append("invoice_date")

    if amount is None:
        missing_fields.append("amount")

    return {
        "invoice_number": invoice_number,
        "supplier_name": supplier_name,
        "invoice_date": (
            invoice_date.isoformat()
            if invoice_date
            else None
        ),
        "amount": (
            float(amount)
            if amount is not None
            else None
        ),
        "tax_amount": (
            float(tax_amount)
            if tax_amount is not None
            else None
        ),
        "currency": currency,
        "missing_fields": missing_fields,
        "is_complete": len(missing_fields) == 0,
        "raw_text": raw_text,
    }


def extract_pdf_invoice_records(file_path: str | Path) -> list[dict]:
    """
    استخراج سجلات الفواتير من صفحات ملف PDF.
    يحتفظ كل سجل برقم الصفحة المصدر.
    """

    file_path = Path(file_path)
    pages = extract_pdf_pages(file_path)
    records = []

    for page in pages:
        raw_text = page.get("raw_text") or ""

        invoice_number = extract_invoice_number(raw_text)
        supplier_name = extract_supplier_name(raw_text)
        invoice_date = extract_invoice_date(raw_text)
        amount = extract_amount(raw_text)
        tax_amount = extract_tax_amount(raw_text)
        currency = extract_currency(raw_text)

        # التحقق من وجود أدلة كافية قبل اعتبار الصفحة مرشحة لاحتواء فاتورة.
        evidence_count = sum([
            bool(invoice_number),
            bool(supplier_name),
            bool(invoice_date),
            amount is not None,
        ])

        if evidence_count < 2 or not (invoice_number or supplier_name):
            continue

        missing_fields = []

        if not invoice_number:
            missing_fields.append("invoice_number")

        if not supplier_name:
            missing_fields.append("supplier_name")

        if not invoice_date:
            missing_fields.append("invoice_date")

        if amount is None:
            missing_fields.append("amount")

        records.append({
            "invoice_number": invoice_number,
            "supplier_name": supplier_name,
            "invoice_date": (
                invoice_date.isoformat()
                if invoice_date
                else None
            ),
            "amount": float(amount) if amount is not None else None,
            "tax_amount": (
                float(tax_amount)
                if tax_amount is not None
                else None
            ),
            "currency": currency,
            "missing_fields": missing_fields,
            "is_complete": len(missing_fields) == 0,
            "source_page": page["page_number"],
            "raw_text": raw_text,
        })

    return records


def extract_tabular_records(file_path: str | Path) -> list[dict]:
    """Extract row-level records from CSV and Excel files."""

    file_path = Path(file_path)
    extension = file_path.suffix.lower()
    records = []

    if extension == ".csv":
        dataframe = pd.read_csv(file_path, dtype=str).fillna("")
        sheets = [("CSV", dataframe)]

    elif extension in {".xlsx", ".xls"}:
        sheets = list(
            pd.read_excel(
                file_path,
                sheet_name=None,
                dtype=str
            ).items()
        )
        sheets = [
            (sheet_name, dataframe.fillna(""))
            for sheet_name, dataframe in sheets
        ]

    else:
        raise ValueError("Unsupported tabular file format")

    aliases = {
    "invoice_number": {
        "invoice number",
        "invoice no",
        "invoice id",
        "رقم الفاتورة",
        "رقم الفاتوره",
    },
    "supplier_name": {
        "supplier",
        "supplier name",
        "vendor",
        "vendor name",
        "اسم المورد",
        "المورد",
    },
    "invoice_date": {
        "date",
        "invoice date",
        "التاريخ",
        "تاريخ الفاتورة",
    },
    "amount": {
        "amount",
        "total",
        "invoice total",
        "grand total",
        "المبلغ",
        "الإجمالي",
        "الاجمالي",
    },
    "tax_amount": {
        "tax",
        "tax amount",
        "vat",
        "الضريبة",
        "مبلغ الضريبة",
    },
    "reference": {
        "reference",
        "ref",
        "reference number",
        "المرجع",
        "رقم المرجع",
    },
    "description": {
        "description",
        "details",
        "الوصف",
        "التفاصيل",
    },
}

    for sheet_name, dataframe in sheets:
        normalized_columns = {
            normalize_label(str(column)): column
            for column in dataframe.columns
        }

        column_map = {}

        for field, names in aliases.items():
            for alias in names:
                normalized_alias = normalize_label(alias)
                if normalized_alias in normalized_columns:
                    column_map[field] = normalized_columns[normalized_alias]
                    break

        if "amount" not in column_map:
            continue

        for row_index, row in dataframe.iterrows():
            def cell(field):
                column = column_map.get(field)
                if column is None:
                    return None
                value = row.get(column)
                if pd.isna(value):
                    return None
                value = normalize_text(str(value))
                return value or None

            raw_amount = cell("amount")
            amount = parse_decimal(raw_amount) if raw_amount else None

            if amount is None:
                continue

            invoice_date = None
            date_value = cell("invoice_date")
            if date_value:
                invoice_date = extract_invoice_date(date_value)

                if invoice_date is None:
                    try:
                        invoice_date = pd.to_datetime(
                            date_value,
                            errors="raise"
                        ).date()
                    except (ValueError, TypeError):
                        pass

            invoice_number = cell("invoice_number")
            supplier_name = cell("supplier_name")
            description = cell("description")
            reference = cell("reference")
            tax_amount = cell("tax_amount")

            record_type = (
                "payment_candidate"
                if amount < 0
                else "invoice_candidate"
            )

            missing_fields = []

            if not invoice_number:
                missing_fields.append("invoice_number")
            if not supplier_name:
                missing_fields.append("supplier_name")
            if not invoice_date:
                missing_fields.append("invoice_date")

            records.append({
                "invoice_number": invoice_number,
                "supplier_name": supplier_name,
                "invoice_date": (
                    invoice_date.isoformat()
                    if invoice_date else None
                ),
                "amount": float(amount),
                "tax_amount": (
                    float(parse_decimal(tax_amount))
                    if tax_amount and parse_decimal(tax_amount) is not None
                    else None
                ),
                "currency": None,
                "reference": reference,
                "description": description,
                "record_type": record_type,
                "missing_fields": missing_fields,
                "is_complete": len(missing_fields) == 0,
                "source_sheet": sheet_name,
                "source_row": int(row_index) + 2,
            })

    return records


def extract_journal_records(file_path: str | Path) -> list[dict]:
    """Extract accounting journal rows or bank ledger rows."""

    file_path = Path(file_path)
    extension = file_path.suffix.lower()

    if extension == ".csv":
        dataframe = pd.read_csv(
            file_path,
            dtype=str,
            sep=None,
            engine="python",
            encoding="utf-8-sig",
            header=None,
        ).fillna("")
        sheets = [("CSV", dataframe)]

    elif extension in {".xlsx", ".xls"}:
        sheets = [
            (name, frame.fillna(""))
            for name, frame in pd.read_excel(
                file_path,
                sheet_name=None,
                dtype=str,
                header=None,
            ).items()
        ]
    else:
        raise ValueError("Unsupported ledger file format")

    aliases = {
        "journal_id": {
            "journal number", "journal no", "journal id",
            "entry number", "entry no",
            "\u0631\u0642\u0645 \u0627\u0644\u0642\u064a\u062f",
            "\u0631\u0642\u0645 \u0627\u0644\u0642\u064a\u062f \u0627\u0644\u0645\u062d\u0627\u0633\u0628\u064a",
            "\u0631\u0642\u0645 \u0627\u0644\u062d\u0631\u0643\u0629",
        },
        "date": {
            "date", "transaction date", "posting date",
            "\u0627\u0644\u062a\u0627\u0631\u064a\u062e",
            "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0642\u064a\u062f",
        },
        "description": {
            "description", "details", "narration",
            "\u0627\u0644\u0628\u064a\u0627\u0646",
            "\u0627\u0644\u0648\u0635\u0641",
            "\u0627\u0644\u0628\u064a\u0627\u0646 \u0627\u0644\u062a\u0641\u0635\u064a\u0644\u064a",
        },
        "debit": {
            "debit", "debit amount",
            "\u0645\u062f\u064a\u0646",
            "\u0627\u0644\u0645\u062f\u064a\u0646",
            "\u0645\u0628\u0644\u063a \u0645\u062f\u064a\u0646",
            "\u0627\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u062f\u064a\u0646",
        },
        "credit": {
            "credit", "credit amount",
            "\u062f\u0627\u0626\u0646",
            "\u0627\u0644\u062f\u0627\u0626\u0646",
            "\u0645\u0628\u0644\u063a \u062f\u0627\u0626\u0646",
            "\u0627\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u062f\u0627\u0626\u0646",
        },
        "reference": {
            "reference", "ref", "transaction id",
            "document number", "document no",
            "\u0631\u0642\u0645 \u0627\u0644\u0645\u0633\u062a\u0646\u062f",
            "\u0631\u0642\u0645 \u0627\u0644\u0648\u062b\u064a\u0642\u0629",
        },
        "currency": {
            "currency",
            "\u0627\u0644\u0639\u0645\u0644\u0629",
        },
        "account_code": {
            "account code", "account number",
            "\u0631\u0645\u0632 \u0627\u0644\u062d\u0633\u0627\u0628",
            "\u0631\u0642\u0645 \u0627\u0644\u062d\u0633\u0627\u0628",
        },
        "account_name": {
            "account name",
            "\u0627\u0633\u0645 \u0627\u0644\u062d\u0633\u0627\u0628",
            "\u0627\u0644\u062d\u0633\u0627\u0628",
        },
    }


    # Detect the actual table header within the first 30 rows.
    bank_header_aliases = {
        "date": {"date", "transaction date", "posting date"},
        "description": {"description", "details", "narration"},
        "debit": {"debit", "withdrawal", "money out"},
        "credit": {"credit", "deposit", "money in"},
        "reference": {"reference", "ref", "transaction id"},
    }

    prepared_sheets = []

    for sheet_name, raw_frame in sheets:
        journal_header_index = None
        bank_header_index = None

        for candidate_index in range(min(len(raw_frame), 30)):
            values = raw_frame.iloc[candidate_index].tolist()

            column_lookup = {
                normalize_label(str(value)): position
                for position, value in enumerate(values)
                if value is not None and str(value).strip()
            }

            journal_selected = {}
            for field, names in aliases.items():
                for alias in names:
                    key = normalize_label(alias)
                    if key in column_lookup:
                        journal_selected[field] = column_lookup[key]
                        break

            if {"journal_id", "debit", "credit"}.issubset(journal_selected):
                journal_header_index = candidate_index
                break

            bank_selected = {}
            for field, names in bank_header_aliases.items():
                for alias in names:
                    key = normalize_label(alias)
                    if key in column_lookup:
                        bank_selected[field] = column_lookup[key]
                        break

            if (
                bank_header_index is None
                and {
                    "date", "description", "debit",
                    "credit", "reference"
                }.issubset(bank_selected)
            ):
                bank_header_index = candidate_index

        header_index = (
            journal_header_index
            if journal_header_index is not None
            else bank_header_index
        )

        if header_index is None:
            continue

        header_values = raw_frame.iloc[header_index].tolist()
        dataframe = raw_frame.iloc[header_index + 1:].copy()

        dataframe.columns = [
            str(value).strip()
            if value is not None and str(value).strip()
            else f"Unnamed: {position}"
            for position, value in enumerate(header_values)
        ]

        prepared_sheets.append((sheet_name, dataframe.fillna("")))

    sheets = prepared_sheets

    records = []

    for sheet_name, dataframe in sheets:
        column_map = {
            normalize_label(str(column)): column
            for column in dataframe.columns
        }

        selected = {}

        for field, names in aliases.items():
            for alias in names:
                key = normalize_label(alias)
                if key in column_map:
                    selected[field] = column_map[key]
                    break

        journal_mode = {
            "journal_id", "debit", "credit"
        }.issubset(selected)

        if journal_mode:
            for row_index, row in dataframe.iterrows():

                def journal_cell(field):
                    column = selected.get(field)
                    if column is None:
                        return ""

                    value = row.get(column)

                    if pd.isna(value):
                        return ""

                    return normalize_text(str(value)).strip()

                journal_id = journal_cell("journal_id")
                debit_text = journal_cell("debit")
                credit_text = journal_cell("credit")

                row_values = [
                    normalize_label(str(value))
                    for value in row.tolist()
                    if value is not None and str(value).strip()
                ]

                if not any(row_values):
                    continue

                if not journal_id and any(
                    marker in " ".join(row_values)
                    for marker in ("\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a", "\u0627\u0644\u0645\u062c\u0645\u0648\u0639", "total")
                ):
                    continue

                if not journal_id and not debit_text and not credit_text:
                    continue

                debit = (
                    parse_decimal(debit_text)
                    if debit_text else Decimal("0")
                )
                credit = (
                    parse_decimal(credit_text)
                    if credit_text else Decimal("0")
                )

                amounts_valid = debit is not None and credit is not None
                errors = []

                if not journal_id:
                    errors.append("missing_journal_id")

                if not amounts_valid:
                    errors.append("invalid_amount")

                debit_value = (
                    debit if debit is not None else Decimal("0")
                )
                credit_value = (
                    credit if credit is not None else Decimal("0")
                )

                if amounts_valid:
                    if debit_value < 0 or credit_value < 0:
                        errors.append("negative_amount")

                    if debit_value > 0 and credit_value > 0:
                        errors.append("both_debit_and_credit")

                    if debit_value == 0 and credit_value == 0:
                        errors.append("zero_amount")

                records.append({
                    "ledger_type": "journal",
                    "is_valid": not errors,
                    "amounts_valid": amounts_valid,
                    "errors": errors,
                    "journal_id": journal_id or None,
                    "transaction_date": journal_cell("date") or None,
                    "reference": journal_cell("reference") or None,
                    "description": journal_cell("description")[:250],
                    "account_code": journal_cell("account_code") or None,
                    "account_name": journal_cell("account_name") or None,
                    "currency": journal_cell("currency") or None,
                    "debit": debit_value,
                    "credit": credit_value,
                    "source_sheet": sheet_name,
                    "source_row": int(row_index) + 1,
                })

            continue

        bank_aliases = {
            "date": {"date", "transaction date", "posting date"},
            "description": {"description", "details", "narration"},
            "debit": {"debit", "withdrawal", "money out"},
            "credit": {"credit", "deposit", "money in"},
            "reference": {"reference", "ref", "transaction id"},
        }

        selected_bank = {}

        for field, names in bank_aliases.items():
            for alias in names:
                key = normalize_label(alias)
                if key in column_map:
                    selected_bank[field] = column_map[key]
                    break

        required_columns = {
            "date", "description", "debit", "credit", "reference"
        }

        if not required_columns.issubset(selected_bank):
            continue

        for row_index, row in dataframe.iterrows():

            def cell(field):
                value = row.get(selected_bank[field])

                if pd.isna(value):
                    return ""

                return normalize_text(str(value)).strip()

            date_text = cell("date")
            description = cell("description")
            reference = cell("reference")
            debit_text = cell("debit")
            credit_text = cell("credit")

            debit = (
                parse_decimal(debit_text)
                if debit_text else Decimal("0")
            )
            credit = (
                parse_decimal(credit_text)
                if credit_text else Decimal("0")
            )

            errors = []

            parsed_date = pd.to_datetime(
                date_text,
                errors="coerce",
            ) if date_text else None

            transaction_date = (
                parsed_date.date()
                if parsed_date is not None and not pd.isna(parsed_date)
                else None
            )

            if transaction_date is None:
                errors.append("invalid_date")

            if not reference:
                errors.append("missing_reference")

            if not description:
                errors.append("missing_description")

            if debit is None or credit is None:
                errors.append("invalid_amount")

            debit = debit or Decimal("0")
            credit = credit or Decimal("0")

            if debit < 0 or credit < 0:
                errors.append("negative_debit_or_credit")

            if debit > 0 and credit > 0:
                errors.append("both_debit_and_credit")

            if debit == 0 and credit == 0:
                errors.append("zero_amount")

            if errors:
                records.append({
                    "is_valid": False,
                    "errors": errors,
                    "source_sheet": sheet_name,
                    "source_row": int(row_index) + 1,
                    "reference": reference or None,
                })
                continue

            direction = "debit" if debit > 0 else "credit"
            amount = debit if debit > 0 else credit

            records.append({
                "is_valid": True,
                "reference": reference,
                "description": description[:250],
                "transaction_date": transaction_date.isoformat(),
                "amount": float(amount),
                "direction": direction,
                "source_sheet": sheet_name,
                "source_row": int(row_index) + 1,
            })

    return records


def extract_ledger_records(file_path: str | Path) -> list[dict]:
    """Extract bank ledger rows without treating them as invoices."""

    file_path = Path(file_path)
    extension = file_path.suffix.lower()

    if extension == ".csv":
        dataframe = pd.read_csv(
            file_path,
            dtype=str,
            sep=None,
            engine="python",
            encoding="utf-8-sig",
        ).fillna("")
        sheets = [("CSV", dataframe)]

    elif extension in {".xlsx", ".xls"}:
        sheets = [
            (name, frame.fillna(""))
            for name, frame in pd.read_excel(
                file_path,
                sheet_name=None,
                dtype=str,
            ).items()
        ]

    else:
        raise ValueError("Unsupported ledger file format")

    aliases = {
        "date": {"date", "transaction date", "posting date"},
        "description": {"description", "details", "narration"},
        "debit": {"debit", "withdrawal", "money out"},
        "credit": {"credit", "deposit", "money in"},
        "reference": {"reference", "ref", "transaction id"},
    }

    records = []

    for sheet_name, dataframe in sheets:
        column_map = {
            normalize_label(str(column)): column
            for column in dataframe.columns
        }

        selected = {}
        for field, names in aliases.items():
            for alias in names:
                key = normalize_label(alias)
                if key in column_map:
                    selected[field] = column_map[key]
                    break

        required_columns = {"date", "description", "debit", "credit", "reference"}
        if not required_columns.issubset(selected):
            continue

        for row_index, row in dataframe.iterrows():
            def cell(field):
                value = row.get(selected[field])
                if pd.isna(value):
                    return ""
                return normalize_text(str(value)).strip()

            date_text = cell("date")
            description = cell("description")
            reference = cell("reference")
            debit_text = cell("debit")
            credit_text = cell("credit")

            debit = parse_decimal(debit_text) if debit_text else Decimal("0")
            credit = parse_decimal(credit_text) if credit_text else Decimal("0")

            errors = []

            parsed_date = pd.to_datetime(
                date_text,
                errors="coerce",
            ) if date_text else None

            transaction_date = (
                parsed_date.date()
                if parsed_date is not None and not pd.isna(parsed_date)
                else None
            )

            if transaction_date is None:
                errors.append("invalid_date")

            if not reference:
                errors.append("missing_reference")

            if not description:
                errors.append("missing_description")

            if debit is None or credit is None:
                errors.append("invalid_amount")

            debit = debit or Decimal("0")
            credit = credit or Decimal("0")

            if debit < 0 or credit < 0:
                errors.append("negative_debit_or_credit")

            if debit > 0 and credit > 0:
                errors.append("both_debit_and_credit")

            if debit == 0 and credit == 0:
                errors.append("zero_amount")

            if errors:
                records.append({
                    "is_valid": False,
                    "errors": errors,
                    "source_sheet": sheet_name,
                    "source_row": int(row_index) + 2,
                    "reference": reference or None,
                })
                continue

            direction = "debit" if debit > 0 else "credit"
            amount = debit if debit > 0 else credit

            records.append({
                "is_valid": True,
                "reference": reference,
                "description": description[:250],
                "transaction_date": transaction_date.isoformat(),
                "amount": float(amount),
                "direction": direction,
                "source_sheet": sheet_name,
                "source_row": int(row_index) + 2,
            })

    return records
