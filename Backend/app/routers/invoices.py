
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pathlib import Path
from datetime import date
from decimal import Decimal
import uuid
import logging
import hashlib

from ..database import get_db
from ..models import Invoice, Document
from ..config import settings
from ..services.invoice_extractor import (
    extract_invoice_data,
    extract_pdf_invoice_records,
    extract_tabular_records,
)
from ..services import run_duplicate_audit


router = APIRouter(
    prefix="/invoices",
    tags=["الفواتير"],
)

class ReviewInvoiceRequest(BaseModel):
    action: str


logger = logging.getLogger(__name__)


# =========================================================
# قائمة الفواتير
# =========================================================

class InvoiceUpdateRequest(BaseModel):
    invoice_number: str | None = None
    supplier_name: str | None = None
    invoice_date: date | None = None
    amount: Decimal | None = None
    tax_amount: Decimal | None = None
    currency: str | None = None
    raw_text: str | None = None

@router.get("")
def list_invoices(
    search: str = "",
    status: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
):
    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="رقم الصفحة يجب أن يكون أكبر من صفر",
        )

    query = select(Invoice)

    if search:
        query = query.where(
            (Invoice.invoice_number.ilike(f"%{search}%"))
            | (Invoice.supplier_name.ilike(f"%{search}%"))
        )

    if status:
        query = query.where(Invoice.status == status)

    rows = db.scalars(
        query.order_by(Invoice.invoice_date.desc())
        .offset((page - 1) * 50)
        .limit(50)
    ).all()

    return [
        {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "supplier": invoice.supplier_name,
            "date": invoice.invoice_date.isoformat(),
            "amount": float(invoice.amount),
            "status": invoice.status,
            "risk_level": invoice.risk_level,
            "document_id": invoice.document_id,
        }
        for invoice in rows
    ]


# =========================================================
# التحقق من أن الملف فاتورة
# =========================================================

def is_invoice_document(
    raw_text: str,
    extracted_data: dict,
) -> bool:

    text = (raw_text or "").lower()

    report_keywords = [
        "تقرير تدقيق",
        "تقرير مالي",
        "audit report",
        "financial report",
        "audit ai",
    ]

    if any(keyword in text for keyword in report_keywords):
        return False

    invoice_keywords = [
        "فاتورة",
        "الفاتورة",
        "فاتورة ضريبية",
        "invoice",
        "tax invoice",
        "فاتوره",
    ]

    if any(keyword in text for keyword in invoice_keywords):
        return True

    return bool(
        extracted_data.get("invoice_number")
        and extracted_data.get("supplier_name")
        and extracted_data.get("amount") is not None
    )


# =========================================================
# حساب بصمة الملف SHA-256
# =========================================================

def calculate_file_hash(file_path: Path) -> str:

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            sha256.update(chunk)

    return sha256.hexdigest()


# =========================================================
# تحويل مسار المستند إلى مسار فعلي
# =========================================================

def resolve_document_path(stored_path: str) -> Path:

    path = Path(stored_path)

    if not path.is_absolute():
        path = Path.cwd() / path

    return path.resolve()


# =========================================================
# رفع الفاتورة ومعالجة المسودات
# =========================================================

