from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from ..models import AuditFinding, Invoice
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import run_duplicate_audit


router = APIRouter(
    prefix="/audits",
    tags=["تدقيق الفواتير المكررة"],
)


class DuplicateAuditRequest(BaseModel):
    invoice_ids: list[int] = Field(min_length=1)


@router.post("/duplicate")
def duplicate_audit(
    payload: DuplicateAuditRequest,
    db: Session = Depends(get_db),
):
    try:
        findings = run_duplicate_audit(
            db,
            payload.invoice_ids,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "message": "تم إكمال تدقيق الفواتير المكررة بنجاح.",
        "invoice_ids": payload.invoice_ids,
        "findings_created": len(findings),
        "findings": [
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "description": item.description,
                "risk_level": item.risk_level,
                "score": item.score,
                "potential_impact": float(item.potential_impact),
                "invoice_id": item.invoice_id,
                "status": item.status,
            }
            for item in findings
        ],
    }

@router.get("/duplicate/export")
def export_duplicate_audit(
    invoice_ids: list[int] = Query(...),
    db: Session = Depends(get_db),
):
    if not invoice_ids:
        raise HTTPException(
            status_code=400,
            detail="يجب تحديد فاتورة واحدة على الأقل.",
        )

    findings = (
        db.query(AuditFinding, Invoice)
        .join(Invoice, AuditFinding.invoice_id == Invoice.id)
        .filter(
            AuditFinding.category == "duplicate_invoice",
            AuditFinding.invoice_id.in_(invoice_ids),
        )
        .order_by(AuditFinding.created_at.desc())
        .all()
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "تدقيق المكررات"

    headers = [
        "\u0631\u0642\u0645 \u0627\u0644\u0646\u062a\u064a\u062c\u0629",
        "\u0631\u0642\u0645 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629",
        "\u0631\u0642\u0645 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629 \u0627\u0644\u0645\u0633\u062c\u0644",
        "\u0627\u0644\u0645\u0648\u0631\u062f",
        "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629",
        "\u0627\u0644\u0645\u0628\u0644\u063a",
        "\u0627\u0644\u0639\u0645\u0644\u0629",
        "\u0645\u0633\u062a\u0648\u0649 \u0627\u0644\u0645\u062e\u0627\u0637\u0631",
        "\u062f\u0631\u062c\u0629 \u0627\u0644\u062a\u0634\u0627\u0628\u0647",
        "\u0627\u0644\u0623\u062b\u0631 \u0627\u0644\u0645\u062d\u062a\u0645\u0644",
        "\u0639\u0646\u0648\u0627\u0646 \u0627\u0644\u0646\u062a\u064a\u062c\u0629",
        "\u062a\u0641\u0627\u0635\u064a\u0644 \u0648\u0633\u0628\u0628 \u0627\u0644\u062a\u0643\u0631\u0627\u0631",
    ]

    sheet.append(headers)

    for finding, invoice in findings:
        sheet.append([
            finding.id,
            invoice.id,
            invoice.invoice_number or "",
            invoice.supplier_name or "",
            invoice.invoice_date.isoformat() if invoice.invoice_date else "",
            float(invoice.amount or 0),
            invoice.currency or "",
            finding.risk_level or "",
            finding.score or 0,
            float(finding.potential_impact or 0),
            finding.title or "",
            finding.description or "",
        ])

    header_fill = PatternFill(
        fill_type="solid",
        fgColor="1F4E78",
    )

    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    for column_cells in sheet.columns:
        max_length = max(
            len(str(cell.value or ""))
            for cell in column_cells
        )
        column_letter = get_column_letter(column_cells[0].column)
        sheet.column_dimensions[column_letter].width = min(
            max(max_length + 2, 14),
            55,
        )

    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True,
            )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition":
                'attachment; filename="duplicate_audit_results.xlsx"'
        },
    )
