
from collections import defaultdict
from pathlib import Path
from decimal import Decimal, InvalidOperation
import re
import pandas as pd
from .invoice_extractor import (
    extract_raw_text,
    extract_tabular_records,
    extract_ledger_records,
    extract_journal_records,
    extract_expense_register_records,
    extract_pdf_pages,
    extract_invoice_number,
    extract_supplier_name,
    extract_invoice_date,
    extract_amount,
    extract_tax_amount,
    extract_currency,
    normalize_text,
)


def _normalize_value(value):
    if value is None:
        return ""

    value = normalize_text(str(value))
    value = re.sub(r"\s+", " ", value).strip()

    return value.casefold()


def _normalize_invoice_number(value):
    """توحيد رقم الفاتورة مع تجاهل المسافات والشرطات."""
    value = _normalize_value(value)
    return re.sub(r"[^a-z0-9]", "", value)


def _normalize_amount(value):
    if value is None or str(value).strip() == "":
        return ""

    try:
        return str(Decimal(str(value)).normalize())
    except (InvalidOperation, ValueError):
        return _normalize_value(value)


def _location(record):
    if record.get("source_sheet") is not None:
        return (
            f"الورقة: {record['source_sheet']}، "
            f"الصف: {record.get('source_row', 'غير معروف')}"
        )

    if record.get("page_number") is not None:
        return f"الصفحة: {record['page_number']}"

    return "موضع غير محدد"


def _make_finding(
    title,
    category,
    description,
    evidence,
    recommendation,
    risk_level,
    score,
    occurrence_count,
):
    return {
        "title": title,
        "category": category,
        "description": description,
        "evidence": evidence,
        "recommendation": recommendation,
        "risk_level": risk_level,
        "score": score,
        "occurrence_count": occurrence_count,
    }


def _group_values(records, field, normalizer=_normalize_value):
    groups = defaultdict(list)

    for record in records:
        value = normalizer(record.get(field))

        if value:
            groups[value].append(record)

    return groups


def _audit_invoice_records(records):
    """تدقيق سجلات الفواتير دون إنشاء سجلات فواتير في قاعدة البيانات."""
    findings = []

    invoice_groups = _group_values(
        records,
        "invoice_number",
        _normalize_invoice_number,
    )

    duplicated_invoice_keys = set()

    for invoice_number, group in invoice_groups.items():
        if len(group) < 2:
            continue

        duplicated_invoice_keys.add(invoice_number)

        original_values = [
            str(record.get("invoice_number", "")).strip()
            for record in group
        ]

        locations = [_location(record) for record in group]

        findings.append(_make_finding(
            title="رقم فاتورة مكرر",
            category="تكرار البيانات",
            description=(
                "تم العثور على رقم فاتورة مكرر داخل المستند. "
                "تم تجاهل اختلاف المسافات والشرطات عند المقارنة."
            ),
            evidence=(
                f"رقم الفاتورة الموحد: {invoice_number}\n"
                f"القيم الأصلية: {' | '.join(original_values)}\n"
                f"عدد مرات الظهور: {len(group)}\n"
                + "\n".join(locations)
            ),
            recommendation=(
                "يرجى مراجعة مواضع الفاتورة والتحقق من "
                "عدم تسجيل الفاتورة نفسها أكثر من مرة."
            ),
            risk_level="مرتفع",
            score=45,
            occurrence_count=len(group),
        ))

    reference_groups = _group_values(records, "reference")

    for reference, group in reference_groups.items():
        if len(group) < 2:
            continue

        locations = [_location(record) for record in group]

        findings.append(_make_finding(
            title="رقم مرجع مكرر",
            category="تكرار البيانات",
            description="تم العثور على رقم المرجع نفسه في أكثر من سجل.",
            evidence=(
                f"رقم المرجع: {reference}\n"
                f"عدد مرات الظهور: {len(group)}\n"
                + "\n".join(locations)
            ),
            recommendation=(
                "يرجى التحقق من أن المرجع لا يرتبط "
                "بأكثر من عملية غير مقصودة."
            ),
            risk_level="متوسط",
            score=25,
            occurrence_count=len(group),
        ))

    # لا ننشئ ملاحظة ثانية للسجل الكامل إذا كان
    # تكرار رقم الفاتورة نفسه قد تم اكتشافه بالفعل.
    record_groups = defaultdict(list)

    for record in records:
        invoice_number = _normalize_invoice_number(
            record.get("invoice_number")
        )

        if invoice_number in duplicated_invoice_keys:
            continue

        reference = _normalize_value(record.get("reference"))

        if not invoice_number and not reference:
            continue

        fingerprint = (
            invoice_number,
            _normalize_value(record.get("supplier_name")),
            _normalize_value(record.get("invoice_date")),
            _normalize_amount(record.get("amount")),
            reference,
        )

        record_groups[fingerprint].append(record)

    for fingerprint, group in record_groups.items():
        if len(group) < 2:
            continue

        invoice_number, supplier, invoice_date, amount, reference = fingerprint

        details = [
            f"رقم الفاتورة: {invoice_number or 'غير متوفر'}",
            f"المورد: {supplier or 'غير متوفر'}",
            f"التاريخ: {invoice_date or 'غير متوفر'}",
            f"المبلغ: {amount or 'غير متوفر'}",
            f"المرجع: {reference or 'غير متوفر'}",
            f"عدد مرات الظهور: {len(group)}",
        ]

        locations = [_location(record) for record in group]

        findings.append(_make_finding(
            title="سجل مكرر بالكامل",
            category="تكرار السجلات",
            description="تم العثور على سجلات متطابقة في بياناتها الأساسية.",
            evidence="\n".join(details) + "\nالمواقع:\n" + "\n".join(locations),
            recommendation=(
                "يرجى مراجعة السجلات المتطابقة "
                "والتحقق من عدم تكرار العملية."
            ),
            risk_level="مرتفع",
            score=45,
            occurrence_count=len(group),
        ))

    return findings