@router.post("/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    stored_path = None

    try:

        # -------------------------------------------------
        # التحقق من اسم الملف
        # -------------------------------------------------

        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="اسم الملف غير صالح",
            )

        original_name = Path(file.filename).name
        extension = Path(original_name).suffix.lower()

        allowed_extensions = {
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".xlsx",
            ".xls",
            ".csv",
        }

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=415,
                detail="نوع الملف غير مدعوم",
            )

        # -------------------------------------------------
        # قراءة الملف
        # -------------------------------------------------

        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="الملف فارغ",
            )

        max_size = settings.max_upload_mb * 1024 * 1024

        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail="حجم الملف أكبر من الحد المسموح",
            )

        # -------------------------------------------------
        # حفظ الملف باسم UUID
        # -------------------------------------------------

        upload_directory = Path(settings.upload_dir)

        upload_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        stored_path = (
            upload_directory
            / f"{uuid.uuid4().hex}{extension}"
        )

        stored_path.write_bytes(content)

        # -------------------------------------------------
        # حساب بصمة الملف
        # -------------------------------------------------

        file_hash = calculate_file_hash(stored_path)

        # -------------------------------------------------
        # استخراج البيانات
        # -------------------------------------------------

        extracted = extract_invoice_data(
            str(stored_path)
        )

        raw_text = extracted.get("raw_text", "")

        # -------------------------------------------------
        # التحقق من نوع المستند
        # -------------------------------------------------

        if not is_invoice_document(
            raw_text,
            extracted,
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "لم يتم التعرف على الملف باعتباره فاتورة. "
                    "يرجى رفع فاتورة واضحة تحتوي على بياناتها الأساسية."
                ),
            )

        invoice_number = extracted.get("invoice_number")
        supplier_name = extracted.get("supplier_name")
        extracted_amount = extracted.get("amount")
        extracted_date = extracted.get("invoice_date")
        extracted_tax_amount = extracted.get("tax_amount")
        extracted_currency = extracted.get("currency")

        missing_fields = extracted.get(
            "missing_fields",
            [],
        )

        # -------------------------------------------------
        # البحث عن المستند نفسه باستخدام SHA-256
        # -------------------------------------------------

        documents = db.scalars(
            select(Document)
        ).all()

        same_document = None

        for old_document in documents:

            try:

                old_path = resolve_document_path(
                    old_document.stored_path
                )

                if not old_path.exists():
                    continue

                old_hash = calculate_file_hash(
                    old_path
                )

                if old_hash == file_hash:
                    same_document = old_document
                    break

            except OSError:

                logger.warning(
                    "تعذر فحص المستند رقم %s",
                    old_document.id,
                )

        # -------------------------------------------------
        # معالجة المستند الموجود سابقًا
        # -------------------------------------------------

        if same_document:

            existing_invoice = db.scalar(
                select(Invoice).where(
                    Invoice.document_id
                    == same_document.id
                )
            )

            # ---------------------------------------------
            # المستند مرتبط بفاتورة موجودة
            # ---------------------------------------------

            if existing_invoice:

                is_draft = (
                    existing_invoice.invoice_number.startswith(
                        "DRAFT-"
                    )
                    or "مسودة"
                    in existing_invoice.status
                )

                # -----------------------------------------
                # الفاتورة ليست مسودة
                # -----------------------------------------

                if not is_draft:

                    db.rollback()

                    if stored_path.exists():
                        stored_path.unlink()

                    return {
                        "message": (
                            "هذا المستند موجود مسبقًا في النظام."
                        ),
                        "duplicate": True,
                        "invoice": {
                            "id": existing_invoice.id,
                            "invoice_number": (
                                existing_invoice.invoice_number
                            ),
                            "supplier": (
                                existing_invoice.supplier_name
                            ),
                            "date": (
                                existing_invoice.invoice_date.isoformat()
                            ),
                            "amount": float(
                                existing_invoice.amount
                            ),
                            "status": existing_invoice.status,
                            "document_id": (
                                existing_invoice.document_id
                            ),
                        },
                    }

                # -----------------------------------------
                # المسودة موجودة: فحص رقم الفاتورة
                # -----------------------------------------

                if invoice_number:

                    duplicate_invoice = db.scalar(
                        select(Invoice).where(
                            Invoice.invoice_number
                            == invoice_number,
                            Invoice.id
                            != existing_invoice.id,
                        )
                    )

                    if duplicate_invoice:

                        raise HTTPException(
                            status_code=409,
                            detail=(
                                f"رقم الفاتورة {invoice_number} "
                                "موجود في سجل آخر."
                            ),
                        )

                # -----------------------------------------
                # تحديث بيانات المستند
                # -----------------------------------------

                old_path = resolve_document_path(
                    same_document.stored_path
                )

                same_document.filename = original_name
                same_document.stored_path = str(
                    stored_path.resolve()
                )
                same_document.content_type = (
                    file.content_type
                )
                same_document.size_bytes = len(content)
                same_document.status = (
                    "تمت إعادة معالجة المستند"
                )

                # -----------------------------------------
                # تحديث بيانات الفاتورة
                # -----------------------------------------

                if invoice_number:

                    existing_invoice.invoice_number = (
                        invoice_number
                    )

                if supplier_name:

                    existing_invoice.supplier_name = (
                        str(supplier_name)[:200]
                    )

                if extracted_date:

                    try:

                        existing_invoice.invoice_date = (
                            date.fromisoformat(
                                str(extracted_date)
                            )
                        )

                    except ValueError:

                        logger.warning(
                            "تاريخ الفاتورة غير صالح"
                        )

                if extracted_amount is not None:

                    existing_invoice.amount = Decimal(
                        str(extracted_amount)
                    )

                if extracted_tax_amount is not None:
                    existing_invoice.tax_amount = Decimal(
                        str(extracted_tax_amount)
                    )

                if extracted_currency:
                    existing_invoice.currency = str(
                        extracted_currency
                    )[:10]

                existing_invoice.raw_text = raw_text

                existing_invoice.status = (
                    "بانتظار المراجعة"
                    if extracted.get("is_complete")
                    else "مسودة - تحتاج مراجعة"
                )

                # -----------------------------------------
                # حفظ التحديث
                # -----------------------------------------

                db.commit()

                db.refresh(existing_invoice)
                db.refresh(same_document)

                # -----------------------------------------
                # حذف الملف القديم بعد نجاح الحفظ
                # -----------------------------------------

                if (
                    old_path.exists()
                    and old_path != stored_path.resolve()
                ):

                    try:
                        old_path.unlink()

                    except OSError:

                        logger.warning(
                            "تعذر حذف الملف القديم: %s",
                            old_path,
                        )

                # -----------------------------------------
                # إرجاع نتيجة التحديث
                # -----------------------------------------

                return {
                    "message": (
                        "تم تحديث المسودة الموجودة "
                        "وإعادة استخراج بياناتها."
                    ),
                    "updated_existing_draft": True,
                    "extraction": {
                        "invoice_number": (
                            extracted.get("invoice_number")
                        ),
                        "supplier_name": (
                            extracted.get("supplier_name")
                        ),
                        "invoice_date": (
                            extracted.get("invoice_date")
                        ),
                        "amount": (
                            extracted.get("amount")
                        ),
                        "tax_amount": (
                            extracted.get("tax_amount")
                        ),
                        "currency": (
                            extracted.get("currency")
                        ),
                        "missing_fields": missing_fields,
                        "is_complete": (
                            extracted.get("is_complete")
                        ),
                    },
                    "invoice": {
                        "id": existing_invoice.id,
                        "invoice_number": (
                            existing_invoice.invoice_number
                        ),
                        "supplier": (
                            existing_invoice.supplier_name
                        ),
                        "date": (
                            existing_invoice.invoice_date.isoformat()
                        ),
                        "amount": float(
                            existing_invoice.amount
                        ),
                        "status": existing_invoice.status,
                        "risk_level": (
                            existing_invoice.risk_level
                        ),
                        "document_id": (
                            existing_invoice.document_id
                        ),
                    },
                }

        # -------------------------------------------------
        # فحص رقم الفاتورة المكرر في مستند آخر
        # -------------------------------------------------

        if invoice_number:

            existing_invoice = db.scalar(
                select(Invoice).where(
                    Invoice.invoice_number
                    == invoice_number
                )
            )

            if existing_invoice:

                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"رقم الفاتورة {invoice_number} "
                        "موجود مسبقًا في النظام."
                    ),
                )

        # -------------------------------------------------
        # إنشاء رقم مؤقت عند عدم استخراج الرقم
        # -------------------------------------------------

        if not invoice_number:

            invoice_number = (
                f"DRAFT-{uuid.uuid4().hex[:12].upper()}"
            )

        # -------------------------------------------------
        # المورد
        # -------------------------------------------------

        if not supplier_name:

            supplier_name = (
                "مورد غير محدد - يحتاج مراجعة"
            )

        supplier_name = str(
            supplier_name
        )[:200]

        # -------------------------------------------------
        # التاريخ
        # -------------------------------------------------

        invoice_date = date.today()

        if extracted_date:

            try:

                invoice_date = date.fromisoformat(
                    str(extracted_date)
                )

            except ValueError:

                invoice_date = date.today()

        # -------------------------------------------------
        # المبلغ
        # -------------------------------------------------

        if extracted_amount is not None:

            amount = Decimal(
                str(extracted_amount)
            )

        else:

            amount = Decimal("0.00")

        # -------------------------------------------------
        # حالة الفاتورة
        # -------------------------------------------------

        if extracted.get("is_complete"):

            invoice_status = "بانتظار المراجعة"

        else:

            invoice_status = (
                "مسودة - تحتاج مراجعة"
            )

        # -------------------------------------------------
        # استخدام المستند الموجود إن لم تكن له فاتورة
        # -------------------------------------------------

        if same_document:

            document = same_document

            document.filename = original_name
            document.stored_path = str(
                stored_path.resolve()
            )
            document.content_type = (
                file.content_type
            )
            document.size_bytes = len(content)
            document.status = (
                "تم رفع الملف واستخراج البيانات"
            )

        else:

            document = Document(
                filename=original_name,
                stored_path=str(
                    stored_path.resolve()
                ),
                content_type=file.content_type,
                size_bytes=len(content),
                status=(
                    "تم رفع الملف واستخراج البيانات"
                ),
            )

            db.add(document)
            db.flush()

        # -------------------------------------------------
        # إنشاء الفاتورة
        # -------------------------------------------------

        invoice = Invoice(
            invoice_number=invoice_number,
            supplier_name=supplier_name,
            invoice_date=invoice_date,
            amount=amount,
            tax_amount=(
                Decimal(str(extracted_tax_amount))
                if extracted_tax_amount is not None
                else None
            ),
            currency=(
                str(extracted_currency)[:10]
                if extracted_currency
                else None
            ),
            raw_text=raw_text,
            status=invoice_status,
            risk_level="غير محدد",
            document_id=document.id,
        )

        db.add(invoice)

        # -------------------------------------------------
        # حفظ البيانات
        # -------------------------------------------------

        db.commit()

        db.refresh(document)
        db.refresh(invoice)

        # -------------------------------------------------
        # نتيجة الرفع
        # -------------------------------------------------

        return {
            "message": (
                "تم رفع الفاتورة واستخراج بياناتها بنجاح."
                if extracted.get("is_complete")
                else (
                    "تم رفع الفاتورة، لكنها تحتاج "
                    "إلى مراجعة البيانات الناقصة."
                )
            ),
            "extraction": {
                "invoice_number": (
                    extracted.get("invoice_number")
                ),
                "supplier_name": (
                    extracted.get("supplier_name")
                ),
                "invoice_date": (
                    extracted.get("invoice_date")
                ),
                "amount": (
                    extracted.get("amount")
                ),
                "tax_amount": (
                    extracted.get("tax_amount")
                ),
                "currency": (
                    extracted.get("currency")
                ),
                "missing_fields": missing_fields,
                "is_complete": (
                    extracted.get("is_complete")
                ),
            },
            "invoice": {
                "id": invoice.id,
                "invoice_number": (
                    invoice.invoice_number
                ),
                "supplier": invoice.supplier_name,
                "date": (
                    invoice.invoice_date.isoformat()
                ),
                "amount": float(invoice.amount),
                "status": invoice.status,
                "risk_level": invoice.risk_level,
                "document_id": invoice.document_id,
            },
            "document": {
                "id": document.id,
                "filename": document.filename,
                "status": document.status,
            },
        }

    # =====================================================
    # معالجة الأخطاء
    # =====================================================

    except HTTPException:

        db.rollback()

        if stored_path and stored_path.exists():

            try:
                stored_path.unlink()

            except OSError:
                logger.warning(
                    "تعذر حذف الملف المؤقت: %s",
                    stored_path,
                )

        raise

    except IntegrityError:

        db.rollback()

        if stored_path and stored_path.exists():

            try:
                stored_path.unlink()

            except OSError:
                logger.warning(
                    "تعذر حذف الملف المؤقت: %s",
                    stored_path,
                )

        raise HTTPException(
            status_code=409,
            detail=(
                "تعذر حفظ الفاتورة بسبب "
                "تكرار رقمها أو تعارض في البيانات."
            ),
        )

    except Exception:

        db.rollback()

        if stored_path and stored_path.exists():

            try:
                stored_path.unlink()

            except OSError:
                logger.warning(
                    "تعذر حذف الملف المؤقت: %s",
                    stored_path,
                )

        logger.exception(
            "Invoice upload or extraction failed"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "حدث خطأ أثناء رفع الفاتورة "
                "أو استخراج بياناتها."
            ),
        )


