from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..models import AuditFinding, ReconciliationResult, BankTransaction
from pathlib import Path
import uuid
from ..database import get_db
from ..models import Document, Invoice
from ..models import DocumentAudit, DocumentAuditFinding
from ..services.document_audit import audit_document, compare_documents, reconcile_uploaded_documents
from ..config import settings
router=APIRouter(prefix="/documents",tags=["المستندات"])

class DocumentCompareRequest(BaseModel):
    first_document_id: int
    second_document_id: int

@router.get("")
def documents(db:Session=Depends(get_db)):
    return [{"id":x.id,"filename":x.filename,"content_type":x.content_type,"size_bytes":x.size_bytes,
             "status":x.status,"created_at":x.created_at.isoformat()} for x in db.scalars(select(Document).order_by(Document.created_at.desc())).all()]
@router.post("/upload")
async def upload(file:UploadFile=File(...),db:Session=Depends(get_db)):
    if not file.filename: raise HTTPException(400,"اسم الملف غير صالح")
    ext=Path(file.filename).suffix.lower()
    if ext not in {".pdf",".png",".jpg",".jpeg",".xlsx",".xls",".csv"}: raise HTTPException(415,"نوع الملف غير مدعوم")
    content=await file.read()
    if len(content)>settings.max_upload_mb*1024*1024: raise HTTPException(413,"حجم الملف أكبر من الحد المسموح")
    path=Path(settings.upload_dir)/f"{uuid.uuid4().hex}{ext}";path.write_bytes(content)
    doc=Document(filename=Path(file.filename).name,stored_path=str(path),content_type=file.content_type,size_bytes=len(content))
    db.add(doc);db.commit();db.refresh(doc)
    return {"message":f"تم رفع المستند {doc.filename} بنجاح.","document_id":doc.id,"status":doc.status}

@router.get("/{document_id}/file")
def document_file(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)

    if doc is None:
       raise HTTPException(404, "المستند غير موجود")

    upload_root = Path(settings.upload_dir).resolve()
    stored_path = Path(doc.stored_path).resolve()

    if upload_root not in stored_path.parents:
        raise HTTPException(403, "مسار المستند غير صالح")

    if not stored_path.is_file():
        raise HTTPException(404, "ملف المستند غير موجود")

    content_type = doc.content_type or "application/octet-stream"

    if not (
        content_type == "application/pdf"
        or content_type.startswith("image/")
    ):
        raise HTTPException(415, "نوع الملف غير مدعوم للعرض المباشر")

    return FileResponse(
        path=str(stored_path),
        media_type=content_type,
        filename=doc.filename,
        content_disposition_type="inline",
    )