def _audit_expense_register_records(records):
    findings = []
    valid_records = [r for r in records if r.get("is_valid")]

    duplicate_groups = defaultdict(list)
    for record in valid_records:
        key = (
            _normalize_invoice_number(record.get("invoice_number")),
            _normalize_value(record.get("beneficiary")),
            _normalize_amount(record.get("amount")),
        )
        if all(key):
            duplicate_groups[key].append(record)

    for group in duplicate_groups.values():
        if len(group) < 2:
            continue
        findings.append(_make_finding(
            title="\u0627\u062d\u062a\u0645\u0627\u0644 \u062a\u0643\u0631\u0627\u0631 \u0641\u0627\u062a\u0648\u0631\u0629 \u0623\u0648 \u0642\u064a\u062f \u0645\u0635\u0631\u0648\u0641",
            category="\u062a\u0643\u0631\u0627\u0631 \u0627\u0644\u0645\u0639\u0627\u0645\u0644\u0627\u062a",
            description="\u062a\u0643\u0631\u0631 \u0631\u0642\u0645 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629 \u0644\u0644\u0645\u0633\u062a\u0641\u064a\u062f \u0646\u0641\u0633\u0647 \u0648\u0628\u0627\u0644\u0645\u0628\u0644\u063a \u0646\u0641\u0633\u0647\u061b \u064a\u0644\u0632\u0645 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0648\u062c\u0648\u062f \u0635\u0631\u0641 \u0645\u0643\u0631\u0631.",
            evidence=(
                f"\u0631\u0642\u0645 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629: {group[0].get('invoice_number')}\n"
                f"\u0639\u062f\u062f \u0627\u0644\u0633\u062c\u0644\u0627\u062a: {len(group)}\n"
                + "\n".join(_location(r) for r in group)
            ),
            recommendation="\u0631\u0627\u062c\u0639 \u0623\u0635\u0644 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629 \u0648\u0625\u062b\u0628\u0627\u062a\u0627\u062a \u0627\u0644\u062f\u0641\u0639\u060c \u0648\u062a\u0623\u0643\u062f \u0645\u0646 \u0639\u062f\u0645 \u0635\u0631\u0641 \u0627\u0644\u0627\u0644\u062a\u0632\u0627\u0645 \u0645\u0631\u062a\u064a\u0646.",
            risk_level="\u0645\u0631\u062a\u0641\u0639",
            score=40,
            occurrence_count=len(group) - 1,
        ))

    self_approved = [
        r for r in valid_records
        if _normalize_value(r.get("entered_by"))
        and _normalize_value(r.get("approved_by"))
        and _normalize_value(r.get("entered_by")) == _normalize_value(r.get("approved_by"))
    ]
    if self_approved:
        findings.append(_make_finding(
            title="\u0627\u0639\u062a\u0645\u0627\u062f \u0627\u0644\u0645\u0648\u0638\u0641 \u0644\u0644\u0642\u064a\u0648\u062f \u0627\u0644\u062a\u064a \u0623\u062f\u062e\u0644\u0647\u0627 \u0628\u0646\u0641\u0633\u0647",
            category="\u0641\u0635\u0644 \u0627\u0644\u0645\u0647\u0627\u0645 \u0648\u0627\u0644\u0635\u0644\u0627\u062d\u064a\u0627\u062a",
            description="\u062a\u0648\u062c\u062f \u0642\u064a\u0648\u062f \u064a\u062a\u0637\u0627\u0628\u0642 \u0641\u064a\u0647\u0627 \u0627\u0644\u0645\u0648\u0638\u0641 \u0627\u0644\u0645\u062f\u062e\u0644 \u0645\u0639 \u0627\u0644\u0645\u0639\u062a\u0645\u062f\u060c \u0645\u0645\u0627 \u0642\u062f \u064a\u0634\u064a\u0631 \u0625\u0644\u0649 \u063a\u064a\u0627\u0628 \u0641\u0635\u0644 \u0627\u0644\u0645\u0647\u0627\u0645.",
            evidence=f"\u0639\u062f\u062f \u0627\u0644\u0642\u064a\u0648\u062f: {len(self_approved)}\n" + "\n".join(_location(r) for r in self_approved),
            recommendation="\u0627\u0634\u062a\u0631\u0637 \u0627\u0639\u062a\u0645\u0627\u062f\u064b\u0627 \u0645\u0633\u062a\u0642\u0644\u064b\u0627 \u0645\u0646 \u0645\u0648\u0638\u0641 \u0645\u062e\u0648\u0644.",
            risk_level="\u0645\u0631\u062a\u0641\u0639",
            score=40,
            occurrence_count=len(self_approved),
        ))

    iban_groups = defaultdict(list)
    for record in valid_records:
        iban = re.sub(r"[\s-]", "", str(record.get("iban") or "")).upper()
        if iban:
            iban_groups[iban].append(record)

    for iban, group in iban_groups.items():
        beneficiaries = {
            _normalize_value(r.get("beneficiary"))
            for r in group if _normalize_value(r.get("beneficiary"))
        }
        if len(beneficiaries) < 2:
            continue
        findings.append(_make_finding(
            title="\u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u062d\u0633\u0627\u0628 \u0628\u0646\u0643\u064a \u0648\u0627\u062d\u062f \u0644\u0645\u0633\u062a\u0641\u064a\u062f\u064a\u0646 \u0645\u062e\u062a\u0644\u0641\u064a\u0646",
            category="\u0645\u062e\u0627\u0637\u0631 \u0627\u0644\u0645\u0633\u062a\u0641\u064a\u062f \u0648\u0627\u0644\u062d\u0633\u0627\u0628 \u0627\u0644\u0628\u0646\u0643\u064a",
            description="\u0638\u0647\u0631 \u0631\u0642\u0645 \u0627\u0644\u062d\u0633\u0627\u0628 \u0646\u0641\u0633\u0647 \u0645\u0631\u062a\u0628\u0637\u064b\u0627 \u0628\u0623\u0633\u0645\u0627\u0621 \u0645\u0633\u062a\u0641\u064a\u062f\u064a\u0646 \u0645\u062e\u062a\u0644\u0641\u064a\u0646\u061b \u064a\u062a\u0637\u0644\u0628 \u0627\u0644\u062a\u062d\u0642\u0642.",
            evidence=f"\u0627\u0644\u062d\u0633\u0627\u0628: ****{iban[-4:]}\n\u0639\u062f\u062f \u0627\u0644\u0645\u0633\u062a\u0641\u064a\u062f\u064a\u0646: {len(beneficiaries)}\n" + "\n".join(_location(r) for r in group),
            recommendation="\u062a\u062d\u0642\u0642 \u0645\u0646 \u0645\u0644\u0643\u064a\u0629 \u0627\u0644\u062d\u0633\u0627\u0628 \u0645\u0646 \u0645\u0635\u062f\u0631 \u0645\u0635\u0631\u0641\u064a \u0645\u0633\u062a\u0642\u0644.",
            risk_level="\u0645\u062a\u0648\u0633\u0637",
            score=25,
            occurrence_count=len(group),
        ))

    invalid_iban = []
    for record in valid_records:
        iban = re.sub(r"[\s-]", "", str(record.get("iban") or "")).upper()
        if not iban.startswith("SA"):
            continue
        valid_format = bool(re.fullmatch(r"SA\d{22}", iban))
        checksum_valid = False
        if valid_format:
            rearranged = iban[4:] + iban[:4]
            numeric = "".join(
                str(ord(c) - 55) if c.isalpha() else c for c in rearranged
            )
            checksum_valid = int(numeric) % 97 == 1
        if not valid_format or not checksum_valid:
            invalid_iban.append(record)

    if invalid_iban:
        findings.append(_make_finding(
            title="\u0623\u0631\u0642\u0627\u0645 IBAN \u0633\u0639\u0648\u062f\u064a\u0629 \u063a\u064a\u0631 \u0645\u0637\u0627\u0628\u0642\u0629 \u0644\u0644\u0635\u064a\u063a\u0629 \u0623\u0648 \u0627\u0644\u062a\u062d\u0642\u0642",
            category="\u0633\u0644\u0627\u0645\u0629 \u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u062d\u0633\u0627\u0628\u0627\u062a \u0627\u0644\u0628\u0646\u0643\u064a\u0629",
            description="\u0628\u0639\u0636 \u0623\u0631\u0642\u0627\u0645 \u0627\u0644\u062d\u0633\u0627\u0628\u0627\u062a \u0644\u0627 \u062a\u062d\u0642\u0642 \u0637\u0648\u0644 IBAN \u0627\u0644\u0633\u0639\u0648\u062f\u064a \u0623\u0648 \u0627\u062e\u062a\u0628\u0627\u0631 MOD-97.",
            evidence=f"\u0639\u062f\u062f \u0627\u0644\u0633\u062c\u0644\u0627\u062a \u0627\u0644\u0645\u062a\u0623\u062b\u0631\u0629: {len(invalid_iban)}\n" + "\n".join(f"{_location(r)}: ****{str(r.get('iban') or '')[-4:]}" for r in invalid_iban),
            recommendation="\u0637\u0627\u0628\u0642 \u0631\u0642\u0645 IBAN \u0645\u0639 \u0645\u0635\u062f\u0631 \u0645\u0635\u0631\u0641\u064a \u0645\u0648\u062b\u0648\u0642.",
            risk_level="\u0645\u062a\u0648\u0633\u0637",
            score=25,
            occurrence_count=len(invalid_iban),
        ))

    late_records = []
    for record in valid_records:
        match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", str(record.get("entry_time") or ""))
        if match:
            hour = int(match.group(1))
            if hour < 6 or hour >= 22:
                late_records.append(record)

    if late_records:
        findings.append(_make_finding(
            title="\u0625\u062f\u062e\u0627\u0644 \u0642\u064a\u0648\u062f \u0641\u064a \u0623\u0648\u0642\u0627\u062a \u0644\u064a\u0644\u064a\u0629 \u063a\u064a\u0631 \u0645\u0639\u062a\u0627\u062f\u0629",
            category="\u0645\u062e\u0627\u0637\u0631 \u0627\u0644\u062a\u0648\u0642\u064a\u062a \u0648\u0627\u0644\u0631\u0642\u0627\u0628\u0629",
            description="\u0631\u064f\u0635\u062f\u062a \u0642\u064a\u0648\u062f \u0623\u064f\u062f\u062e\u0644\u062a \u0628\u064a\u0646 22:00 \u0648 05:59.",
            evidence=f"\u0639\u062f\u062f \u0627\u0644\u0642\u064a\u0648\u062f: {len(late_records)}\n" + "\n".join(f"{_location(r)}? \u0627\u0644\u0648\u0642\u062a: {r.get('entry_time')}" for r in late_records),
            recommendation="\u062a\u062d\u0642\u0642 \u0645\u0646 \u0633\u062c\u0644 \u0627\u0644\u0646\u0638\u0627\u0645 \u0648\u0648\u062c\u0648\u062f \u062a\u0641\u0648\u064a\u0636 \u0644\u0644\u0639\u0645\u0644 \u062e\u0627\u0631\u062c \u0633\u0627\u0639\u0627\u062a \u0627\u0644\u062f\u0648\u0627\u0645.",
            risk_level="\u0645\u062a\u0648\u0633\u0637",
            score=15,
            occurrence_count=len(late_records),
        ))

    return findings