# =========================================================
# تفاصيل الفاتورة: جلب فاتورة واحدة
# =========================================================

@router.get("/{invoice_id}")
def get_invoice_details(
    invoice_id: int,
    db: Session = Depends(get_db),
):
    invoice = db.get(Invoice, invoice_id)

    if invoice is None:
        raise HTTPException(
            status_code=404,
            detail="الفاتورة غير موجودة.",
        )

    document = (
        db.get(Document, invoice.document_id)
        if invoice.document_id
        else None
    )

    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "supplier_id": invoice.supplier_id,
        "supplier": invoice.supplier_name,
        "date": (
            invoice.invoice_date.isoformat()
            if invoice.invoice_date
            else None
        ),
        "amount": (
            float(invoice.amount)
            if invoice.amount is not None
            else 0.0
        ),
        "tax_amount": (
            float(invoice.tax_amount)
            if invoice.tax_amount is not None
            else None
        ),
        "currency": invoice.currency,
        "raw_text": invoice.raw_text,
        "status": invoice.status,
        "risk_level": invoice.risk_level,
        "document_id": invoice.document_id,
        "document": (
            {
                "id": document.id,
                "filename": document.filename,
                "content_type": document.content_type,
                "size_bytes": document.size_bytes,
            }
            if document
            else None
        ),
        "created_at": (
            invoice.created_at.isoformat()
            if invoice.created_at
            else None
        ),
    }

