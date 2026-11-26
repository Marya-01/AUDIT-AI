from collections import defaultdict
from datetime import datetime
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from ..config import settings
from ..database import get_db
from ..models import AuditReport, Document, DocumentAudit, DocumentAuditFinding
from ..schemas import ReportRequest


router = APIRouter(prefix="/reports", tags=["\u0627\u0644\u062a\u0642\u0627\u0631\u064a\u0631"])


def prepare_arabic(value):
    text = str(value or "")
    return get_display(arabic_reshaper.reshape(text))


def get_arabic_font():
    font_path = Path("C:/Windows/Fonts/tahoma.ttf")

    if not font_path.exists():
        raise RuntimeError("\u062a\u0639\u0630\u0631 \u0627\u0644\u0639\u062b\u0648\u0631 \u0639\u0644\u0649 \u062e\u0637 Tahoma.")

    font_name = "ArabicTahoma"

    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))

    return font_name


@router.get("")
def reports(db: Session = Depends(get_db)):
    items = db.scalars(
        select(AuditReport).order_by(AuditReport.created_at.desc())
    ).all()

    return [
        {
            "id": item.id,
            "title": item.title,
            "type": item.report_type,
            "format": "PDF",
            "status": "\u0645\u0643\u062a\u0645\u0644",
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]


@router.post("/generate")
def generate(payload: ReportRequest, db: Session = Depends(get_db)):
    if payload.format.lower() != "pdf":
        raise HTTPException(
            status_code=400,
            detail="\u0627\u0644\u0635\u064a\u063a\u0629 \u0627\u0644\u0645\u062f\u0639\u0648\u0645\u0629 \u062d\u0627\u0644\u064a\u064b\u0627 PDF \u0641\u0642\u0637.",
        )

    font_name = get_arabic_font()

    documents = db.scalars(
        select(Document).order_by(Document.created_at.desc())
    ).all()

    audits = db.scalars(
        select(DocumentAudit).order_by(
            DocumentAudit.created_at.desc(),
            DocumentAudit.id.desc(),
        )
    ).all()

    document_map = {item.id: item for item in documents}

    # \u0627\u0633\u062a\u062e\u0631\u0627\u062c \u0623\u062d\u062f\u062b \u062a\u062f\u0642\u064a\u0642 \u0644\u0643\u0644 \u0645\u0633\u062a\u0646\u062f
    latest_audits = {}
    for audit in audits:
        if audit.document_id not in latest_audits:
            latest_audits[audit.document_id] = audit

    audit_ids = [item.id for item in latest_audits.values()]

    findings = []
    if audit_ids:
        findings = db.scalars(
            select(DocumentAuditFinding)
            .where(DocumentAuditFinding.audit_id.in_(audit_ids))
            .order_by(
                DocumentAuditFinding.score.desc(),
                DocumentAuditFinding.id.asc(),
            )
        ).all()

    findings_by_audit = defaultdict(list)
    for finding in findings:
        findings_by_audit[finding.audit_id].append(finding)

    high_risk_documents = sum(
        1 for audit in latest_audits.values()
        if audit.risk_level == "\u0645\u0631\u062a\u0641\u0639"
    )

    high_risk_findings = sum(
        1 for finding in findings
        if finding.risk_level == "\u0645\u0631\u062a\u0641\u0639"
    )

    output_dir = Path(settings.upload_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        "audit-report-"
        + datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
        + ".pdf"
    )
    output_path = output_dir / filename

    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    right = width - 48
    y = height - 55

    pdf.setTitle("AUDIT AI Audit Report")

    def new_page():
        nonlocal y
        pdf.showPage()
        y = height - 55

    def draw_text(text, size=10, spacing=17):
        nonlocal y

        visual = prepare_arabic(text)
        text_width = pdfmetrics.stringWidth(visual, font_name, size)

        if text_width > width - 100:
            draw_paragraph(text, size, spacing)
            return

        if y < 65:
            new_page()

        pdf.setFont(font_name, size)
        pdf.drawString(right - text_width, y, visual)
        y -= spacing

    def draw_paragraph(text, size=9, spacing=15):
        nonlocal y

        words = str(text or "").split()
        if not words:
            y -= spacing
            return

        lines = []
        current = ""

        for word in words:
            candidate = (current + " " + word).strip()
            visual = prepare_arabic(candidate)
            measured = pdfmetrics.stringWidth(visual, font_name, size)

            if measured <= width - 105:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

        for line in lines:
            if y < 65:
                new_page()

            visual = prepare_arabic(line)
            text_width = pdfmetrics.stringWidth(visual, font_name, size)

            pdf.setFont(font_name, size)
            pdf.drawString(right - text_width, y, visual)
            y -= spacing

    pdf.setFont(font_name, 19)
    draw_text("\u062a\u0642\u0631\u064a\u0631 \u062a\u062f\u0642\u064a\u0642 \u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a", 19, 30)
    draw_text("\u0646\u0638\u0627\u0645 AUDIT AI", 12, 24)
    draw_text(
        "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u062a\u0642\u0631\u064a\u0631: " + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        9,
        25,
    )

    draw_text("\u0627\u0644\u0625\u062d\u0635\u0627\u0626\u064a\u0627\u062a \u0627\u0644\u0639\u0627\u0645\u0629", 13, 23)
    draw_text(f"\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a: {len(documents)}")
    draw_text(f"\u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a \u0627\u0644\u0645\u062f\u0642\u0642\u0629: {len(latest_audits)}")
    draw_text(
        f"\u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a \u063a\u064a\u0631 \u0627\u0644\u0645\u062f\u0642\u0642\u0629: {max(0, len(documents) - len(latest_audits))}"
    )
    draw_text(f"\u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a \u0639\u0627\u0644\u064a\u0629 \u0627\u0644\u062e\u0637\u0648\u0631\u0629: {high_risk_documents}")
    draw_text(f"\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0627\u062a \u0627\u0644\u062a\u062f\u0642\u064a\u0642\u064a\u0629: {len(findings)}")
    draw_text(f"\u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0627\u062a \u0639\u0627\u0644\u064a\u0629 \u0627\u0644\u062e\u0637\u0648\u0631\u0629: {high_risk_findings}")

    y -= 12
    draw_text("\u062a\u0641\u0627\u0635\u064a\u0644 \u0646\u062a\u0627\u0626\u062c \u0627\u0644\u062a\u062f\u0642\u064a\u0642", 13, 23)

    if not latest_audits:
        draw_paragraph("\u0644\u0627 \u062a\u0648\u062c\u062f \u0645\u0633\u062a\u0646\u062f\u0627\u062a \u0645\u062f\u0642\u0642\u0629 \u062d\u0627\u0644\u064a\u064b\u0627.")

    for document_id, audit in latest_audits.items():
        document = document_map.get(document_id)
        document_name = (
            document.filename if document else f"\u0645\u0633\u062a\u0646\u062f \u0631\u0642\u0645 {document_id}"
        )

        y -= 8
        draw_text("\u0627\u0644\u0645\u0633\u062a\u0646\u062f: " + document_name, 11, 20)
        draw_text("\u062d\u0627\u0644\u0629 \u0627\u0644\u062a\u062f\u0642\u064a\u0642: " + str(audit.status))
        draw_text("\u0645\u0633\u062a\u0648\u0649 \u0627\u0644\u062e\u0637\u0648\u0631\u0629: " + str(audit.risk_level))
        draw_text(f"\u062f\u0631\u062c\u0629 \u0627\u0644\u062e\u0637\u0648\u0631\u0629: {audit.risk_score} / 100")
        draw_text(f"\u0639\u062f\u062f \u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0627\u062a: {audit.finding_count}")

        if audit.summary:
            draw_text("\u0645\u0644\u062e\u0635 \u0627\u0644\u062a\u062f\u0642\u064a\u0642:")
            draw_paragraph(audit.summary)

        audit_findings = findings_by_audit.get(audit.id, [])

        if not audit_findings:
            draw_text("\u0644\u0627 \u062a\u0648\u062c\u062f \u0645\u0644\u0627\u062d\u0638\u0627\u062a \u062a\u062f\u0642\u064a\u0642\u064a\u0629 \u0644\u0647\u0630\u0627 \u0627\u0644\u0645\u0633\u062a\u0646\u062f.")
            continue

        draw_text("\u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0627\u062a \u0627\u0644\u062a\u062f\u0642\u064a\u0642\u064a\u0629:", 10, 19)

        for index, finding in enumerate(audit_findings, start=1):
            y -= 5
            draw_text(f"{index}. {finding.title}", 10, 18)
            draw_text("\u0627\u0644\u062a\u0635\u0646\u064a\u0641: " + str(finding.category))
            draw_text("\u0645\u0633\u062a\u0648\u0649 \u0627\u0644\u062e\u0637\u0648\u0631\u0629: " + str(finding.risk_level))
            draw_text(f"\u0627\u0644\u062f\u0631\u062c\u0629: {finding.score} / 100")
            draw_text(f"\u0639\u062f\u062f \u0645\u0631\u0627\u062a \u0627\u0644\u062a\u0643\u0631\u0627\u0631: {finding.occurrence_count}")

            if finding.description:
                draw_text("\u0627\u0644\u0648\u0635\u0641:")
                draw_paragraph(finding.description)

            if finding.evidence:
                draw_text("\u0627\u0644\u0623\u062f\u0644\u0629:")
                draw_paragraph(finding.evidence)

            if finding.recommendation:
                draw_text("\u0627\u0644\u062a\u0648\u0635\u064a\u0629:")
                draw_paragraph(finding.recommendation)

            y -= 8

    footer = prepare_arabic(
        "\u062a\u0645 \u0625\u0646\u0634\u0627\u0621 \u0647\u0630\u0627 \u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u0622\u0644\u064a\u064b\u0627 \u0628\u0648\u0627\u0633\u0637\u0629 \u0646\u0638\u0627\u0645 AUDIT AI."
    )
    pdf.setFont(font_name, 8)
    pdf.drawRightString(right, 35, footer)
    pdf.save()

    report = AuditReport(
        title="\u062a\u0642\u0631\u064a\u0631 \u062a\u062f\u0642\u064a\u0642 \u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a",
        report_type=payload.type,
        file_path=str(output_path.resolve()),
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "id": report.id,
        "title": report.title,
        "download_url": f"/api/v1/reports/{report.id}/download",
        "message": "\u062a\u0645 \u0625\u0646\u0634\u0627\u0621 \u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u0628\u0646\u062c\u0627\u062d.",
    }


@router.get("/{report_id}/download")
def download(report_id: int, db: Session = Depends(get_db)):
    report = db.get(AuditReport, report_id)

    if not report or not Path(report.file_path).exists():
        raise HTTPException(status_code=404, detail="\u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u063a\u064a\u0631 \u0645\u0648\u062c\u0648\u062f")

    return FileResponse(
        report.file_path,
        media_type="application/pdf",
        filename=Path(report.file_path).name,
    )


@router.delete("/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(AuditReport, report_id)

    if report is None:
        raise HTTPException(status_code=404, detail="\u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u063a\u064a\u0631 \u0645\u0648\u062c\u0648\u062f")

    upload_root = Path(settings.upload_dir).resolve()
    report_path = Path(report.file_path).resolve()

    if upload_root not in report_path.parents:
        raise HTTPException(
            status_code=400,
            detail="\u0645\u0633\u0627\u0631 \u0645\u0644\u0641 \u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u063a\u064a\u0631 \u0645\u0633\u0645\u0648\u062d",
        )

    if report_path.exists():
        if not report_path.is_file():
            raise HTTPException(
                status_code=400,
                detail="\u0645\u0633\u0627\u0631 \u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u0644\u064a\u0633 \u0645\u0644\u0641\u064b\u0627 \u0635\u0627\u0644\u062d\u064b\u0627",
            )
        report_path.unlink()

    db.delete(report)
    db.commit()

    return {
        "message": "\u062a\u0645 \u062d\u0630\u0641 \u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u0648\u0645\u0644\u0641 PDF \u0627\u0644\u0645\u0631\u062a\u0628\u0637 \u0628\u0647 \u0628\u0646\u062c\u0627\u062d",
        "id": report_id,
    }
