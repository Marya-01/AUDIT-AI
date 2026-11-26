from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, func
from .models import Supplier, Invoice, BankTransaction, AuditFinding

def seed_if_empty(db):
    if db.scalar(select(func.count(Invoice.id))) > 0:
        return
    suppliers = ["شركة الأفق للتوريدات", "مؤسسة النور التجارية", "شركة الإمداد الحديث", "مكتبة المعرفة", "شركة التقنية المتقدمة"]
    objects = [Supplier(name=x) for x in suppliers]
    db.add_all(objects); db.flush()
    today = date.today()
    rows = [
        ("INV-2026-001",0,485000,"مكتملة","منخفض"),
        ("INV-2026-002",1,127500,"قيد المراجعة","متوسط"),
        ("INV-2026-003",2,895000,"مكتملة","مرتفع"),
        ("INV-2026-004",3,36500,"مرفوضة","مرتفع"),
        ("INV-2026-005",4,240000,"قيد المراجعة","متوسط"),
    ]
    invoices=[]
    for no,idx,amount,status,risk in rows:
        inv=Invoice(invoice_number=no,supplier_id=objects[idx].id,supplier_name=suppliers[idx],
                    invoice_date=today-timedelta(days=idx+1),amount=Decimal(str(amount)),
                    status=status,risk_level=risk)
        db.add(inv); invoices.append(inv)
    db.flush()
    for i,inv in enumerate(invoices):
        db.add(BankTransaction(reference=f"BNK-{i+1:04}",description=f"دفعة {inv.supplier_name}",
                               transaction_date=inv.invoice_date,amount=inv.amount,
                               direction="debit",status="مطابق" if i in (0,2) else "غير مطابق",
                               matched_invoice_id=inv.id if i in (0,2) else None))
    db.add(AuditFinding(title="مراجعة فاتورة ذات مبلغ مرتفع",category="unusual_amount",
        description="قيمة الفاتورة مرتفعة مقارنة ببقية العينة؛ يلزم فحص المستندات المؤيدة.",risk_level="مرتفع",
        score=78,potential_impact=Decimal("895000"),invoice_id=invoices[2].id))
    db.add(AuditFinding(title="فاتورة قيد المراجعة",category="pending_review",
        description="لم تكتمل إجراءات المراجعة والموافقة.",risk_level="متوسط",score=54,
        potential_impact=Decimal("127500"),invoice_id=invoices[1].id))
    db.commit()