@router.put("/{invoice_id}")
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdateRequest,
    db: Session = Depends(get_db),
):
    COMPLETED = "\u0645\u0643\u062a\u0645\u0644\u0629"
    REJECTED = "\u0645\u0631\u0641\u0648\u0636\u0629"

    invoice = db.get(Invoice, invoice_id)

    if invoice is None:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found.",
        )

    if invoice.status in {COMPLETED, REJECTED}:
        raise HTTPException(
            status_code=409,
            detail="Finalized invoices cannot be edited.",
        )

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=400,
            detail="No fields were provided for update.",
        )

    if "invoice_number" in changes:
        value = changes["invoice_number"]

        if value is None or not value.strip():
            raise HTTPException(
                status_code=422,
                detail="Invoice number cannot be empty.",
            )

        changes["invoice_number"] = value.strip()[:80]

    if "supplier_name" in changes:
        value = changes["supplier_name"]

        if value is None or not value.strip():
            raise HTTPException(
                status_code=422,
                detail="Supplier name cannot be empty.",
            )

        changes["supplier_name"] = value.strip()[:200]

    if "amount" in changes:
        value = changes["amount"]

        if value is None or value < 0:
            raise HTTPException(
                status_code=422,
                detail="Amount must be zero or greater.",
            )

    if "tax_amount" in changes:
        value = changes["tax_amount"]

        if value is not None and value < 0:
            raise HTTPException(
                status_code=422,
                detail="Tax amount must be zero or greater.",
            )

    if "currency" in changes:
        value = changes["currency"]

        if value is not None:
            changes["currency"] = value.strip()[:10] or None

    for field, value in changes.items():
        setattr(invoice, field, value)

    try:
        db.commit()
        db.refresh(invoice)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Invoice number already exists.",
        )

    return {
        "message": "Invoice updated successfully.",
        "invoice": {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "supplier": invoice.supplier_name,
            "date": (
                invoice.invoice_date.isoformat()
                if invoice.invoice_date
                else None
            ),
            "amount": (
                float(invoice.amount)
                if invoice.amount is not None
                else 0.0
            ),
            "tax_amount": (
                float(invoice.tax_amount)
                if invoice.tax_amount is not None
                else None
            ),
            "currency": invoice.currency,
            "raw_text": invoice.raw_text,
            "status": invoice.status,
            "risk_level": invoice.risk_level,
            "document_id": invoice.document_id,
        },
    }

