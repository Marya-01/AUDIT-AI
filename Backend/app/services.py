
from collections import defaultdict
from decimal import Decimal
from datetime import timedelta
from difflib import SequenceMatcher
import re
import statistics

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Invoice,
    BankTransaction,
    AuditFinding,
    ReconciliationResult,
)


# الفئات التي يعيد محرك الفحص بناءها عند كل تشغيل
SCAN_CATEGORIES = [
    "duplicate_invoice",
    "unusual_amount",
    "supplier_anomaly",
]


def normalize_invoice_number(value):
    """
    توحيد رقم الفاتورة لإزالة الفواصل والرموز والمسافات.
    مثال:
    INV-1001 = INV1001
    """
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def normalize_supplier(value):
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def days_between(date1, date2):
    return abs((date1 - date2).days)


def median_decimal(values):
    values = sorted(Decimal(str(x)) for x in values)
    if not values:
        return Decimal("0")

    middle = len(values) // 2

    if len(values) % 2:
        return values[middle]

    return (values[middle - 1] + values[middle]) / Decimal("2")


def create_finding(
    db,
    title,
    category,
    description,
    risk_level,
    score,
    impact,
    invoice_id,
):
    finding = AuditFinding(
        title=title,
        category=category,
        description=description,
        risk_level=risk_level,
        score=score,
        potential_impact=Decimal(str(impact)),
        invoice_id=invoice_id,
        status="مفتوحة",
    )

    db.add(finding)
    return finding


def detect_duplicate_invoices(db, invoices):
    """
    اكتشاف الفواتير المتشابهة وفق مجموعة من القرائن:
    - رقم فاتورة متطابق بعد التطبيع.
    - المورد نفسه والمبلغ نفسه والتاريخ متقارب.
    - أرقام متشابهة جداً مع تطابق المبلغ أو تقارب التاريخ.
    """

    suppliers = defaultdict(list)

    for invoice in invoices:
        key = normalize_supplier(invoice.supplier_name)
        suppliers[key].append(invoice)

    suspicious_pairs = []

    for supplier_key, supplier_invoices in suppliers.items():

        supplier_invoices.sort(
            key=lambda x: (x.invoice_date, x.id)
        )

        for i in range(len(supplier_invoices)):
            first = supplier_invoices[i]

            for j in range(i + 1, len(supplier_invoices)):
                second = supplier_invoices[j]

                number1 = normalize_invoice_number(
                    first.invoice_number
                )

                number2 = normalize_invoice_number(
                    second.invoice_number
                )

                amount1 = Decimal(first.amount)
                amount2 = Decimal(second.amount)

                same_amount = amount1 == amount2

                close_date = (
                    days_between(
                        first.invoice_date,
                        second.invoice_date,
                    ) <= 3
                )

                same_normalized_number = (
                    number1 == number2 and bool(number1)
                )

                similarity = SequenceMatcher(
                    None,
                    number1,
                    number2,
                ).ratio()

                similar_number = similarity >= 0.90

                duplicate_reason = None
                score = 0

                if same_normalized_number:
                    duplicate_reason = (
                        "رقما الفاتورتين متطابقان بعد إزالة الرموز "
                        "والفواصل."
                    )
                    score = 95

                elif same_amount and close_date:
                    duplicate_reason = (
                        "الفاتورتان لهما المبلغ نفسه "
                        "وتاريخاهما متقاربان بفترة لا تتجاوز 3 أيام."
                    )
                    score = 85

                elif similar_number and (
                    same_amount or close_date
                ):
                    duplicate_reason = (
                        f"رقما الفاتورتين متشابهان بنسبة "
                        f"{similarity * 100:.1f}%، "
                        "مع وجود تشابه إضافي في المبلغ أو التاريخ."
                    )
                    score = 80

                if duplicate_reason:
                    suspicious_pairs.append(
                        (first, second, duplicate_reason, score)
                    )

    # كل فاتورة تظهر مرة واحدة فقط في نتائج هذه المجموعة
    reported_invoices = set()
    findings = []

    for first, second, reason, score in suspicious_pairs:

        pair_key = tuple(sorted((first.id, second.id)))

        if pair_key in reported_invoices:
            continue

        reported_invoices.add(pair_key)

        description = (
            f"تم العثور على فاتورتين متشابهتين للمورد "
            f"{first.supplier_name}. "
            f"الفاتورة الأولى: {first.invoice_number} "
            f"بمبلغ {first.amount} وتاريخ {first.invoice_date}. "
            f"الفاتورة الثانية: {second.invoice_number} "
            f"بمبلغ {second.amount} وتاريخ {second.invoice_date}. "
            f"سبب الاشتباه: {reason} "
            "يجب مراجعة المستندات الأصلية قبل اعتبارهما مكررتين."
        )

        for invoice in (first, second):

            if invoice.id in reported_invoices:
                continue

            reported_invoices.add(invoice.id)

            finding = create_finding(
                db=db,
                title="اشتباه في تكرار فاتورة",
                category="duplicate_invoice",
                description=description,
                risk_level="مرتفع",
                score=score,
                impact=invoice.amount,
                invoice_id=invoice.id,
            )

            findings.append(finding)

    return findings




