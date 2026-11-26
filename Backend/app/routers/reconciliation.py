
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from ..models import ReconciliationResult, BankTransaction, Invoice
from .. import services

router = APIRouter(
    prefix="/reconciliation",
    tags=["التسوية البنكية"],
)


@router.post("/run")
def run(db: Session = Depends(get_db)):
    rows = services.reconcile(db)

    matched = sum(
        1 for x in rows if x.status == "مطابق"
    )

    return {
        "message": "اكتملت عملية المطابقة.",
        "total": len(rows),
        "matched": matched,
        "unmatched": len(rows) - matched,
    }


@router.get("/results")
def results(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ReconciliationResult).order_by(
            ReconciliationResult.id.desc()
        )
    ).all()

    output = []

    for x in rows:
        tx = db.get(BankTransaction, x.bank_transaction_id)
        inv = db.get(Invoice, x.invoice_id) if x.invoice_id else None

        output.append({
            "id": x.id,
            "transaction_reference": tx.reference if tx else None,
            "invoice_number": inv.invoice_number if inv else None,
            "status": x.status,
            "difference": float(x.difference),
        })

    return output