def _audit_ledger_records(records):
    """\u062a\u062f\u0642\u064a\u0642 \u0627\u0644\u0642\u064a\u0648\u062f \u0627\u0644\u0645\u062d\u0627\u0633\u0628\u064a\u0629 \u0648\u0627\u0644\u062d\u0631\u0643\u0627\u062a \u0627\u0644\u0628\u0646\u0643\u064a\u0629."""

    journal_records = [
        record for record in records
        if record.get("ledger_type") == "journal"
    ]

    if journal_records:
        findings = []
        journal_groups = defaultdict(list)

        missing_id_records = [
            record for record in journal_records
            if not record.get("journal_id")
        ]

        for record in journal_records:
            journal_id = record.get("journal_id")
            if journal_id:
                currency = _normalize_value(record.get("currency"))
                journal_groups[(journal_id, currency)].append(record)

        if missing_id_records:
            findings.append(_make_finding(
                title="\u0642\u064a\u0648\u062f \u0645\u062d\u0627\u0633\u0628\u064a\u0629 \u0628\u062f\u0648\u0646 \u0631\u0642\u0645 \u0642\u064a\u062f",
                category="\u0645\u0634\u0643\u0644\u0627\u062a \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0645\u062d\u0627\u0633\u0628\u064a\u0629",
                description="\u062a\u0648\u062c\u062f \u0633\u0637\u0648\u0631 \u0645\u062d\u0627\u0633\u0628\u064a\u0629 \u0644\u0627 \u062a\u062d\u062a\u0648\u064a \u0639\u0644\u0649 \u0631\u0642\u0645 \u0642\u064a\u062f.",
                evidence=(
                    f"\u0639\u062f\u062f \u0627\u0644\u0633\u0637\u0648\u0631: {len(missing_id_records)}\n"
                    + "\n".join(_location(record) for record in missing_id_records)
                ),
                recommendation="\u064a\u0631\u062c\u0649 \u062a\u062d\u062f\u064a\u062f \u0631\u0642\u0645 \u0642\u064a\u062f \u0644\u0643\u0644 \u0633\u0637\u0631.",
                risk_level="\u0645\u062a\u0648\u0633\u0637",
                score=25,
                occurrence_count=len(missing_id_records),
            ))

        for (journal_id, currency), group in journal_groups.items():
            invalid_amounts = [
                record for record in group
                if not record.get("amounts_valid")
            ]

            line_errors = [
                record for record in group
                if record.get("errors")
            ]

            if invalid_amounts:
                findings.append(_make_finding(
                    title="\u0645\u0628\u0627\u0644\u063a \u0627\u0644\u0642\u064a\u062f \u063a\u064a\u0631 \u0635\u0627\u0644\u062d\u0629",
                    category="\u0623\u062e\u0637\u0627\u0621 \u0627\u0644\u0642\u064a\u0648\u062f \u0627\u0644\u0645\u062d\u0627\u0633\u0628\u064a\u0629",
                    description="\u064a\u062d\u062a\u0648\u064a \u0627\u0644\u0642\u064a\u062f \u0639\u0644\u0649 \u0645\u0628\u0627\u0644\u063a \u0645\u0641\u0642\u0648\u062f\u0629 \u0623\u0648 \u063a\u064a\u0631 \u0635\u0627\u0644\u062d\u0629 \u0644\u0644\u062d\u0633\u0627\u0628.",
                    evidence=(
                        f"\u0631\u0642\u0645 \u0627\u0644\u0642\u064a\u062f: {journal_id}\n"
                        f"\u0627\u0644\u0639\u0645\u0644\u0629: {currency}\n"
                        + "\n".join(_location(record) for record in invalid_amounts)
                    ),
                    recommendation="\u064a\u0631\u062c\u0649 \u0645\u0631\u0627\u062c\u0639\u0629 \u0645\u0628\u0627\u0644\u063a \u0627\u0644\u0642\u064a\u062f \u0648\u062a\u0635\u062d\u064a\u062d\u0647\u0627.",
                    risk_level="\u0645\u0631\u062a\u0641\u0639",
                    score=40,
                    occurrence_count=len(invalid_amounts),
                ))
                continue

            debit_total = sum(
                (record["debit"] for record in group),
                Decimal("0"),
            )
            credit_total = sum(
                (record["credit"] for record in group),
                Decimal("0"),
            )
            difference = debit_total - credit_total

            if abs(difference) > Decimal("0.01"):
                findings.append(_make_finding(
                    title="\u0639\u062f\u0645 \u062a\u0648\u0627\u0632\u0646 \u0627\u0644\u0642\u064a\u062f \u0627\u0644\u0645\u062d\u0627\u0633\u0628\u064a",
                    category="\u0627\u0644\u062a\u062f\u0642\u064a\u0642 \u0627\u0644\u0645\u062d\u0627\u0633\u0628\u064a",
                    description="\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u062f\u064a\u0646 \u0644\u0627 \u064a\u0633\u0627\u0648\u064a \u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u062f\u0627\u0626\u0646 \u0641\u064a \u0647\u0630\u0627 \u0627\u0644\u0642\u064a\u062f.",
                    evidence=(
                        f"\u0631\u0642\u0645 \u0627\u0644\u0642\u064a\u062f: {journal_id}\n"
                        f"\u0627\u0644\u0639\u0645\u0644\u0629: {currency}\n"
                        f"\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u062f\u064a\u0646: {debit_total}\n"
                        f"\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u062f\u0627\u0626\u0646: {credit_total}\n"
                        f"\u0627\u0644\u0641\u0631\u0642: {abs(difference)}\n"
                        f"\u0639\u062f\u062f \u0627\u0644\u0633\u0637\u0648\u0631: {len(group)}\n"
                        + "\n".join(_location(record) for record in group)
                    ),
                    recommendation="\u064a\u0631\u062c\u0649 \u0645\u0631\u0627\u062c\u0639\u0629 \u0627\u0644\u0642\u064a\u062f \u0648\u062a\u0633\u0648\u064a\u0629 \u0627\u0644\u0641\u0631\u0642 \u0642\u0628\u0644 \u0627\u0639\u062a\u0645\u0627\u062f\u0647.",
                    risk_level="\u0645\u0631\u062a\u0641\u0639",
                    score=50,
                    occurrence_count=1,
                ))

            if line_errors:
                findings.append(_make_finding(
                    title="\u0623\u062e\u0637\u0627\u0621 \u0641\u064a \u062a\u0641\u0627\u0635\u064a\u0644 \u0627\u0644\u0642\u064a\u062f",
                    category="\u0623\u062e\u0637\u0627\u0621 \u0627\u0644\u0642\u064a\u0648\u062f \u0627\u0644\u0645\u062d\u0627\u0633\u0628\u064a\u0629",
                    description="\u064a\u0648\u062c\u062f \u062e\u0637\u0623 \u0641\u064a \u0628\u064a\u0627\u0646\u0627\u062a \u0623\u062d\u062f \u0623\u0633\u0637\u0631 \u0627\u0644\u0642\u064a\u062f \u0645\u062b\u0644 \u0627\u0644\u0645\u062f\u064a\u0646 \u0648\u0627\u0644\u062f\u0627\u0626\u0646 \u0623\u0648 \u0627\u0644\u0645\u0628\u0644\u063a.",
                    evidence=(
                        f"\u0631\u0642\u0645 \u0627\u0644\u0642\u064a\u062f: {journal_id}\n"
                        + "\n".join(
                            _location(record) + " - " + ", ".join(record["errors"])
                            for record in line_errors
                        )
                    ),
                    recommendation="\u064a\u0631\u062c\u0649 \u0645\u0631\u0627\u062c\u0639\u0629 \u062a\u0641\u0627\u0635\u064a\u0644 \u0627\u0644\u0642\u064a\u062f \u0648\u062a\u0635\u062d\u064a\u062d\u0647\u0627.",
                    risk_level="\u0645\u062a\u0648\u0633\u0637",
                    score=25,
                    occurrence_count=len(line_errors),
                ))

        return findings

    # Preserve existing bank transaction audit.
    findings = []
    valid_records = [
        record for record in records
        if record.get("is_valid")
    ]

    reference_groups = _group_values(valid_records, "reference")

    for reference, group in reference_groups.items():
        if len(group) < 2:
            continue

        findings.append(_make_finding(
            title="\u0645\u0631\u062c\u0639 \u062d\u0631\u0643\u0629 \u0628\u0646\u0643\u064a\u0629 \u0645\u0643\u0631\u0631",
            category="\u062a\u0643\u0631\u0627\u0631 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0628\u0646\u0643\u064a\u0629",
            description="\u062a\u0645 \u0627\u0644\u0639\u062b\u0648\u0631 \u0639\u0644\u0649 \u0645\u0631\u062c\u0639 \u0628\u0646\u0643\u064a \u0645\u0633\u062a\u062e\u062f\u0645 \u0641\u064a \u0623\u0643\u062b\u0631 \u0645\u0646 \u062d\u0631\u0643\u0629.",
            evidence=(
                f"\u0627\u0644\u0645\u0631\u062c\u0639: {reference}\n"
                f"\u0639\u062f\u062f \u0645\u0631\u0627\u062a \u0627\u0644\u0638\u0647\u0648\u0631: {len(group)}\n"
                + "\n".join(_location(record) for record in group)
            ),
            recommendation="\u064a\u0631\u062c\u0649 \u0645\u0631\u0627\u062c\u0639\u0629 \u0627\u0644\u0645\u0631\u062c\u0639 \u0627\u0644\u0628\u0646\u0643\u064a \u0648\u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0639\u062f\u0645 \u0627\u0633\u062a\u062e\u062f\u0627\u0645\u0647 \u0644\u0623\u0643\u062b\u0631 \u0645\u0646 \u062d\u0631\u0643\u0629.",
            risk_level="\u0645\u0631\u062a\u0641\u0639",
            score=40,
            occurrence_count=len(group),
        ))

    transaction_groups = defaultdict(list)

    for record in valid_records:
        fingerprint = (
            _normalize_value(record.get("transaction_date")),
            _normalize_value(record.get("description")),
            _normalize_amount(record.get("amount")),
            _normalize_value(record.get("direction")),
        )
        if not all(fingerprint):
            continue
        transaction_groups[fingerprint].append(record)

    for fingerprint, group in transaction_groups.items():
        if len(group) < 2:
            continue

        transaction_date, description, amount, direction = fingerprint
        locations = [_location(record) for record in group]
        references = [
            _normalize_value(record.get("reference")) or "\u063a\u064a\u0631 \u0645\u062a\u0648\u0641\u0631"
            for record in group
        ]

        findings.append(_make_finding(
            title="\u062d\u0631\u0643\u0629 \u0628\u0646\u0643\u064a\u0629 \u0645\u0643\u0631\u0631\u0629 \u0645\u062d\u062a\u0645\u0644\u0629",
            category="\u062a\u0643\u0631\u0627\u0631 \u0627\u0644\u062d\u0631\u0643\u0627\u062a \u0627\u0644\u0628\u0646\u0643\u064a\u0629",
            description="\u062a\u0645 \u0627\u0644\u0639\u062b\u0648\u0631 \u0639\u0644\u0649 \u062d\u0631\u0643\u0627\u062a \u0644\u0647\u0627 \u0627\u0644\u062a\u0627\u0631\u064a\u062e \u0648\u0627\u0644\u0648\u0635\u0641 \u0648\u0627\u0644\u0645\u0628\u0644\u063a \u0648\u0627\u0644\u0627\u062a\u062c\u0627\u0647 \u0646\u0641\u0633\u0647\u0627. \u064a\u0644\u0632\u0645 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0627\u062d\u062a\u0645\u0627\u0644 \u062a\u0643\u0631\u0627\u0631\u0647\u0627.",
            evidence=(
                f"\u0627\u0644\u062a\u0627\u0631\u064a\u062e: {transaction_date}\n"
                f"\u0627\u0644\u0648\u0635\u0641: {description}\n"
                f"\u0627\u0644\u0645\u0628\u0644\u063a: {amount}\n"
                f"\u0627\u0644\u0627\u062a\u062c\u0627\u0647: {direction}\n"
                f"\u0627\u0644\u0645\u0631\u0627\u062c\u0639: {' | '.join(references)}\n"
                f"\u0639\u062f\u062f \u0645\u0631\u0627\u062a \u0627\u0644\u0638\u0647\u0648\u0631: {len(group)}\n"
                + "\n".join(locations)
            ),
            recommendation="\u064a\u0631\u062c\u0649 \u0645\u0642\u0627\u0631\u0646\u0629 \u0627\u0644\u062d\u0631\u0643\u0627\u062a \u0645\u0639 \u0643\u0634\u0641 \u0627\u0644\u0628\u0646\u0643 \u0627\u0644\u0623\u0635\u0644\u064a \u0648\u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0639\u062f\u0645 \u062a\u0646\u0641\u064a\u0630 \u0627\u0644\u0639\u0645\u0644\u064a\u0629 \u0623\u0643\u062b\u0631 \u0645\u0646 \u0645\u0631\u0629.",
            risk_level="\u0645\u0631\u062a\u0641\u0639",
            score=45,
            occurrence_count=len(group),
        ))

    return findings