def run_duplicate_audit(db: Session, invoice_ids):
    """
    تشغيل تدقيق الفواتير المكررة للفواتير المحددة.
    يقارن الفواتير المحددة بجميع الفواتير الموجودة.
    """

    selected_ids = {int(x) for x in invoice_ids}

    if not selected_ids:
        raise ValueError("يجب تحديد فاتورة واحدة على الأقل.")

    try:
        invoices = db.scalars(
            select(Invoice).order_by(
                Invoice.supplier_name,
                Invoice.invoice_date,
                Invoice.id,
            )
        ).all()

        invoice_map = {invoice.id: invoice for invoice in invoices}

        missing_ids = selected_ids - set(invoice_map)

        if missing_ids:
            raise ValueError(
                f"الفواتير التالية غير موجودة: {sorted(missing_ids)}"
            )

        # حذف نتائج التدقيق السابقة المفتوحة للفواتير المحددة فقط.
        db.query(AuditFinding).filter(
            AuditFinding.category == "duplicate_invoice",
            AuditFinding.invoice_id.in_(selected_ids),
            AuditFinding.status == "مفتوحة",
        ).delete(synchronize_session=False)

        seen_pairs = set()
        findings = []

        for first in invoices:
            if first.id not in selected_ids:
                continue

            for second in invoices:
                if first.id == second.id:
                    continue

                pair_key = tuple(sorted((first.id, second.id)))

                if pair_key in seen_pairs:
                    continue

                seen_pairs.add(pair_key)

                supplier1 = normalize_supplier(first.supplier_name)
                supplier2 = normalize_supplier(second.supplier_name)

                if not supplier1 or supplier1 != supplier2:
                    continue

                number1 = normalize_invoice_number(first.invoice_number)
                number2 = normalize_invoice_number(second.invoice_number)

                amount1 = Decimal(first.amount or 0)
                amount2 = Decimal(second.amount or 0)

                same_amount = amount1 == amount2

                close_date = (
                    days_between(first.invoice_date, second.invoice_date) <= 3
                )

                same_number = bool(number1) and number1 == number2

                similarity = SequenceMatcher(
                    None, number1, number2
                ).ratio()

                reason = None
                score = 0

                if same_number:
                    reason = "رقما الفاتورتين متطابقان بعد توحيد التنسيق."
                    score = 95

                elif same_amount and close_date:
                    reason = (
                        "الفاتورتان لهما المبلغ نفسه وتاريخاهما متقاربان "
                        "بفارق لا يتجاوز 3 أيام."
                    )
                    score = 85

                elif similarity >= 0.90 and (same_amount or close_date):
                    reason = (
                        f"تشابه رقمي الفاتورتين بنسبة {similarity * 100:.1f}% "
                        "مع تطابق المبلغ أو تقارب التاريخ."
                    )
                    score = 80

                if not reason:
                    continue

                description = (
                    f"تم العثور على فاتورتين متشابهتين للمورد "
                    f"{first.supplier_name}. "
                    f"الفاتورة الأولى: {first.invoice_number} "
                    f"بمبلغ {first.amount} وتاريخ {first.invoice_date}. "
                    f"الفاتورة الثانية: {second.invoice_number} "
                    f"بمبلغ {second.amount} وتاريخ {second.invoice_date}. "
                    f"سبب الاشتباه: {reason} "
                    "يجب مراجعة المستندات الأصلية قبل اعتبارهما مكررتين."
                )

                # إنشاء النتائج للفواتير المحددة فقط.
                for invoice in (first, second):
                    if invoice.id not in selected_ids:
                        continue

                    finding = create_finding(
                        db=db,
                        title="اشتباه في تكرار فاتورة",
                        category="duplicate_invoice",
                        description=description,
                        risk_level="مرتفع",
                        score=score,
                        impact=invoice.amount,
                        invoice_id=invoice.id,
                    )

                    findings.append(finding)

        db.commit()
        return findings

    except Exception:
        db.rollback()
        raise


