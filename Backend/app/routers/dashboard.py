from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from decimal import Decimal
from ..database import get_db
from ..models import Invoice, BankTransaction, AuditFinding

router=APIRouter(prefix="/dashboard",tags=["لوحة التحكم"])

@router.get("/summary")
def summary(db:Session=Depends(get_db)):
    invoice_count=db.scalar(select(func.count(Invoice.id))) or 0
    tx_count=db.scalar(select(func.count(BankTransaction.id))) or 0
    finding_count=db.scalar(select(func.count(AuditFinding.id))) or 0
    high_count=db.scalar(select(func.count(AuditFinding.id)).where(AuditFinding.risk_level=="مرتفع")) or 0
    total=db.scalar(select(func.coalesce(func.sum(Invoice.amount),0))) or 0
    exposure=db.scalar(select(func.coalesce(func.sum(AuditFinding.potential_impact),0))) or 0
    return {"total_transactions":tx_count,"total_invoices":invoice_count,"total_findings":finding_count,
            "high_risk_findings":high_count,"potential_exposure":float(exposure),"total_expenses":float(total),
            "audit_completion":round((tx_count/max(invoice_count,1))*100,1) if invoice_count else 0}

@router.get("/cashflow")
def cashflow(period:str="6m",db:Session=Depends(get_db)):
    # Demo aggregation from stored transactions; the frontend chart expects m/in/out.
    txs=db.scalars(select(BankTransaction).order_by(BankTransaction.transaction_date)).all()
    labels=["يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر"]
    data=[]
    for idx,label in enumerate(labels):
        vals=[float(t.amount) for t in txs if t.transaction_date.month==((idx+5)%12)+1]
        data.append({"m":label,"in":sum(v for v in vals if v>0),"out":sum(abs(v) for v in vals)})
    return {"period":period,"data":data}