@router.get("/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)

    if doc is None:
        raise HTTPException(404, "Document not found")

    upload_root = Path(settings.upload_dir).resolve()
    stored_path = Path(doc.stored_path).resolve()

    if upload_root not in stored_path.parents:
        raise HTTPException(403, "Invalid document path")

    if not stored_path.is_file():
        raise HTTPException(404, "Document file not found")

    return FileResponse(
        path=str(stored_path),
        media_type="application/octet-stream",
        filename=doc.filename,
        content_disposition_type="attachment",
    )


@router.get("/{document_id}/preview")
def preview_document(document_id: int, db: Session = Depends(get_db)):
    import pandas as pd

    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")

    upload_root = Path(settings.upload_dir).resolve()
    stored_path = Path(doc.stored_path).resolve()

    if upload_root not in stored_path.parents:
        raise HTTPException(403, "Invalid document path")

    if not stored_path.is_file():
        raise HTTPException(404, "Document file not found")

    extension = Path(doc.filename).suffix.lower()

    try:
        if extension == ".csv":
            frame = pd.read_csv(
                stored_path,
                dtype=str,
                encoding="utf-8-sig",
                sep=None,
                engine="python",
                nrows=200,
            )
            sheets = {"CSV": frame}

        elif extension in {".xlsx", ".xls"}:
            sheets = pd.read_excel(
                stored_path,
                sheet_name=None,
                dtype=str,
                nrows=200,
            )

        else:
            raise HTTPException(415, "Preview supports Excel and CSV only")

        result = []
        for sheet_name, frame in sheets.items():
            frame = frame.fillna("")
            result.append({
                "name": str(sheet_name),
                "columns": [str(column) for column in frame.columns],
                "rows": [
                    [str(value) for value in row]
                    for row in frame.values.tolist()
                ],
            })

        return {
            "document_id": doc.id,
            "filename": doc.filename,
            "sheets": result,
            "preview_limit": 200,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, f"Could not preview document: {str(exc)}")




@router.post("/{document_id}/audit")
def audit_document_route(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)

    if doc is None:
        raise HTTPException(404, "المستند غير موجود")

    upload_root = Path(settings.upload_dir).resolve()
    stored_path = Path(doc.stored_path).resolve()

    if upload_root not in stored_path.parents:
        raise HTTPException(403, "مسار المستند غير صالح")

    if not stored_path.is_file():
       raise HTTPException(404, "ملف المستند غير موجود")

    try:
        result = audit_document(stored_path)

        previous_audits = list(
            db.scalars(
                select(DocumentAudit).where(
                    DocumentAudit.document_id == document_id
                )
            ).all()
        )

        previous_ids = [item.id for item in previous_audits]

        if previous_ids:
            db.query(DocumentAuditFinding).filter(
                DocumentAuditFinding.audit_id.in_(previous_ids)
            ).delete(synchronize_session=False)

            db.query(DocumentAudit).filter(
                DocumentAudit.id.in_(previous_ids)
            ).delete(synchronize_session=False)

        audit = DocumentAudit(
            document_id=doc.id,
            status="مكتمل",
            summary=result["summary"],
            risk_level=result["risk_level"],
            risk_score=result["risk_score"],
            extracted_chars=result["extracted_chars"],
            line_count=result["line_count"],
            finding_count=len(result["findings"]),
        )

        db.add(audit)
        db.flush()

        for item in result["findings"]:
            extra_data = {
                key: item[key]
                for key in (
                    "source_type",
                    "source_sheet",
                    "source_row",
                    "financial_impact",
                    "treatment_status",
                )
                if key in item
            }

            item["extra_data"] = extra_data or None

            db.add(DocumentAuditFinding(
                audit_id=audit.id,
                title=item["title"],
                category=item["category"],
                description=item["description"],
                evidence=item["evidence"],
                recommendation=item["recommendation"],
                risk_level=item["risk_level"],
                score=item["score"],
                occurrence_count=item["occurrence_count"],
                extra_data=extra_data or None,
            ))

        doc.status = "تم التدقيق"
        db.commit()
        db.refresh(audit)

        return {
            "audit_id": audit.id,
            "document_id": doc.id,
            "filename": doc.filename,
            "status": audit.status,
            "summary": audit.summary,
            "risk_level": audit.risk_level,
            "risk_score": audit.risk_score,
            "extracted_chars": audit.extracted_chars,
            "line_count": audit.line_count,
            "finding_count": audit.finding_count,
            "created_at": audit.created_at,
            "findings": result["findings"],
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=f"تعذر تنفيذ تدقيق المستند: {str(exc)}",
        )


@router.get("/{document_id}/audit")
def get_document_audit(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)

    if doc is None:
        raise HTTPException(404, "المستند غير موجود")

    audit = db.scalars(
        select(DocumentAudit)
        .where(DocumentAudit.document_id == document_id)
        .order_by(DocumentAudit.created_at.desc())
    ).first()

    if audit is None:
        return {
            "document_id": document_id,
            "status": "لم يتم التدقيق",
            "audit": None,
            "findings": [],
        }

    findings = db.scalars(
        select(DocumentAuditFinding)
        .where(DocumentAuditFinding.audit_id == audit.id)
        .order_by(DocumentAuditFinding.id)
    ).all()

    return {
        "document_id": document_id,
        "filename": doc.filename,
        "status": audit.status,
        "audit": {
            "id": audit.id,
            "summary": audit.summary,
            "risk_level": audit.risk_level,
            "risk_score": audit.risk_score,
            "extracted_chars": audit.extracted_chars,
            "line_count": audit.line_count,
            "finding_count": audit.finding_count,
            "created_at": audit.created_at,
        },
        "findings": [
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "description": item.description,
                "evidence": item.evidence,
                "recommendation": item.recommendation,
                "risk_level": item.risk_level,
                "score": item.score,
                "occurrence_count": item.occurrence_count,
                "extra_data": item.extra_data,
            }
            for item in findings
        ],
    }



