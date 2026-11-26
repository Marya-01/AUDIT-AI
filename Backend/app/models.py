from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, DateTime, Date, Numeric, Integer, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(80), index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    supplier_name: Mapped[str] = mapped_column(String(200))
    invoice_date: Mapped[date] = mapped_column(Date, default=date.today)
    amount: Mapped[Decimal] = mapped_column(Numeric(14,2), default=0)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(14,2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="قيد المراجعة")
    risk_level: Mapped[str] = mapped_column(String(30), default="منخفض")
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(250))
    transaction_date: Mapped[date] = mapped_column(Date, default=date.today)
    amount: Mapped[Decimal] = mapped_column(Numeric(14,2))
    direction: Mapped[str] = mapped_column(String(20), default="debit")
    status: Mapped[str] = mapped_column(String(40), default="غير مطابق")
    matched_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="تم الرفع")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AuditFinding(Base):
    __tablename__ = "audit_findings"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250))
    category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(30))
    score: Mapped[int] = mapped_column(Integer, default=0)
    potential_impact: Mapped[Decimal] = mapped_column(Numeric(14,2), default=0)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="مفتوحة")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    bank_transaction_id: Mapped[int] = mapped_column(ForeignKey("bank_transactions.id"))
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    difference: Mapped[Decimal] = mapped_column(Numeric(14,2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AuditReport(Base):
    __tablename__ = "audit_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250))
    report_type: Mapped[str] = mapped_column(String(80))
    file_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentAudit(Base):
    __tablename__ = "document_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), default="مكتمل")
    summary: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(30), default="منخفض")
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    extracted_chars: Mapped[int] = mapped_column(Integer, default=0)
    line_count: Mapped[int] = mapped_column(Integer, default=0)
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class DocumentAuditFinding(Base):
    __tablename__ = "document_audit_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    audit_id: Mapped[int] = mapped_column(
        ForeignKey("document_audits.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(250))
    category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(30), default="منخفض")
    score: Mapped[int] = mapped_column(Integer, default=0)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