@router.post("/{invoice_id}/review")
def review_invoice(
    invoice_id: int,
    payload: ReviewInvoiceRequest,
    db: Session = Depends(get_db),
):
    PENDING = "\u0628\u0627\u0646\u062a\u0638\u0627\u0631 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629"
    IN_REVIEW = "\u0642\u064a\u062f \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629"
    DRAFT = "\u0645\u0633\u0648\u062f\u0629 - \u062a\u062d\u062a\u0627\u062c \u0645\u0631\u0627\u062c\u0639\u0629"
    REJECTED = "\u0645\u0631\u0641\u0648\u0636\u0629"
    COMPLETED = "\u0645\u0643\u062a\u0645\u0644\u0629"

    invoice = db.get(Invoice, invoice_id)

    if invoice is None:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found.",
        )

    action = payload.action.strip().lower()

    if action not in {"approve", "reject"}:
        raise HTTPException(
            status_code=422,
            detail="Action must be approve or reject.",
        )

    if invoice.status in {COMPLETED, REJECTED}:
        raise HTTPException(
            status_code=409,
            detail="This invoice has already been finalized.",
        )

    if action == "approve":
        if invoice.status not in {PENDING, IN_REVIEW, DRAFT}:
            raise HTTPException(
                status_code=409,
                detail="Only pending or in-review invoices can be approved.",
            )

        invoice.status = COMPLETED

    else:
        if invoice.status not in {PENDING, IN_REVIEW, DRAFT}:
            raise HTTPException(
                status_code=409,
                detail="This invoice cannot be rejected in its current state.",
            )

        invoice.status = REJECTED

    db.commit()
    db.refresh(invoice)

    return {
        "message": (
            "Invoice approved successfully."
            if action == "approve"
            else "Invoice rejected successfully."
        ),
        "invoice": {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "supplier": invoice.supplier_name,
            "date": (
                invoice.invoice_date.isoformat()
                if invoice.invoice_date
                else None
            ),
            "amount": (
                float(invoice.amount)
                if invoice.amount is not None
                else 0.0
            ),
            "tax_amount": (
                float(invoice.tax_amount)
                if invoice.tax_amount is not None
                else None
            ),
            "currency": invoice.currency,
            "status": invoice.status,
            "risk_level": invoice.risk_level,
            "document_id": invoice.document_id,
        },
    }