@router.post("/compare")
def compare_documents_endpoint(
    request: DocumentCompareRequest,
    db: Session = Depends(get_db),
):
    if request.first_document_id == request.second_document_id:
        raise HTTPException(
            status_code=400,
            detail="يجب اختيار مستندين مختلفين للمقارنة",
        )

    first_doc = db.get(Document, request.first_document_id)
    second_doc = db.get(Document, request.second_document_id)

    if first_doc is None or second_doc is None:
        raise HTTPException(
            status_code=404,
            detail="أحد المستندين المحددين غير موجود",
        )

    upload_root = Path(settings.upload_dir).resolve()

    first_path = Path(first_doc.stored_path).resolve()
    second_path = Path(second_doc.stored_path).resolve()

    if (
        upload_root not in first_path.parents
        or upload_root not in second_path.parents
    ):
        raise HTTPException(
            status_code=403,
            detail="مسار أحد المستندات غير صالح",
        )

    if not first_path.is_file() or not second_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="ملف أحد المستندات غير موجود",
        )

    try:
        result = reconcile_uploaded_documents(first_path, second_path)
        if result is None:
            result = compare_documents(first_path, second_path)

        return {
            "first_document": {
                "id": first_doc.id,
                "filename": first_doc.filename,
            },
            "second_document": {
                "id": second_doc.id,
                "filename": second_doc.filename,
            },
            **result,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"تعذرت مقارنة المستندين: {str(exc)}",
        )


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)

    if doc is None:
        raise HTTPException(
            status_code=404,
            detail="المستند غير موجود",
        )

    upload_root = Path(settings.upload_dir).resolve()
    stored_path = Path(doc.stored_path).resolve()

    if upload_root not in stored_path.parents:
        raise HTTPException(
            status_code=403,
            detail="مسار المستند غير صالح",
        )

    invoice_ids = list(
        db.scalars(
            select(Invoice.id).where(Invoice.document_id == document_id)
        ).all()
    )

    deleted_findings = 0
    deleted_reconciliations = 0
    deleted_invoices = 0

    try:
        if invoice_ids:
            db.query(BankTransaction).filter(
                BankTransaction.matched_invoice_id.in_(invoice_ids)
            ).update(
                {BankTransaction.matched_invoice_id: None},
                synchronize_session=False,
            )

            deleted_reconciliations = db.query(
                ReconciliationResult
            ).filter(
                ReconciliationResult.invoice_id.in_(invoice_ids)
            ).delete(synchronize_session=False)

            deleted_findings = db.query(AuditFinding).filter(
                AuditFinding.invoice_id.in_(invoice_ids)
            ).delete(synchronize_session=False)

            deleted_invoices = db.query(Invoice).filter(
                Invoice.id.in_(invoice_ids)
            ).delete(synchronize_session=False)

        db.delete(doc)
        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="تعذر حذف المستند والبيانات المرتبطة به من قاعدة البيانات"
        )

    try:
        if stored_path.is_file():
            stored_path.unlink()
    except OSError:
        pass

    return {
        "message": "تم حذف المستند والبيانات المرتبطة به بنجاح",
        "document_id": document_id,
        "deleted_invoices": deleted_invoices,
        "deleted_findings": deleted_findings,
        "deleted_reconciliation_results": deleted_reconciliations,
    }