def detect_unusual_amounts(db, invoices):
    """
    فحص أولي للقيم المرتفعة مقارنة بوسيط مبالغ الفواتير.
    """

    amounts = [
        Decimal(x.amount)
        for x in invoices
        if Decimal(x.amount) > 0
    ]

    findings = []

    if len(amounts) < 3:
        return findings

    median = median_decimal(amounts)

    threshold = median * Decimal("3")

    for invoice in invoices:

        amount = Decimal(invoice.amount)

        if amount > threshold:

            finding = create_finding(
                db=db,
                title="قيمة فاتورة غير معتادة",
                category="unusual_amount",
                description=(
                    f"المبلغ {amount} أعلى من حد الفحص الأولي "
                    f"{threshold} المحسوب من وسيط مبالغ الفواتير. "
                    "يتطلب ذلك مراجعة ولا يثبت وجود احتيال."
                ),
                risk_level="متوسط",
                score=68,
                impact=amount,
                invoice_id=invoice.id,
            )

            findings.append(finding)

    return findings


def detect_supplier_anomalies(db, invoices):
    """
    مقارنة قيمة الفاتورة بالقيم السابقة للمورد نفسه.

    يشترط توفر 3 فواتير سابقة على الأقل.
    لا تدخل الفاتورة الحالية في حساب خط الأساس.
    """

    suppliers = defaultdict(list)

    for invoice in invoices:
        key = normalize_supplier(invoice.supplier_name)
        suppliers[key].append(invoice)

    findings = []

    for supplier_key, supplier_invoices in suppliers.items():

        supplier_invoices.sort(
            key=lambda x: (x.invoice_date, x.id)
        )

        for index, invoice in enumerate(supplier_invoices):

            historical = supplier_invoices[:index]

            # لا نحلل المورد إذا لم تتوفر 3 فواتير سابقة
            if len(historical) < 3:
                continue

            historical_amounts = [
                Decimal(x.amount)
                for x in historical
                if Decimal(x.amount) > 0
            ]

            if len(historical_amounts) < 3:
                continue

            baseline = median_decimal(historical_amounts)

            current_amount = Decimal(invoice.amount)

            if baseline <= 0:
                continue

            threshold = baseline * Decimal("3")

            if current_amount > threshold:

                ratio = current_amount / baseline

                score = min(
                    95,
                    65 + int((ratio - 3) * 10),
                )

                description = (
                    f"قيمة الفاتورة {invoice.invoice_number} "
                    f"للمورد {invoice.supplier_name} "
                    f"تبلغ {current_amount}. "
                    f"وسيط قيمة فواتير المورد السابقة "
                    f"هو {baseline}. "
                    f"القيمة الحالية تعادل تقريباً "
                    f"{ratio:.2f} مرة من خط الأساس التاريخي. "
                    f"حد الفحص الأولي هو {threshold}. "
                    "ينبغي التحقق من العقد وطلب الشراء "
                    "والتغيرات المحتملة في حجم التوريد."
                )

                finding = create_finding(
                    db=db,
                    title="نمط إنفاق غير معتاد لدى المورد",
                    category="supplier_anomaly",
                    description=description,
                    risk_level="مرتفع",
                    score=score,
                    impact=current_amount,
                    invoice_id=invoice.id,
                )

                findings.append(finding)

    return findings


def scan_risks(db: Session):
    """
    تشغيل محرك اكتشاف المخاطر:
    1. الفواتير المكررة.
    2. القيم غير المعتادة.
    3. أنماط الموردين غير المعتادة.
    """

    try:
        db.query(AuditFinding).filter(
            AuditFinding.category.in_(SCAN_CATEGORIES)
        ).delete(synchronize_session=False)

        invoices = db.scalars(
            select(Invoice).order_by(
                Invoice.supplier_name,
                Invoice.invoice_date,
                Invoice.id,
            )
        ).all()

        findings = []

        findings.extend(
            detect_duplicate_invoices(db, invoices)
        )

        findings.extend(
            detect_unusual_amounts(db, invoices)
        )

        findings.extend(
            detect_supplier_anomalies(db, invoices)
        )

        db.commit()

        return findings

    except Exception:
        db.rollback()
        raise


def reconcile(db: Session):
    db.query(ReconciliationResult).delete(
        synchronize_session=False
    )

    txs = db.scalars(
        select(BankTransaction)
    ).all()

    invoices = db.scalars(
        select(Invoice)
    ).all()

    results = []

    for tx in txs:

        candidates = [
            invoice
            for invoice in invoices
            if Decimal(invoice.amount) == Decimal(tx.amount)
            and (
                tx.matched_invoice_id is None
                or invoice.id == tx.matched_invoice_id
            )
        ]

        match = candidates[0] if candidates else None

        status = "مطابق" if match else "غير مطابق"

        difference = (
            Decimal("0")
            if match
            else Decimal(tx.amount)
        )

        tx.status = status

        tx.matched_invoice_id = (
            match.id if match else None
        )

        result = ReconciliationResult(
            bank_transaction_id=tx.id,
            invoice_id=match.id if match else None,
            status=status,
            difference=difference,
        )

        db.add(result)
        results.append(result)

    db.commit()

    return results
