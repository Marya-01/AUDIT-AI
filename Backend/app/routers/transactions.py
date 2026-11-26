from pathlib import Path
from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from ..models import BankTransaction, Document
from ..config import settings
from ..services.invoice_extractor import extract_ledger_records


router = APIRouter(
    prefix="/transactions",
    tags=["المعاملات البنكية"],
)


@router.get("")
def transactions(
    search: str = "",
    status: str | None = None,
    db: Session = Depends(get_db),
):
    q = select(BankTransaction)

    if search:
        q = q.where(
            (BankTransaction.reference.ilike(f"%{search}%"))
            | (BankTransaction.description.ilike(f"%{search}%"))
        )

    if status:
        q = q.where(BankTransaction.status == status)

    rows = db.scalars(
        q.order_by(BankTransaction.transaction_date.desc())
    ).all()

    return [
        {
            "id": x.id,
            "reference": x.reference,
            "description": x.description,
            "date": x.transaction_date.isoformat(),
            "amount": float(x.amount),
            "direction": x.direction,
            "status": x.status,
        }
        for x in rows
    ]


@router.post("/upload-ledger")
async def upload_ledger(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    original_name = Path(file.filename).name
    extension = Path(original_name).suffix.lower()

    if extension not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(
            status_code=415,
            detail="Ledger upload supports CSV and Excel only.",
        )

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    max_size = settings.max_upload_mb * 1024 * 1024

    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the maximum upload size.",
        )

    upload_directory = Path(settings.upload_dir)
    upload_directory.mkdir(parents=True, exist_ok=True)

    stored_path = upload_directory / f"{uuid.uuid4().hex}{extension}"
    stored_path.write_bytes(content)

    try:
        records = extract_ledger_records(stored_path)

        if not records:
            raise HTTPException(
                status_code=422,
                detail="No ledger records found. Check the column headers.",
            )

        existing_references = set(
            db.execute(
                select(BankTransaction.reference)
            ).scalars().all()
        )

        seen_references = set()
        saved = []
        duplicates = []
        invalid = []

        document = Document(
            filename=original_name,
            stored_path=str(stored_path),
            content_type=file.content_type,
            size_bytes=len(content),
            status="تم الرفع",
        )

        db.add(document)
        db.flush()

        for record in records:
            if not record.get("is_valid"):
                invalid.append({
                    "source_row": record.get("source_row"),
                    "errors": record.get("errors", []),
                })
                continue

            reference = record["reference"]

            if (
                reference in existing_references
                or reference in seen_references
            ):
                duplicates.append({
                    "reference": reference,
                    "source_row": record.get("source_row"),
                })
                continue

            seen_references.add(reference)

            transaction = BankTransaction(
                reference=reference,
                description=record["description"],
                transaction_date=__import__("datetime").date.fromisoformat(
                    record["transaction_date"]
                ),
                amount=Decimal(str(record["amount"])),
                direction=record["direction"],
                status="غير مطابق",
            )

            db.add(transaction)

            saved.append({
                "reference": reference,
                "source_row": record.get("source_row"),
                "direction": record["direction"],
                "amount": record["amount"],
                "date": record["transaction_date"],
            })

        db.commit()

        return {
            "message": "Ledger import completed.",
            "document_id": document.id,
            "filename": original_name,
            "total_extracted": len(records),
            "saved_count": len(saved),
            "duplicate_count": len(duplicates),
            "invalid_count": len(invalid),
            "saved_transactions": saved,
            "duplicates": duplicates,
            "invalid_rows": invalid,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ledger import failed: {type(exc).__name__}",
        ) from exc