def _extract_page_records(file_path):
    records = []

    pages = extract_pdf_pages(file_path)

    for page in pages:
        text = page.get("raw_text", "")

        if not text.strip():
            continue

        invoice_number = extract_invoice_number(text)
        supplier_name = extract_supplier_name(text)
        invoice_date = extract_invoice_date(text)
        amount = extract_amount(text)
        tax_amount = extract_tax_amount(text)
        currency = extract_currency(text)

        if not any((
            invoice_number,
            supplier_name,
            invoice_date,
            amount is not None,
            tax_amount is not None,
        )):
            continue

        records.append({
            "invoice_number": invoice_number,
            "supplier_name": supplier_name,
            "invoice_date": invoice_date.isoformat() if invoice_date else None,
            "amount": str(amount) if amount is not None else None,
            "tax_amount": str(tax_amount) if tax_amount is not None else None,
            "currency": currency,
            "reference": None,
            "description": None,
            "page_number": page.get("page_number"),
        })

    return records




def _has_populated_audit_notes(file_path):
    header = bytes.fromhex(
        "d8 b1 d9 82 d9 85 20 d8 a7 d9 84 d9 85 d9 84 d8 a7 d8 ad d8 b8 d8 a9"
    ).decode("utf-8")

    sheets = pd.read_excel(
        file_path, sheet_name=None, header=None, dtype=object
    )

    for frame in sheets.values():
        for i in range(len(frame)):
            value = frame.iloc[i, 0]

            if pd.isna(value) or str(value).strip() != header:
                continue

            for _, row in frame.iloc[i + 1:].iterrows():
                first = row.iloc[0]
                if pd.notna(first) and str(first).strip():
                    return True

            return False

    return False


