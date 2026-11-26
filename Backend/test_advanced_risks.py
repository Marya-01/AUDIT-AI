
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Supplier, Invoice


def get_or_create_supplier(db, name):
    supplier = db.scalar(
        select(Supplier).where(Supplier.name == name)
    )

    if supplier is None:
        supplier = Supplier(name=name)
        db.add(supplier)
        db.flush()

    return supplier


def add_invoice(
    db,
    number,
    supplier,
    amount,
    days_ago,
):
    existing = db.scalar(
        select(Invoice.id).where(
            Invoice.invoice_number == number
        )
    )

    if existing is not None:
        print(f"موجودة مسبقاً: {number}")
        return False

    invoice = Invoice(
        invoice_number=number,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        invoice_date=date.today() - timedelta(days=days_ago),
        amount=Decimal(str(amount)),
        status="قيد المراجعة",
        risk_level="منخفض",
    )

    db.add(invoice)
    print(f"تم تجهيز: {number}")
    return True


def main():
    db = SessionLocal()

    try:
        supplier = get_or_create_supplier(
            db,
            "مورد اختبار تحليل الأنماط",
        )

        duplicate_supplier = get_or_create_supplier(
            db,
            "مورد اختبار الفواتير المكررة",
        )

        inserted = 0

        # ثلاث فواتير تاريخية للمورد الأول
        historical_invoices = [
            ("TEST-SUP-001", 100000, 120),
            ("TEST-SUP-002", 110000, 90),
            ("TEST-SUP-003", 105000, 60),
        ]

        for number, amount, days in historical_invoices:
            if add_invoice(
                db, number, supplier, amount, days
            ):
                inserted += 1

        # فاتورة مرتفعة مقارنة بتاريخ المورد
        if add_invoice(
            db,
            "TEST-SUP-004",
            supplier,
            600000,
            1,
        ):
            inserted += 1

        # فاتورتان مختلفتا الرقم لكن لهما المبلغ والتاريخ نفسيهما
        duplicate_invoices = [
            ("TEST-DUP-001", 250000, 2),
            ("TEST-DUP-002", 250000, 2),
        ]

        for number, amount, days in duplicate_invoices:
            if add_invoice(
                db,
                number,
                duplicate_supplier,
                amount,
                days,
            ):
                inserted += 1

        db.commit()

        print("\nاكتمل تجهيز بيانات الاختبار.")
        print(f"عدد الفواتير الجديدة: {inserted}")
        print("المورد الأول: 4 فواتير لاختبار الأنماط.")
        print("المورد الثاني: فاتورتان لاختبار التكرار.")

    except Exception:
        db.rollback()
        print("فشل إدخال البيانات، تم التراجع عن العملية.")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
