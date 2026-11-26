
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from ..models import (
    AuditFinding,
    Document,
    DocumentAudit,
    DocumentAuditFinding,
)
from ..services import scan_risks

router = APIRouter(
    prefix="/risks",
    tags=["كشف المخاطر"],
)


@router.get("")
def risks(db: Session = Depends(get_db)):

    # نتائج المخاطر القديمة المرتبطة بالفواتير
    invoice_rows = db.scalars(
        select(AuditFinding).order_by(
            AuditFinding.created_at.desc()
        )
    ).all()

    invoice_findings = [
        {
            "id": x.id,
            "title": x.title,
            "category": x.category,
            "description": x.description,
            "risk_level": x.risk_level,
            "score": x.score,
            "potential_impact": float(x.potential_impact or 0),
            "invoice_id": x.invoice_id,
            "status": x.status,
            "source_type": "invoice",
            "document_name": None,
            "evidence": None,
            "recommendation": None,
            "occurrence_count": None,
            "created_at": x.created_at,
        }
        for x in invoice_rows
    ]

    # نتائج تدقيق المستندات المحفوظة
    document_rows = db.execute(
        select(
            DocumentAuditFinding,
            DocumentAudit,
            Document,
        )
        .join(
            DocumentAudit,
            DocumentAuditFinding.audit_id == DocumentAudit.id,
        )
        .join(
            Document,
            DocumentAudit.document_id == Document.id,
        )
        .order_by(
            DocumentAuditFinding.created_at.desc()
        )
    ).all()

    document_findings = [
        {
            "id": f"document-finding-{finding.id}",
            "title": finding.title,
            "category": finding.category,
            "description": finding.description,
            "risk_level": finding.risk_level,
            "score": finding.score,
            "potential_impact": None,
            "invoice_id": None,
            "status": "نتيجة تدقيق مستند",
            "source_type": "document",
            "document_name": document.filename,
            "evidence": finding.evidence,
            "recommendation": finding.recommendation,
            "occurrence_count": finding.occurrence_count,
            "created_at": finding.created_at,
        }
        for finding, audit, document in document_rows
    ]

    # دمج النتائج وترتيبها من الأحدث إلى الأقدم
    all_findings = invoice_findings + document_findings

    all_findings.sort(
        key=lambda item: item["created_at"],
        reverse=True,
    )

    # تحويل التاريخ إلى نص مناسب للـ API
    for item in all_findings:
        item["created_at"] = (
            item["created_at"].isoformat()
            if item["created_at"]
            else None
        )

    return all_findings


@router.post("/scan")
def scan(db: Session = Depends(get_db)):

    rows = scan_risks(db)

    counts = {
        "duplicate_invoice": 0,
        "unusual_amount": 0,
        "supplier_anomaly": 0,
    }

    for finding in rows:
        if finding.category in counts:
            counts[finding.category] += 1

    return {
        "message": "اكتمل فحص المخاطر بنجاح.",
        "findings_created": len(rows),
        "duplicate_invoice_findings": counts["duplicate_invoice"],
        "unusual_amount_findings": counts["unusual_amount"],
        "supplier_anomaly_findings": counts["supplier_anomaly"],
    }