def _audit_multisheet_workbook(file_path):
    findings = []
    sheets = pd.read_excel(file_path, sheet_name=None, header=None, dtype=object)

    def key(value):
        if value is None or pd.isna(value):
            return ""
        return re.sub(r"[\s_\-:/()%]+", "", normalize_text(str(value))).casefold()

    def number(value):
        if value is None or pd.isna(value) or str(value).strip() == "":
            return None
        try:
            return Decimal(str(value).replace(",", ""))
        except (InvalidOperation, ValueError):
            return None

    for sheet_name, frame in sheets.items():
        header_index = None
        headers = []

        for index in range(min(15, len(frame))):
            candidate = [key(value) for value in frame.iloc[index].tolist()]
            if any(value in candidate for value in (
                "\u0631\u0642\u0645\u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629",
                "\u0627\u0644\u0645\u0631\u062c\u0639\u0627\u0644\u0628\u0646\u0643\u064a",
                "\u0631\u0642\u0645\u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0629",
            )):
                header_index = index
                headers = candidate
                break

        if header_index is None:
            continue

        columns = {value: i for i, value in enumerate(headers) if value}

        def get(row, label):
            index = columns.get(key(label))
            if index is None or index >= len(row):
                return None
            value = row.iloc[index]
            return None if pd.isna(value) else value

        invoice_sheet = key("\u0631\u0642\u0645 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629") in columns
        bank_sheet = key("\u0627\u0644\u0645\u0631\u062c\u0639 \u0627\u0644\u0628\u0646\u0643\u064a") in columns
        notes_sheet = key("\u0631\u0642\u0645 \u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0629") in columns

        for row_index in range(header_index + 1, len(frame)):
            row = frame.iloc[row_index]
            row_number = row_index + 1

            if invoice_sheet:
                invoice_id = get(row, "\u0631\u0642\u0645 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629")
                if invoice_id is None or key(invoice_id) == key("\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a"):
                    continue

                amount = number(get(row, "\u0627\u0644\u0645\u0628\u0644\u063a \u0642\u0628\u0644 \u0627\u0644\u0636\u0631\u064a\u0628\u0629"))
                rate = number(get(row, "\u0646\u0633\u0628\u0629 \u0627\u0644\u0636\u0631\u064a\u0628\u0629 %"))
                tax = number(get(row, "\u0642\u064a\u0645\u0629 \u0627\u0644\u0636\u0631\u064a\u0628\u0629"))
                total = number(get(row, "\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a \u0634\u0627\u0645\u0644 \u0627\u0644\u0636\u0631\u064a\u0628\u0629"))

                missing = []
                if tax is None:
                    missing.append("\u0642\u064a\u0645\u0629 \u0627\u0644\u0636\u0631\u064a\u0628\u0629")
                if total is None:
                    missing.append("\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a \u0634\u0627\u0645\u0644 \u0627\u0644\u0636\u0631\u064a\u0628\u0629")
                if not missing:
                    continue

                expected = ""
                if amount is not None and rate is not None:
                    if rate > 1:
                        rate /= Decimal("100")
                    expected_tax = (amount * rate).quantize(Decimal("0.01"))
                    expected_total = (amount + expected_tax).quantize(Decimal("0.01"))
                    expected = (
                        f"\n\u0627\u0644\u0636\u0631\u064a\u0628\u0629 \u0627\u0644\u0645\u062a\u0648\u0642\u0639\u0629: {expected_tax}"
                        f"\n\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u062a\u0648\u0642\u0639: {expected_total}"
                    )

                finding = _make_finding(
                    title="\u0628\u064a\u0627\u0646\u0627\u062a \u0636\u0631\u064a\u0628\u064a\u0629 \u0646\u0627\u0642\u0635\u0629",
                    category="\u0645\u0631\u0627\u062c\u0639\u0629 \u0627\u0644\u0641\u0648\u0627\u062a\u064a\u0631",
                    description="\u062d\u0642\u0648\u0644 \u0636\u0631\u064a\u0628\u064a\u0629 \u0623\u0633\u0627\u0633\u064a\u0629 \u063a\u064a\u0631 \u0645\u0633\u062c\u0644\u0629 \u0641\u064a \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629.",
                    evidence=(
                        f"\u0631\u0642\u0645 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629: {invoice_id}\n"
                        f"\u0627\u0644\u062d\u0642\u0648\u0644 \u0627\u0644\u0646\u0627\u0642\u0635\u0629: {', '.join(missing)}"
                        f"\n\u0627\u0644\u0648\u0631\u0642\u0629: {sheet_name}\u060c \u0627\u0644\u0635\u0641: {row_number}"
                        f"{expected}"
                    ),
                    recommendation="\u0627\u0633\u062a\u0643\u0645\u0627\u0644 \u0627\u0644\u062d\u0642\u0648\u0644 \u0627\u0644\u0636\u0631\u064a\u0628\u064a\u0629 \u0648\u0645\u0637\u0627\u0628\u0642\u062a\u0647\u0627 \u0645\u0639 \u0627\u0644\u0645\u0633\u062a\u0646\u062f \u0627\u0644\u0623\u0635\u0644\u064a.",
                    risk_level="\u0645\u062a\u0648\u0633\u0637",
                    score=10,
                    occurrence_count=1,
                )
                finding.update(source_type="system_rule", source_sheet=str(sheet_name), source_row=row_number)
                findings.append(finding)

            elif bank_sheet:
                reference = get(row, "\u0627\u0644\u0645\u0631\u062c\u0639 \u0627\u0644\u0628\u0646\u0643\u064a")
                if reference is None:
                    continue

                book = number(get(row, "\u0627\u0644\u0631\u0635\u064a\u062f \u062d\u0633\u0628 \u0627\u0644\u062f\u0641\u0627\u062a\u0631"))
                bank = number(get(row, "\u0627\u0644\u0631\u0635\u064a\u062f \u062d\u0633\u0628 \u0643\u0634\u0641 \u0627\u0644\u0628\u0646\u0643"))
                difference = number(get(row, "\u0627\u0644\u0641\u0631\u0642"))
                status = str(get(row, "\u062d\u0627\u0644\u0629 \u0627\u0644\u0645\u0637\u0627\u0628\u0642\u0629") or "")

                if difference is None and book is not None and bank is not None:
                    difference = book - bank
                if difference is None or difference == 0:
                    continue

                finding = _make_finding(
                    title="\u0641\u0631\u0642 \u0641\u064a \u0627\u0644\u062a\u0633\u0648\u064a\u0629 \u0627\u0644\u0628\u0646\u0643\u064a\u0629",
                    category="\u0645\u0637\u0627\u0628\u0642\u0629 \u0627\u0644\u0628\u0646\u0648\u0643",
                    description="\u0647\u0646\u0627\u0643 \u0641\u0631\u0642 \u0628\u064a\u0646 \u0631\u0635\u064a\u062f \u0627\u0644\u062f\u0641\u0627\u062a\u0631 \u0648\u0643\u0634\u0641 \u0627\u0644\u0628\u0646\u0643.",
                    evidence=(
                        f"\u0627\u0644\u0645\u0631\u062c\u0639: {reference}\n"
                        f"\u0631\u0635\u064a\u062f \u0627\u0644\u062f\u0641\u0627\u062a\u0631: {book}\n"
                        f"\u0631\u0635\u064a\u062f \u0627\u0644\u0628\u0646\u0643: {bank}\n"
                        f"\u0627\u0644\u0641\u0631\u0642: {difference}\n"
                        f"\u0627\u0644\u062d\u0627\u0644\u0629: {status}\n"
                        f"\u0627\u0644\u0648\u0631\u0642\u0629: {sheet_name}\u060c \u0627\u0644\u0635\u0641: {row_number}"
                    ),
                    recommendation="\u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0633\u0628\u0628 \u0627\u0644\u0641\u0631\u0642 \u0648\u062a\u0633\u062c\u064a\u0644 \u0642\u064a\u062f \u0627\u0644\u062a\u0633\u0648\u064a\u0629 \u0627\u0644\u0644\u0627\u0632\u0645.",
                    risk_level="\u0645\u062a\u0648\u0633\u0637",
                    score=25,
                    occurrence_count=1,
                )
                finding.update(source_type="system_rule", source_sheet=str(sheet_name), source_row=row_number)
                findings.append(finding)

            elif notes_sheet:
                note_id = get(row, "\u0631\u0642\u0645 \u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0629")
                if note_id is None:
                    continue

                severity = str(get(row, "\u062f\u0631\u062c\u0629 \u0627\u0644\u062e\u0637\u0648\u0631\u0629") or "")
                severity_key = key(severity)
                recorded_risk = (
                    "\u0645\u0631\u062a\u0641\u0639" if "\u0645\u0631\u062a\u0641\u0639" in severity_key
                    else "\u0645\u062a\u0648\u0633\u0637" if "\u0645\u062a\u0648\u0633\u0637" in severity_key
                    else "\u0645\u0646\u062e\u0641\u0636"
                )

                finding = _make_finding(
                    title="\u0645\u0644\u0627\u062d\u0638\u0629 \u062a\u062f\u0642\u064a\u0642 \u0645\u0633\u062c\u0644\u0629 \u0641\u064a \u0627\u0644\u0645\u0633\u062a\u0646\u062f",
                    category="\u0645\u0644\u0627\u062d\u0638\u0627\u062a \u0645\u0633\u062c\u0644\u0629 \u0641\u064a \u0627\u0644\u0645\u0633\u062a\u0646\u062f",
                    description=str(get(row, "\u0648\u0635\u0641 \u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0629") or ""),
                    evidence=(
                        f"\u0631\u0642\u0645 \u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0629: {note_id}\n"
                        f"\u0646\u0648\u0639 \u0627\u0644\u0645\u062e\u0627\u0644\u0641\u0629: {get(row, '\u0646\u0648\u0639 \u0627\u0644\u0645\u062e\u0627\u0644\u0641\u0629')}\n"
                        f"\u0627\u0644\u0623\u062b\u0631 \u0627\u0644\u0645\u0627\u0644\u064a: {get(row, '\u0627\u0644\u0623\u062b\u0631 \u0627\u0644\u0645\u0627\u0644\u064a')}\n"
                        f"\u0627\u0644\u062d\u0627\u0644\u0629: {get(row, '\u062d\u0627\u0644\u0629 \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629')}"
                    ),
                    recommendation=str(get(row, "\u0627\u0644\u062a\u0648\u0635\u064a\u0629 \u0627\u0644\u0645\u062d\u0627\u0633\u0628\u064a\u0629") or ""),
                    risk_level=recorded_risk,
                    score=0,
                    occurrence_count=1,
                )
                finding.update(
                    source_type="document_audit_note",
                    source_sheet=str(sheet_name),
                    source_row=row_number,
                    financial_impact=str(get(row, "\u0627\u0644\u0623\u062b\u0631 \u0627\u0644\u0645\u0627\u0644\u064a") or ""),
                    treatment_status=str(get(row, "\u062d\u0627\u0644\u0629 \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629") or ""),
                )
                findings.append(finding)

    return findings