# BATCH_INVOICE_UPLOAD_ENDPOINT
@router.post("/upload-batch")
async def upload_invoices_batch(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    stored_path = None

    try:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Invalid filename.",
            )

        original_name = Path(file.filename).name
        extension = Path(original_name).suffix.lower()

        allowed_extensions = {".pdf", ".xlsx", ".xls", ".csv"}

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=415,
                detail="Batch upload supports PDF, Excel and CSV only.",
            )

        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

        max_size = settings.max_upload_mb * 1024 * 1024

        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail="File exceeds the maximum upload size.",
            )

        upload_directory = Path(settings.upload_dir)
        upload_directory.mkdir(parents=True, exist_ok=True)

        stored_path = upload_directory / (
            f"{uuid.uuid4().hex}{extension}"
        )
        stored_path.write_bytes(content)

        if extension == ".pdf":
            records = extract_pdf_invoice_records(str(stored_path))
        else:
            records = extract_tabular_records(str(stored_path))

        if not isinstance(records, list):
            raise ValueError("Extractor returned an invalid result.")

        document = Document(
            filename=original_name,
            stored_path=str(stored_path),
            content_type=file.content_type,
            size_bytes=len(content),
            status="\u062a\u0645 \u0627\u0644\u0631\u0641\u0639",
        )
        db.add(document)
        db.flush()

        saved_invoices = []
        needs_review = []
        excluded_payments = 0

        for index, record in enumerate(records):
            if not isinstance(record, dict):
                needs_review.append({
                    "record_index": index + 1,
                    "reason": "Invalid extracted record.",
                })
                continue

            if record.get("record_type") == "payment_candidate":
                excluded_payments += 1
                continue

            invoice_number = record.get("invoice_number")
            supplier_name = record.get("supplier_name")
            invoice_date_value = record.get("invoice_date")
            amount_value = record.get("amount")

            missing = []

            if not invoice_number or not str(invoice_number).strip():
                missing.append("invoice_number")

            if not supplier_name or not str(supplier_name).strip():
                missing.append("supplier_name")

            if not invoice_date_value:
                missing.append("invoice_date")

            if amount_value is None:
                missing.append("amount")

            if len(str(invoice_number or "")) > 80:
                missing.append("invoice_number_too_long")

            if len(str(supplier_name or "")) > 200:
                missing.append("supplier_name_too_long")

            if missing:
                needs_review.append({
                    "record_index": index + 1,
                    "source_page": record.get("source_page"),
                    "source_sheet": record.get("source_sheet"),
                    "source_row": record.get("source_row"),
                    "invoice_number": invoice_number,
                    "supplier_name": supplier_name,
                    "missing_fields": missing,
                    "extracted_missing_fields": record.get("missing_fields", []),
                    "raw_text": record.get("raw_text"),
                })
                continue

            try:
                if isinstance(invoice_date_value, date):
                    parsed_date = invoice_date_value
                else:
                    parsed_date = date.fromisoformat(
                        str(invoice_date_value)[:10]
                    )

                parsed_amount = Decimal(str(amount_value))

                if not parsed_amount.is_finite():
                    raise ValueError("Invalid amount.")

                tax_value = record.get("tax_amount")
                parsed_tax = (
                    Decimal(str(tax_value))
                    if tax_value is not None
                    else None
                )

                if parsed_tax is not None and not parsed_tax.is_finite():
                    raise ValueError("Invalid tax amount.")

            except (ValueError, TypeError, ArithmeticError):
                needs_review.append({
                    "record_index": index + 1,
                    "source_page": record.get("source_page"),
                    "source_sheet": record.get("source_sheet"),
                    "source_row": record.get("source_row"),
                    "invoice_number": invoice_number,
                    "supplier_name": supplier_name,
                    "missing_fields": ["invalid_date_or_amount"],
                    "raw_text": record.get("raw_text"),
                })
                continue

            invoice = Invoice(
                invoice_number=str(invoice_number).strip(),
                supplier_name=str(supplier_name).strip(),
                invoice_date=parsed_date,
                amount=parsed_amount,
                tax_amount=parsed_tax,
                currency=record.get("currency"),
                raw_text=(
                    record.get("raw_text")
                    or record.get("description")
                ),
                status="\u0642\u064a\u062f \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
                risk_level="\u0645\u0646\u062e\u0641\u0636",
                document_id=document.id,
            )

            db.add(invoice)
            saved_invoices.append({
                "invoice": invoice,
                "source_page": record.get("source_page"),
                "source_sheet": record.get("source_sheet"),
                "source_row": record.get("source_row"),
            })

        db.commit()

        for item in saved_invoices:
            db.refresh(item["invoice"])

        invoice_ids = [
            item["invoice"].id
            for item in saved_invoices
        ]

        duplicate_result = {
            "findings_created": 0,
            "findings": [],
        }

        if invoice_ids:
            try:
                findings = run_duplicate_audit(db, invoice_ids)

                duplicate_result = {
                    "findings_created": len(findings),
                    "findings": [
                        {
                            "id": finding.id,
                            "invoice_id": finding.invoice_id,
                            "title": finding.title,
                            "category": finding.category,
                            "risk_level": finding.risk_level,
                            "score": finding.score,
                            "potential_impact": float(
                                finding.potential_impact
                            ),
                            "status": finding.status,
                        }
                        for finding in findings
                    ],
                }

            except Exception:
                logger.exception(
                    "Duplicate audit failed after batch import."
                )
                duplicate_result["error"] = (
                    "Invoices were saved, but duplicate audit failed."
                )

        return {
            "message": "Batch import completed.",
            "document": {
                "id": document.id,
                "filename": document.filename,
            },
            "total_extracted": len(records),
            "invoices_saved": len(saved_invoices),
            "payments_excluded": excluded_payments,
            "records_needing_review": len(needs_review),
            "invoices": [
                {
                    "id": item["invoice"].id,
                    "invoice_number": item["invoice"].invoice_number,
                    "supplier_name": item["invoice"].supplier_name,
                    "invoice_date": item["invoice"].invoice_date.isoformat(),
                    "amount": float(item["invoice"].amount),
                    "tax_amount": (
                        float(item["invoice"].tax_amount)
                        if item["invoice"].tax_amount is not None
                        else None
                    ),
                    "document_id": item["invoice"].document_id,
                    "source_page": item["source_page"],
                    "source_sheet": item["source_sheet"],
                    "source_row": item["source_row"],
                }
                for item in saved_invoices
            ],
            "needs_review": needs_review,
            "duplicate_audit": duplicate_result,
        }

    except HTTPException:
        db.rollback()
        if stored_path and stored_path.exists():
            stored_path.unlink()
        raise

    except Exception:
        db.rollback()
        logger.exception("Batch invoice upload failed.")

        if stored_path and stored_path.exists():
            stored_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Batch invoice processing failed.",
        )