def audit_document(file_path: str | Path) -> dict:
    """تدقيق محتوى المستند بالكامل دون تفكيكه إلى سجلات قاعدة بيانات."""

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError("الملف غير موجود")

    extension = file_path.suffix.lower()
    text = extract_raw_text(file_path) or ""

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    records = []
    findings = []

    if extension in {".xlsx", ".xls", ".csv"}:
        expense_records = []

        try:
            expense_records = extract_expense_register_records(file_path)
        except (ValueError, KeyError, TypeError):
            expense_records = []

        if expense_records:
            records = [
                record for record in expense_records
                if record.get("is_valid")
            ]
            findings = _audit_expense_register_records(expense_records)

        else:
            ledger_records = []

            try:
                ledger_records = extract_journal_records(file_path)
            except (ValueError, KeyError, TypeError):
                ledger_records = []

            if ledger_records:
                records = [
                    record for record in ledger_records
                    if record.get("is_valid")
                ]
                findings = _audit_ledger_records(ledger_records)

            else:
                try:
                    records = extract_tabular_records(file_path)
                except Exception:
                    records = []

                findings = _audit_invoice_records(records)

        if extension in {".xlsx", ".xls"} and _has_populated_audit_notes(file_path):
            findings.extend(_audit_multisheet_workbook(file_path))

    elif extension == ".pdf":
        records = _extract_page_records(file_path)
        findings = _audit_invoice_records(records)

    elif extension in {".png", ".jpg", ".jpeg"}:
        invoice_number = extract_invoice_number(text)
        supplier_name = extract_supplier_name(text)
        invoice_date = extract_invoice_date(text)
        amount = extract_amount(text)
        tax_amount = extract_tax_amount(text)

        if any((
            invoice_number,
            supplier_name,
            invoice_date,
            amount is not None,
            tax_amount is not None,
        )):
            records.append({
                "invoice_number": invoice_number,
                "supplier_name": supplier_name,
                "invoice_date": invoice_date.isoformat() if invoice_date else None,
                "amount": str(amount) if amount is not None else None,
                "tax_amount": str(tax_amount) if tax_amount is not None else None,
                "reference": None,
                "description": None,
            })

        findings = _audit_invoice_records(records)

    score = min(100, sum(item["score"] for item in findings))

    if any(item.get("risk_level") == "\u0645\u0631\u062a\u0641\u0639" for item in findings):
        risk_level = "\u0645\u0631\u062a\u0641\u0639"
    elif score >= 30:
        risk_level = "\u0645\u062a\u0648\u0633\u0637"
    else:
        risk_level = "\u0645\u0646\u062e\u0641\u0636"

    duplicate_findings = [
        item for item in findings
        if any(
            marker in str(item.get(field) or "").lower()
            for field in ("title", "category")
            for marker in ("\u062a\u0643\u0631\u0627\u0631", "\u0645\u0643\u0631\u0631", "duplicate")
        )
    ]
    duplicate_count = sum(
        int(item.get("occurrence_count") or 1)
        for item in duplicate_findings
    )

    summary = (
        "\u0627\u0643\u062a\u0645\u0644 \u0641\u062d\u0635 \u0645\u062d\u062a\u0648\u0649 \u0627\u0644\u0645\u0633\u062a\u0646\u062f \u0628\u0627\u0644\u0643\u0627\u0645\u0644. "
        f"\u0639\u062f\u062f \u0627\u0644\u0623\u062d\u0631\u0641 \u0627\u0644\u0645\u0633\u062a\u062e\u0631\u062c\u0629: {len(text)}\u060c "
        f"\u0639\u062f\u062f \u0627\u0644\u0623\u0633\u0637\u0631: {len(lines)}\u060c "
        f"\u0639\u062f\u062f \u0627\u0644\u0633\u062c\u0644\u0627\u062a \u0627\u0644\u062a\u064a \u0623\u0645\u0643\u0646 \u062a\u062d\u0644\u064a\u0644\u0647\u0627: {len(records)}\u060c "
        f"\u0639\u062f\u062f \u062d\u0627\u0644\u0627\u062a \u0627\u0644\u062a\u0643\u0631\u0627\u0631 \u0627\u0644\u0645\u0643\u062a\u0634\u0641\u0629: {duplicate_count}."
    )

    if not records:
        summary += (
            " لم يتمكن النظام من استخراج سجلات منظمة "
            "كافية لاكتشاف التكرارات."
        )

    return {
        "summary": summary,
        "risk_level": risk_level,
        "risk_score": score,
        "extracted_chars": len(text),
        "line_count": len(lines),
        "findings": findings,
    }


def _extract_comparison_records(file_path):
    """استخراج سجلات المقارنة مع الاحتفاظ بجميع أعمدة الملف الأصلي."""
    file_path = Path(file_path)
    extension = file_path.suffix.lower()

    if extension in {".xlsx", ".xls", ".csv"}:
        # قراءة جميع الأعمدة الأصلية من الملف
        try:
            if extension == ".csv":
                raw_sheets = {
                    "CSV": pd.read_csv(
                        file_path,
                        dtype=str,
                        encoding="utf-8-sig",
                    ).fillna("")
                }
            else:
                raw_sheets = pd.read_excel(
                    file_path,
                    sheet_name=None,
                    dtype=str,
                )

                raw_sheets = {
                    sheet_name: frame.fillna("")
                    for sheet_name, frame in raw_sheets.items()
                }
        except Exception as exc:
            raise ValueError(
                f"تعذر قراءة بيانات المستند للمقارنة: {exc}"
            )

        # استخراج السجلات المحاسبية بالطريقة الحالية
        try:
            ledger_records = extract_journal_records(file_path)
        except Exception:
            ledger_records = []

        valid_ledger = [
            record for record in ledger_records
            if record.get("is_valid")
        ]

        if valid_ledger:
            record_type = "ledger"
            records = valid_ledger
        else:
            try:
                records = extract_tabular_records(file_path)
            except Exception:
                records = []

            record_type = "invoice"

        # ربط السجل المستخرج بصفه الأصلي وإضافة جميع أعمدة الصف
        raw_rows = {}

        for sheet_name, frame in raw_sheets.items():
            for index, row in frame.iterrows():
                source_row = index + 2

                raw_fields = {
                    str(column): str(value)
                    for column, value in row.items()
                }

                # تجاهل الصفوف الفارغة فقط
                if not any(value.strip() for value in raw_fields.values()):
                    continue

                raw_rows[(str(sheet_name), source_row)] = raw_fields

        enriched_records = []

        for record in records:
            enriched = dict(record)

            sheet_name = str(record.get("source_sheet", "CSV"))
            source_row = record.get("source_row")

            try:
                source_row = int(source_row)
            except (TypeError, ValueError):
                source_row = None

            raw_fields = (
                raw_rows.get((sheet_name, source_row), {})
                if source_row is not None
                else {}
            )

            enriched["source_fields"] = raw_fields
            enriched_records.append(enriched)

        return record_type, enriched_records

    if extension == ".pdf":
        return "invoice", _extract_page_records(file_path)

    if extension in {".png", ".jpg", ".jpeg"}:
        text = extract_raw_text(file_path) or ""

        invoice_number = extract_invoice_number(text)
        supplier_name = extract_supplier_name(text)
        invoice_date = extract_invoice_date(text)
        amount = extract_amount(text)

        records = []

        if any((invoice_number, supplier_name, invoice_date, amount is not None)):
            records.append({
                "invoice_number": invoice_number,
                "supplier_name": supplier_name,
                "invoice_date": invoice_date.isoformat() if invoice_date else None,
                "amount": str(amount) if amount is not None else None,
                "reference": None,
                "description": None,
            })

        return "invoice", records

    raise ValueError("نوع المستند غير مدعوم للمقارنة")


def _comparison_match(first, second, record_type):
    """إرجاع سبب المطابقة، أو None إذا لم يوجد تطابق مؤكد."""

    if record_type == "ledger":
        first_reference = _normalize_value(first.get("reference"))
        second_reference = _normalize_value(second.get("reference"))

        if first_reference and first_reference == second_reference:
            return {
                "match_type": "تطابق رقم المرجع",
                "matched_value": first_reference,
            }

        fingerprint_fields = (
            _normalize_value(first.get("transaction_date")),
            _normalize_value(first.get("description")),
            _normalize_amount(first.get("amount")),
            _normalize_value(first.get("direction")),
        )

        second_fingerprint = (
            _normalize_value(second.get("transaction_date")),
            _normalize_value(second.get("description")),
            _normalize_amount(second.get("amount")),
            _normalize_value(second.get("direction")),
        )

        if all(fingerprint_fields) and fingerprint_fields == second_fingerprint:
            return {
                "match_type": "تطابق بيانات الحركة",
                "matched_value": {
                    "date": fingerprint_fields[0],
                    "description": fingerprint_fields[1],
                    "amount": fingerprint_fields[2],
                    "direction": fingerprint_fields[3],
                },
            }

        return None

    first_number = _normalize_invoice_number(first.get("invoice_number"))
    second_number = _normalize_invoice_number(second.get("invoice_number"))

    if first_number and first_number == second_number:
        return {
            "match_type": "تطابق رقم الفاتورة",
            "matched_value": first_number,
        }

    fingerprint_fields = (
        _normalize_value(first.get("supplier_name")),
        _normalize_value(first.get("invoice_date")),
        _normalize_amount(first.get("amount")),
    )

    second_fingerprint = (
        _normalize_value(second.get("supplier_name")),
        _normalize_value(second.get("invoice_date")),
        _normalize_amount(second.get("amount")),
    )

    if all(fingerprint_fields) and fingerprint_fields == second_fingerprint:
        return {
            "match_type": "تطابق بيانات الفاتورة",
            "matched_value": {
                "supplier": fingerprint_fields[0],
                "date": fingerprint_fields[1],
                "amount": fingerprint_fields[2],
            },
        }

    return None





def _reconciliation_label(value):
    value = normalize_text(str(value or "")).casefold()
    value = re.sub(r"[\u064b-\u065f]", "", value)
    return re.sub(r"[^\w]", "", value)


def _reconciliation_amount(value):
    if value is None:
        return None

    text = normalize_text(str(value))
    text = text.replace(",", "").replace("\u066c", "").replace("\u066b", ".")
    text = re.sub(r"[^\d.\-]", "", text)

    if not text:
        return None

    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _read_reconciliation_document(file_path):
    file_path = Path(file_path)
    extension = file_path.suffix.lower()

    if extension == ".csv":
        try:
            frame = pd.read_csv(
                file_path, header=None, dtype=str,
                encoding="utf-8-sig", sep=None, engine="python"
            ).fillna("")
        except Exception:
            frame = pd.read_csv(
                file_path, header=None, dtype=str, encoding="cp1252"
            ).fillna("")
        sheets = {"CSV": frame}
    elif extension in {".xlsx", ".xls"}:
        sheets = pd.read_excel(
            file_path, sheet_name=None, header=None, dtype=str
        )
        sheets = {name: frame.fillna("") for name, frame in sheets.items()}
    else:
        return None

    bank_aliases = {
        "reference": {"\u0627\u0644\u0645\u0631\u062c\u0639\u0627\u0644\u0628\u0646\u0643\u064a"},
        "date": {"\u062a\u0627\u0631\u064a\u062e\u0627\u0644\u062a\u0646\u0641\u064a\u0630"},
        "description": {"\u0627\u0644\u062c\u0647\u0629\u0627\u0644\u0645\u0633\u062a\u0641\u064a\u062f\u0629"},
        "amount": {"\u0627\u0644\u0645\u0628\u0644\u063a\u0627\u0644\u0645\u062e\u0635\u0648\u0645"},
        "record_id": {"\u0631\u0642\u0645\u0627\u0644\u0639\u0645\u0644\u064a\u0629\u0627\u0644\u0628\u0646\u0643\u064a\u0629"},
        "status": {"\u062d\u0627\u0644\u0629\u0627\u0644\u0639\u0645\u0644\u064a\u0629"},
    }
    ledger_aliases = {
        "reference": {"\u0631\u0642\u0645\u0627\u0644\u0645\u0631\u062c\u0639\u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629"},
        "date": {"\u0627\u0644\u062a\u0627\u0631\u064a\u062e"},
        "description": {
            "\u0627\u0633\u0645\u0627\u0644\u0645\u0648\u0631\u062f\u0627\u0644\u062c\u0647\u0629",
            "\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u0644\u0648\u0635\u0641",
        },
        "amount": {"\u0627\u0644\u0645\u0628\u0644\u063a\u0627\u0644\u0645\u0633\u062c\u0644"},
        "record_id": {"\u0631\u0642\u0645\u0627\u0644\u0642\u064a\u062f"},
        "status": {"\u062d\u0627\u0644\u0629\u0627\u0644\u0627\u0639\u062a\u0645\u0627\u062f"},
    }

    documents = []

    for sheet_name, frame in sheets.items():
        if frame.empty:
            continue

        header_index = None
        columns = None
        role = None

        for row_index in range(min(30, len(frame))):
            labels = [
                _reconciliation_label(value)
                for value in frame.iloc[row_index].tolist()
            ]

            for candidate_role, aliases in (
                ("bank", bank_aliases),
                ("ledger", ledger_aliases),
            ):
                mapping = {}
                for field, accepted in aliases.items():
                    for column_index, label in enumerate(labels):
                        if label in accepted:
                            mapping[field] = column_index
                            break

                if {"reference", "date", "amount", "record_id"}.issubset(mapping):
                    header_index = row_index
                    columns = mapping
                    role = candidate_role
                    break

            if role:
                break

        if role is None:
            continue

        records = []
        for row_index in range(header_index + 1, len(frame)):
            row = frame.iloc[row_index]

            def cell(field):
                index = columns.get(field)
                if index is None or index >= len(row):
                    return ""
                value = row.iloc[index]
                return str(value).strip() if value is not None else ""

            reference = cell("reference")
            amount = _reconciliation_amount(cell("amount"))

            if not reference or amount is None:
                continue

            records.append({
                "reference": reference,
                "normalized_reference": _normalize_invoice_number(reference),
                "date": cell("date"),
                "description": cell("description"),
                "amount": amount,
                "record_id": cell("record_id"),
                "status": cell("status"),
                "source_sheet": str(sheet_name),
                "source_row": int(row_index + 1),
            })

        if records:
            documents.append({"role": role, "records": records})

    roles = {item["role"] for item in documents}
    if len(roles) != 1:
        return None

    combined = []
    for item in documents:
        combined.extend(item["records"])

    return next(iter(roles)), combined


def _reconciliation_record_output(record):
    result = dict(record)
    result["amount"] = float(record["amount"])
    result["location"] = _location(record)
    return result


def reconcile_uploaded_documents(first_path, second_path):
    """Reconcile uploaded bank statement and ledger files without database writes."""
    first = _read_reconciliation_document(first_path)
    second = _read_reconciliation_document(second_path)

    if first is None or second is None or first[0] == second[0]:
        return None

    bank_records = first[1] if first[0] == "bank" else second[1]
    ledger_records = first[1] if first[0] == "ledger" else second[1]

    if not bank_records or not ledger_records:
        return None

    ledger_by_reference = defaultdict(list)
    for index, record in enumerate(ledger_records):
        ledger_by_reference[record["normalized_reference"]].append((index, record))

    used_ledger_ids = set()
    matched_bank_ids = set()
    matches = []
    duplicates = []
    variances = []

    for bank_index, bank in enumerate(bank_records):
        reference = bank["normalized_reference"]
        candidates = [
            item for item in ledger_by_reference.get(reference, [])
            if item[0] not in used_ledger_ids
        ]

        if not candidates:
            continue

        exact = [
            item for item in candidates
            if item[1]["amount"] == bank["amount"]
        ]
        chosen_index, chosen = exact[0] if exact else candidates[0]

        used_ledger_ids.add(chosen_index)
        matched_bank_ids.add(bank_index)

        if chosen["amount"] == bank["amount"]:
            matches.append({
                "match_id": len(matches) + 1,
                "match_type": "\u062a\u0637\u0627\u0628\u0642\u062a\u0627\u0645",
                "matched_value": reference,
                "bank_record": _reconciliation_record_output(bank),
                "ledger_record": _reconciliation_record_output(chosen),
            })
        else:
            difference = chosen["amount"] - bank["amount"]
            variances.append({
                "finding_id": len(variances) + 1,
                "reference": bank["reference"],
                "difference": float(difference),
                "severity": "high",
                "message": "\u0627\u062e\u062a\u0644\u0627\u0641\u0641\u064a\u0645\u0628\u0644\u063a\u0627\u0644\u0642\u064a\u062f\u0648\u0627\u0644\u062d\u0631\u0643\u0629\u0627\u0644\u0628\u0646\u0643\u064a\u0629",
                "bank_record": _reconciliation_record_output(bank),
                "ledger_record": _reconciliation_record_output(chosen),
            })

        for duplicate_index, duplicate in candidates:
            if duplicate_index == chosen_index:
                continue
            used_ledger_ids.add(duplicate_index)
            duplicates.append({
                "finding_id": len(duplicates) + 1,
                "reference": duplicate["reference"],
                "severity": "high",
                "message": "\u0642\u064a\u062f\u0645\u062d\u0627\u0633\u0628\u064a\u0625\u0636\u0627\u0641\u064a\u0644\u0646\u0641\u0633\u0627\u0644\u0645\u0631\u062c\u0639",
                "bank_record": _reconciliation_record_output(bank),
                "ledger_record": _reconciliation_record_output(duplicate),
            })

    ledger_only = [
        _reconciliation_record_output(record)
        for index, record in enumerate(ledger_records)
        if index not in used_ledger_ids
    ]
    bank_only = [
        _reconciliation_record_output(record)
        for index, record in enumerate(bank_records)
        if index not in matched_bank_ids
    ]

    bank_total = sum((record["amount"] for record in bank_records), Decimal("0"))
    ledger_total = sum((record["amount"] for record in ledger_records), Decimal("0"))
    total_difference = ledger_total - bank_total

    return {
        "status": "completed",
        "record_type": "bank_reconciliation",
        "bank_record_count": len(bank_records),
        "ledger_record_count": len(ledger_records),
        "first_record_count": len(first[1]),
        "second_record_count": len(second[1]),
        "match_count": len(matches),
        "duplicate_count": len(duplicates),
        "variance_count": len(variances),
        "ledger_only_count": len(ledger_only),
        "bank_only_count": len(bank_only),
        "bank_total": float(bank_total),
        "ledger_total": float(ledger_total),
        "total_difference": float(total_difference),
        "matches": matches,
        "duplicates": duplicates,
        "variances": variances,
        "ledger_only": ledger_only,
        "bank_only": bank_only,
        "summary": (
            f"\u0627\u0644\u062a\u0637\u0627\u0628\u0642\u0627\u062a: {len(matches)}\u060c "
            f"\u0627\u0644\u0642\u064a\u0648\u062f\u0627\u0644\u0645\u0643\u0631\u0631\u0629: {len(duplicates)}\u060c "
            f"\u0641\u0631\u0648\u0642\u0627\u0644\u0645\u0628\u0627\u0644\u063a: {len(variances)}\u060c "
            f"\u0642\u064a\u0648\u062f\u0628\u0644\u0627\u062d\u0631\u0643\u0629\u0628\u0646\u0643\u064a\u0629: {len(ledger_only)}\u060c "
            f"\u062d\u0631\u0643\u0627\u062a\u0628\u0646\u0643\u064a\u0629\u0628\u0644\u0627\u0642\u064a\u062f: {len(bank_only)}."
        ),
    }


def compare_documents(first_path, second_path):
    """مقارنة محتوى مستندين وإرجاع السجلات المتطابقة ومواقعها."""

    first_path = Path(first_path)
    second_path = Path(second_path)

    if not first_path.is_file() or not second_path.is_file():
        raise FileNotFoundError("تعذر العثور على أحد ملفات المستندات")

    first_type, first_records = _extract_comparison_records(first_path)
    second_type, second_records = _extract_comparison_records(second_path)

    if first_type != second_type:
        return {
            "status": "incompatible",
            "message": "لا يمكن مقارنة مستند فواتير مع مستند حركات بنكية.",
            "first_record_count": len(first_records),
            "second_record_count": len(second_records),
            "match_count": 0,
            "matches": [],
        }

    matches = []

    for first_index, first_record in enumerate(first_records):
        for second_index, second_record in enumerate(second_records):
            match = _comparison_match(
                first_record,
                second_record,
                first_type,
            )

            if match is None:
                continue

            matches.append({
                "match_id": len(matches) + 1,
                "match_type": match["match_type"],
                "matched_value": match["matched_value"],
                "first_location": _location(first_record),
                "second_location": _location(second_record),
                "first_record": first_record,
                "second_record": second_record,
            })

    return {
        "status": "completed",
        "record_type": first_type,
        "first_record_count": len(first_records),
        "second_record_count": len(second_records),
        "match_count": len(matches),
        "matches": matches,
        "summary": (
            f"تمت مقارنة المستندين. "
            f"عدد سجلات المستند الأول: {len(first_records)}، "
            f"والمستند الثاني: {len(second_records)}، "
            f"وعدد التطابقات: {len(matches)}."
        ),
    }
