import React, { useEffect, useRef, useState } from "react";
import {
  LayoutDashboard,
  FileText,
  ClipboardCheck,
  Landmark,
  GitCompareArrows,
  ShieldAlert,
  Bot,
  ChartNoAxesCombined,
  FolderOpen,
  Settings,
  Search,
  Bell,
  Menu,
  Upload,
  Sparkles,
  Wallet,
  Clock3,
  FileCheck2,
  Send,
  Paperclip,
  AlertTriangle,
  RefreshCw,
  Download,
  CheckCircle2,
  Server,
  Database,
  ShieldCheck,
} from "lucide-react";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

import { api } from "./api";

const nav = [
  ["dashboard", "لوحة التحكم", LayoutDashboard],
  ["documents", "مركز المستندات", FolderOpen],
  [
    "audits",
    "\u0627\u0644\u0641\u062d\u0648\u0635\u0627\u062a \u0648\u0627\u0644\u062a\u062f\u0642\u064a\u0642 \u0627\u0644\u0630\u0643\u064a",
    ClipboardCheck,
  ],
  //["transactions", "المعاملات البنكية", Landmark],
  //["reconciliation", "التسوية البنكية", GitCompareArrows],
  ["risks", "كشف المخاطر والاحتيال", ShieldAlert],
  ["assistant", "مساعد التدقيق الذكي", Bot],
  ["reports", "التقارير والتحليلات", ChartNoAxesCombined],
  ["settings", "الإعدادات", Settings],
];

const money = (value) =>
  Number(value || 0).toLocaleString("ar-YE", {
    maximumFractionDigits: 2,
  });

const listOf = (value) => {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") return [value];
  return [];
};

function Tag({ children, t = "gray" }) {
  return <span className={`tag ${t}`}>{children}</span>;
}

function riskTag(value) {
  if (value === "مرتفع" || value === "high") return "red";
  if (value === "متوسط" || value === "medium") return "amber";
  return "green";
}

function statusTag(value) {
  if (String(value).includes("مكتملة") || String(value).includes("مطابق")) {
    return "green";
  }
  if (String(value).includes("مرفوض")) return "red";
  return "amber";
}

function Table({ rows = [], columns = [], renderActions = null }) {
  if (!rows.length) {
    return <div className="empty">لا توجد بيانات متاحة حاليًا.</div>;
  }

  return (
    <div className="tablebox">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.label}</th>
            ))}
            {renderActions && (
              <th>
                {"\u0627\u0644\u0625\u062c\u0631\u0627\u0621\u0627\u062a"}
              </th>
            )}
          </tr>
        </thead>

        <tbody>
          {rows.map((row, index) => (
            <tr key={row.id ?? index}>
              {columns.map((column) => {
                const value = row[column.key] ?? "—";

                return (
                  <td key={column.key}>
                    {column.type === "risk" ? (
                      <Tag t={riskTag(value)}>{value}</Tag>
                    ) : column.type === "status" ? (
                      <Tag t={statusTag(value)}>{value}</Tag>
                    ) : column.type === "money" ? (
                      money(value)
                    ) : (
                      value
                    )}
                  </td>
                );
              })}
              {renderActions && <td>{renderActions(row)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const invoiceColumns = [
  { key: "invoice_number", label: "رقم الفاتورة" },
  { key: "supplier", label: "المورد" },
  { key: "date", label: "التاريخ" },
  { key: "amount", label: "المبلغ (ر.ي)", type: "money" },
  { key: "status", label: "الحالة", type: "status" },
  { key: "risk_level", label: "المخاطر", type: "risk" },
];

/*const transactionColumns = [
  { key: "reference", label: "رقم المعاملة" },
  { key: "description", label: "الوصف" },
  { key: "date", label: "التاريخ" },
  { key: "amount", label: "المبلغ", type: "money" },
  { key: "direction", label: "الاتجاه" },
  { key: "status", label: "الحالة", type: "status" },
];*/

/*const reconciliationColumns = [
  { key: "transaction_reference", label: "رقم المعاملة" },
  { key: "invoice_number", label: "رقم الفاتورة" },
  { key: "status", label: "الحالة", type: "status" },
  { key: "difference", label: "الفرق", type: "money" },
];*/

const riskColumns = [
  { key: "document_name", label: "اسم المستند" },
  { key: "title", label: "الخطر" },
  { key: "category", label: "التصنيف" },
  { key: "description", label: "الوصف" },
  { key: "evidence", label: "الدليل" },
  { key: "recommendation", label: "التوصية" },
  { key: "occurrence_count", label: "عدد مرات التكرار" },
  { key: "risk_level", label: "مستوى الخطر", type: "risk" },
  { key: "score", label: "درجة الخطر" },
  { key: "potential_impact", label: "الأثر المحتمل", type: "money" },
  { key: "status", label: "الحالة", type: "status" },
];

function renderAssistantInline(value, keyPrefix) {
  const parts = String(value || "").split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${keyPrefix}-${index}`}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={`${keyPrefix}-${index}`}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={`${keyPrefix}-${index}`}>{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

function AssistantAnswer({ text }) {
  const lines = String(text || "").split(/\r?\n/);

  return (
    <div className="assistant-answer" dir="rtl">
      {lines.map((line, index) => {
        const value = line.trim();

        if (!value)
          return <div className="assistant-answer-space" key={index} />;

        if (/^[-*_]{3,}$/.test(value)) {
          return <hr className="assistant-answer-divider" key={index} />;
        }

        const heading = value.match(/^(#{1,4})\s+(.+)$/);
        if (heading) {
          const TagName = heading[1].length <= 2 ? "h4" : "h5";
          return (
            <TagName className="assistant-answer-heading" key={index}>
              {renderAssistantInline(heading[2], index)}
            </TagName>
          );
        }

        const bullet = value.match(/^[-*?]\s+(.+)$/);
        if (bullet) {
          return (
            <div className="assistant-answer-list-item" key={index}>
              <span className="assistant-answer-bullet">{"\u2022"}</span>
              <div>{renderAssistantInline(bullet[1], index)}</div>
            </div>
          );
        }

        const numbered = value.match(/^(\d+)[.)]\s+(.+)$/);
        if (numbered) {
          return (
            <div className="assistant-answer-list-item" key={index}>
              <span className="assistant-answer-number">{numbered[1]}</span>
              <div>{renderAssistantInline(numbered[2], index)}</div>
            </div>
          );
        }

        if (value.startsWith(">")) {
          return (
            <blockquote className="assistant-answer-quote" key={index}>
              {renderAssistantInline(value.slice(1).trim(), index)}
            </blockquote>
          );
        }

        return (
          <p className="assistant-answer-paragraph" key={index}>
            {renderAssistantInline(value, index)}
          </p>
        );
      })}
    </div>
  );
}

function RiskOverview({ text }) {
  const lines = String(text || "").split("\n");
  const documents = [];
  let currentDocument = null;
  let currentFinding = null;
  let readingEvidence = false;
  let disclaimer = "";

  const starts = {
    document: "\u0627\u0644\u0645\u0633\u062a\u0646\u062f: ",
    level:
      "\u0645\u0633\u062a\u0648\u0649 \u0627\u0644\u062e\u0637\u0648\u0631\u0629: ",
    score:
      "\u062f\u0631\u062c\u0629 \u0627\u0644\u062e\u0637\u0648\u0631\u0629: ",
    details: "  \u0627\u0644\u062a\u0641\u0627\u0635\u064a\u0644: ",
    recommendation: "  \u0627\u0644\u062a\u0648\u0635\u064a\u0629: ",
    evidence: "  \u0627\u0644\u062f\u0644\u064a\u0644: ",
  };

  for (const line of lines) {
    if (
      readingEvidence &&
      currentFinding &&
      line.trim() &&
      !line.startsWith(starts.details) &&
      !line.startsWith(starts.recommendation) &&
      !line.startsWith(starts.document) &&
      !line.startsWith(starts.level) &&
      !line.startsWith(starts.score) &&
      !line.trim().startsWith("- ") &&
      !line.includes("\u0644\u0627 \u062a\u062b\u0628\u062a")
    ) {
      currentFinding.evidence += "\n" + line.trim();
      continue;
    }

    if (line.startsWith(starts.document)) {
      currentDocument = {
        filename: line.slice(starts.document.length),
        level: "",
        score: "",
        findings: [],
      };
      documents.push(currentDocument);
      currentFinding = null;
    } else if (line.startsWith(starts.level) && currentDocument) {
      currentDocument.level = line.slice(starts.level.length);
    } else if (line.startsWith(starts.score) && currentDocument) {
      currentDocument.score = line.slice(starts.score.length);
    } else if (line.trim().startsWith("- ") && currentDocument) {
      const parts = line.trim().slice(2).split(" | ");
      currentFinding = {
        title: parts[0] || "",
        risk: "",
        score: "",
        count: "",
        details: "",
        recommendation: "",
        evidence: "",
      };

      parts.slice(1).forEach((part) => {
        if (part.startsWith("\u0627\u0644\u062e\u0637\u0631: ")) {
          currentFinding.risk = part.slice(
            "\u0627\u0644\u062e\u0637\u0631: ".length,
          );
        } else if (part.startsWith("\u0627\u0644\u062f\u0631\u062c\u0629: ")) {
          currentFinding.score = part.slice(
            "\u0627\u0644\u062f\u0631\u062c\u0629: ".length,
          );
        } else if (part.startsWith("\u062a\u0643\u0631\u0631\u062a: ")) {
          currentFinding.count = part.slice(
            "\u062a\u0643\u0631\u0631\u062a: ".length,
          );
        }
      });

      currentDocument.findings.push(currentFinding);
    } else if (line.startsWith(starts.details) && currentFinding) {
      currentFinding.details = line.slice(starts.details.length);
    } else if (line.startsWith(starts.recommendation) && currentFinding) {
      readingEvidence = false;
      currentFinding.recommendation = line.slice(starts.recommendation.length);
    } else if (line.startsWith(starts.evidence) && currentFinding) {
      currentFinding.evidence = line.slice(starts.evidence.length);
      readingEvidence = true;
    } else if (line.includes("\u0644\u0627 \u062a\u062b\u0628\u062a")) {
      disclaimer = line.trim();
    }
  }

  if (!documents.length) {
    return <div className="risk-overview-empty">{text}</div>;
  }

  return (
    <div className="risk-overview" dir="rtl">
      <div className="risk-overview-heading">
        <div className="risk-overview-icon">
          <ShieldAlert size={21} />
        </div>
        <div>
          <h3>
            {
              "\u0645\u0644\u062e\u0635 \u0627\u0644\u0645\u062e\u0627\u0637\u0631"
            }
          </h3>
          <p>
            {
              "\u0646\u062a\u0627\u0626\u062c \u062a\u062f\u0642\u064a\u0642 \u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a"
            }
          </p>
        </div>
        <Tag t="red">
          {documents.length} {"\u0645\u0633\u062a\u0646\u062f"}
        </Tag>
      </div>

      {documents.map((document, index) => (
        <section
          className="risk-document-card"
          key={`${document.filename}-${index}`}
        >
          <div className="risk-document-header">
            <div>
              <span className="risk-document-label">
                {"\u0627\u0644\u0645\u0633\u062a\u0646\u062f"}
              </span>
              <h4>{document.filename}</h4>
            </div>
            <Tag t={riskTag(document.level)}>{document.level}</Tag>
          </div>

          <div className="risk-score-row">
            <span>
              {
                "\u062f\u0631\u062c\u0629 \u062e\u0637\u0648\u0631\u0629 \u0627\u0644\u0645\u0633\u062a\u0646\u062f"
              }
            </span>
            <strong>{document.score || "?"} / 100</strong>
          </div>

          {document.findings.length > 0 && (
            <div className="risk-findings">
              <h5>
                {
                  "\u0627\u0644\u0645\u0644\u0627\u062d\u0638\u0627\u062a \u0627\u0644\u062a\u062f\u0642\u064a\u0642\u064a\u0629"
                }
              </h5>
              {document.findings.map((finding, findingIndex) => (
                <div className="risk-finding" key={findingIndex}>
                  <div className="risk-finding-header">
                    <strong>{finding.title}</strong>
                    <Tag t={riskTag(finding.risk)}>{finding.risk}</Tag>
                  </div>
                  <div className="risk-finding-meta">
                    {finding.score && (
                      <span>
                        {"\u0627\u0644\u062f\u0631\u062c\u0629"}:{" "}
                        {finding.score}
                      </span>
                    )}
                    {finding.count && (
                      <span>
                        {"\u062a\u0643\u0631\u0631\u062a"}: {finding.count}
                      </span>
                    )}
                  </div>
                  {finding.details && <p>{finding.details}</p>}
                  {finding.evidence && (
                    <div className="risk-evidence">
                      <strong>{"\u0627\u0644\u062f\u0644\u064a\u0644"}:</strong>
                      <pre>{finding.evidence}</pre>
                    </div>
                  )}
                  {finding.recommendation && (
                    <div className="risk-recommendation">
                      <strong>
                        {"\u0627\u0644\u062a\u0648\u0635\u064a\u0629"}:
                      </strong>{" "}
                      {finding.recommendation}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      ))}

      {disclaimer && (
        <div className="risk-disclaimer">
          <AlertTriangle size={17} />
          <p>{disclaimer}</p>
        </div>
      )}
    </div>
  );
}

function DocumentCountAnswer({ text }) {
  const values = String(text || "").match(/\d+/g) || [];
  const total = values[0] ?? "0";
  const audited = values[1] ?? "0";

  return (
    <div className="document-count-answer" dir="rtl">
      <div className="document-count-heading">
        <span className="document-count-icon">{"\u{1F4C1}"}</span>
        <div>
          <h3>
            {
              "\u0625\u062d\u0635\u0627\u0626\u064a\u0629 \u0627\u0644\u0645\u0644\u0641\u0627\u062a"
            }
          </h3>
          <p>
            {
              "\u062d\u0635\u0631 \u0645\u0646 \u0642\u0627\u0639\u062f\u0629 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a"
            }
          </p>
        </div>
      </div>
      <div className="document-count-main">
        <strong>{total}</strong>
        <span>
          {
            "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u0644\u0641\u0627\u062a"
          }
        </span>
      </div>
      <div className="document-count-audited">
        <span>
          {
            "\u0627\u0644\u0645\u0644\u0641\u0627\u062a \u0627\u0644\u0645\u062f\u0642\u0642\u0629"
          }
        </span>
        <strong>{audited}</strong>
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [toast, setToast] = useState("");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);

  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [invoiceForm, setInvoiceForm] = useState({});
  const [invoiceDetailsLoading, setInvoiceDetailsLoading] = useState(false);
  const [invoiceSaving, setInvoiceSaving] = useState(false);

  const [dashboard, setDashboard] = useState({});
  const [cashflow, setCashflow] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [auditQuery, setAuditQuery] = useState("");
  const [selectedAuditIds, setSelectedAuditIds] = useState([]);
  const [selectedAuditChecks, setSelectedAuditChecks] = useState([
    "duplicate",
    "risk",
    "tax",
    "accounting",
  ]);
  const [auditRunning, setAuditRunning] = useState(false);
  const [auditResult, setAuditResult] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [risks, setRisks] = useState([]);
  const [reconciliation, setReconciliation] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [documentAuditResult, setDocumentAuditResult] = useState(null);
  const [documentAuditLoadingId, setDocumentAuditLoadingId] = useState(null);
  const [selectedAuditDocumentId, setSelectedAuditDocumentId] = useState("");
  const [compareDocumentIds, setCompareDocumentIds] = useState(["", ""]);
  const [documentCompareResult, setDocumentCompareResult] = useState(null);
  const [documentCompareLoading, setDocumentCompareLoading] = useState(false);
  const [previewDocument, setPreviewDocument] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [reports, setReports] = useState([]);

  const [chat, setChat] = useState([
    {
      who: "ai",
      text: "مرحباً! أنا مساعد التدقيق الذكي. اسألني عن المخاطر أو الفواتير .",
    },
  ]);

  const [msg, setMsg] = useState("");
  const fileRef = useRef(null);
  const invoiceFileRef = useRef(null);

  const notify = (message) => {
    setToast(String(message || "تم تنفيذ العملية"));
    setTimeout(() => setToast(""), 4000);
  };

  const openDocumentPreview = async (doc) => {
    setPreviewDocument(doc);
    setPreviewData(null);
    setPreviewLoading(true);

    try {
      const result = await api.previewDocument(doc.id);
      setPreviewData(result);
    } catch (error) {
      notify(error.message || "تعذرت معاينة المستند.");
      setPreviewDocument(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const closeDocumentPreview = () => {
    setPreviewDocument(null);
    setPreviewData(null);
    setPreviewLoading(false);
  };

  const title = nav.find((item) => item[0] === page)?.[1] || "لوحة التحكم";

  async function loadDashboard() {
    const [summary, flow, invoiceData, documentData] = await Promise.all([
      api.getDashboard(),
      api.getCashflow(),
      api.getInvoices(),
      api.getDocuments(),
    ]);

    setDashboard(summary || {});
    setCashflow(flow?.data || []);
    setInvoices(listOf(invoiceData));
    setDocuments(listOf(documentData));
  }

  async function loadPage(target = page) {
    setLoading(true);

    try {
      switch (target) {
        case "dashboard":
          await loadDashboard();
          break;

        case "invoices":
          setInvoices(listOf(await api.getInvoices()));
          break;

        case "audits":
          setDocuments(listOf(await api.getDocuments()));
          break;

        case "transactions":
          setTransactions(listOf(await api.getTransactions()));
          break;

        case "risks":
          setRisks(listOf(await api.getRisks()));
          break;

        case "reconciliation":
          setReconciliation(listOf(await api.getReconciliationResults()));
          break;

        case "documents":
          setDocuments(listOf(await api.getDocuments()));
          break;

        case "reports":
          setReports(listOf(await api.getReports()));
          break;

        default:
          break;
      }
    } catch (error) {
      notify(error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPage(page);
  }, [page]);

  async function scanRisks() {
    setBusy(true);

    try {
      const result = await api.scanRisks();
      notify(result.message || "اكتمل فحص المخاطر");

      await loadPage("risks");
      await loadDashboard();
    } catch (error) {
      notify(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function runReconciliation() {
    setBusy(true);

    try {
      const result = await api.runReconciliation();

      notify(result?.message || result?.detail || "تم تشغيل عملية المطابقة");

      await loadPage("reconciliation");
    } catch (error) {
      notify(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function uploadDocument(file) {
    if (!file) return;

    setBusy(true);

    try {
      const result = await api.uploadDocument(file);
      notify(result.message || "تم رفع المستند بنجاح");
      await loadPage("documents");
    } catch (error) {
      notify(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function runDocumentAudit(doc) {
    if (!doc?.id || documentAuditLoadingId !== null) return;

    setDocumentAuditLoadingId(doc.id);
    setDocumentAuditResult(null);

    try {
      const result = await api.runDocumentAudit(doc.id);

      setDocumentAuditResult({
        ...result,
        filename: result.filename || doc.filename,
      });

      setDocuments(listOf(await api.getDocuments()));
      notify("اكتمل تدقيق المستند بنجاح");
    } catch (error) {
      notify(error.message || "تعذر تدقيق المستند.");
    } finally {
      setDocumentAuditLoadingId(null);
    }
  }

  async function runDocumentComparison() {
    const [firstId, secondId] = compareDocumentIds;

    if (!firstId || !secondId) {
      notify("يرجى اختيار المستندين المراد مقارنتهما.");
      return;
    }

    if (firstId === secondId) {
      notify("يجب اختيار مستندين مختلفين للمقارنة.");
      return;
    }

    if (documentCompareLoading) return;

    setDocumentCompareLoading(true);
    setDocumentCompareResult(null);

    try {
      const result = await api.compareDocuments(
        Number(firstId),
        Number(secondId),
      );

      setDocumentCompareResult(result);

      if (result.status === "incompatible") {
        notify(result.message || "نوع المستندين غير متوافق للمقارنة.");
      } else {
        notify(`اكتملت المقارنة. عدد التطابقات: ${result.match_count ?? 0}`);
      }
    } catch (error) {
      notify(error.message || "تعذرت مقارنة المستندين.");
    } finally {
      setDocumentCompareLoading(false);
    }
  }

  function downloadMatchingRecords() {
    const matches = documentCompareResult?.matches || [];

    if (matches.length === 0) {
      notify("لا توجد سجلات متطابقة لتنزيلها.");
      return;
    }

    // دمج الحقول الأصلية مع الحقول المحاسبية
    // مع منع ظهور source_fields كعمود واحد.
    const flattenRecord = (record) => {
      if (!record) return {};

      const { source_fields: sourceFields = {}, ...standardFields } = record;

      return {
        ...standardFields,
        ...(sourceFields && typeof sourceFields === "object"
          ? sourceFields
          : {}),
      };
    };

    const flattenedMatches = matches.map((match) => ({
      ...match,
      first_record: flattenRecord(match.first_record),
      second_record: flattenRecord(match.second_record),
    }));

    // جمع جميع أسماء الحقول الموجودة في السجلين.
    const recordKeys = [
      ...new Set(
        flattenedMatches.flatMap((match) => [
          ...Object.keys(match.first_record),
          ...Object.keys(match.second_record),
        ]),
      ),
    ];

    const headers = [
      "رقم التطابق",
      "نوع التطابق",
      "القيمة المتطابقة",
      "موقع المستند الأول",
      "موقع المستند الثاني",
      ...recordKeys.map((key) => `المستند الأول - ${key}`),
      ...recordKeys.map((key) => `المستند الثاني - ${key}`),
    ];

    const formatValue = (value) => {
      if (value === null || value === undefined) return "";

      if (typeof value === "object") {
        return JSON.stringify(value);
      }

      return String(value);
    };

    const escapeCsv = (value) => {
      const text = formatValue(value);
      return `"${text.replace(/"/g, '""')}"`;
    };

    const rows = flattenedMatches.map((match) => [
      match.match_id ?? "",
      match.match_type ?? "",
      match.matched_value ?? "",
      match.first_location ?? "",
      match.second_location ?? "",
      ...recordKeys.map((key) => match.first_record[key] ?? ""),
      ...recordKeys.map((key) => match.second_record[key] ?? ""),
    ]);

    const csvContent = [
      headers.map(escapeCsv).join(","),
      ...rows.map((row) => row.map(escapeCsv).join(",")),
    ].join("\r\n");

    const blob = new Blob(["\uFEFF", csvContent], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "السجلات_المتطابقة.csv";

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);

    notify(`تم تجهيز تنزيل ${matches.length} سجل متطابق.`);
  }

  async function deleteDocument(doc) {
    if (!doc?.id) {
      notify("المستند غير صالح للحذف.");
      return;
    }

    const confirmed = window.confirm(
      `هل أنت متأكدة من حذف المستند "${doc.filename}"؟\nسيتم حذف المستند وبيانات التدقيق المرتبطة به.`,
    );

    if (!confirmed) return;

    setBusy(true);

    try {
      const result = await api.deleteDocument(doc.id);
      notify(result.message || "تم حذف المستند بنجاح.");

      const [
        documentsData,
        invoiceData,
        summary,
        flow,
        transactionData,
        riskData,
        reconciliationData,
      ] = await Promise.all([
        api.getDocuments(),
        api.getInvoices(),
        api.getDashboard(),
        api.getCashflow(),
        api.getTransactions(),
        api.getRisks(),
        api.getReconciliationResults(),
      ]);

      setDocuments(listOf(documentsData));
      setInvoices(listOf(invoiceData));
      setDashboard(summary || {});
      setCashflow(flow?.data || []);
      setTransactions(listOf(transactionData));
      setRisks(listOf(riskData));
      setReconciliation(listOf(reconciliationData));
      setAuditResult(null);
      setSelectedAuditIds([]);
      setDocumentAuditResult(null);
    } catch (error) {
      notify(error.message || "تعذر حذف المستند.");
    } finally {
      setBusy(false);
    }
  }

  async function uploadInvoice(file) {
    if (!file) return;

    setBusy(true);

    try {
      const extension = file.name.split(".").pop()?.toLowerCase();

      // التحقق من أن ملف CSV يحتوي على كشف حساب بنكي.
      let isLedgerCsv = false;

      if (extension === "csv") {
        const headerText = await file.slice(0, 8192).text();
        const headerLine = headerText
          .split(/\r?\n/, 1)[0]
          .replace(/^\uFEFF/, "");

        const columns = headerLine.split(/[;,\t|]/).map((column) =>
          column
            .trim()
            .replace(/^["']|["']$/g, "")
            .toLowerCase(),
        );

        isLedgerCsv = [
          "date",
          "description",
          "debit",
          "credit",
          "reference",
        ].every((column) => columns.includes(column));
      }

      // استيراد الحركات البنكية إذا كان الملف كشف حساب.
      if (isLedgerCsv) {
        const ledgerResult = await api.uploadLedger(file);
        const transactionData = await api.getTransactions();

        setTransactions(listOf(transactionData));

        notify(
          `\u062a\u0645 \u0627\u0633\u062a\u064a\u0631\u0627\u062f ${ledgerResult.saved_count ?? 0} \u062d\u0631\u0643\u0629 \u0628\u0646\u0643\u064a\u0629. \u0627\u0644\u0645\u0643\u0631\u0631\u0629: ${ledgerResult.duplicate_count ?? 0}\u060c \u063a\u064a\u0631 \u0627\u0644\u0635\u0627\u0644\u062d\u0629: ${ledgerResult.invalid_count ?? 0}.`,
        );

        console.log("نتيجة استيراد كشف الحساب:", ledgerResult);
        return;
      }

      // رفع الفواتير باستخدام المسار المناسب لنوع الملف.
      const useBatchUpload = ["pdf", "xlsx", "xls", "csv"].includes(extension);

      const uploadResult = useBatchUpload
        ? await api.uploadInvoiceBatch(file)
        : await api.uploadInvoice(file);

      console.log("نتيجة رفع الفواتير:", uploadResult);

      const invoiceData = await api.getInvoices();
      const updatedInvoices = listOf(invoiceData);

      setInvoices(updatedInvoices);

      notify(
        "\u062a\u0645 \u0631\u0641\u0639 \u0627\u0644\u0645\u0644\u0641 \u0628\u0646\u062c\u0627\u062d. \u0631\u0627\u062c\u0639\u064a \u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u0641\u0648\u0627\u062a\u064a\u0631.",
      );
    } catch (error) {
      console.error("خطأ في رفع الفواتير:", error);
      notify(
        error.message ||
          "\u0641\u0634\u0644 \u0631\u0641\u0639 \u0627\u0644\u0645\u0644\u0641",
      );
    } finally {
      setBusy(false);
    }
  }

  async function runSelectedAudits() {
    if (auditRunning) return;

    if (selectedAuditIds.length === 0) {
      notify("يجب اختيار فاتورة واحدة على الأقل.");
      return;
    }

    if (!selectedAuditChecks.includes("duplicate")) {
      notify("يجب تفعيل فحص التكرار لتشغيل التدقيق.");
      return;
    }

    setAuditRunning(true);
    setAuditResult(null);

    try {
      const invoiceIds = selectedAuditIds
        .map(Number)
        .filter((id) =>
          auditEligibleInvoices.some((invoice) => Number(invoice.id) === id),
        );
      const result = await api.runDuplicateAudit(invoiceIds);

      setAuditResult(result);

      const extraChecks = selectedAuditChecks.some(
        (item) => item !== "duplicate",
      );

      notify(
        `اكتمل فحص التكرار. عدد الملاحظات: ${result.findings_created ?? 0}` +
          (extraChecks ? " الفحوصات الأخرى لم يتم تنفيذها بعد." : ""),
      );
    } catch (error) {
      console.error("Duplicate audit error:", error);
      notify(error.message || "تعذر تنفيذ التدقيق.");
    } finally {
      setAuditRunning(false);
    }
  }

  async function reviewInvoice(invoice, action) {
    if (busy || !invoice?.id) return;

    const actionLabel =
      action === "approve"
        ? "\u0627\u0639\u062a\u0645\u0627\u062f"
        : "\u0631\u0641\u0636";

    const confirmed = window.confirm(
      `\u0647\u0644 \u062a\u0631\u064a\u062f\u064a\u0646 ${actionLabel} \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629 \u0631\u0642\u0645 ${invoice.invoice_number}\u061f`,
    );

    if (!confirmed) return;

    setBusy(true);

    try {
      const result = await api.reviewInvoice(invoice.id, action);

      const [invoiceData, detail] = await Promise.all([
        api.getInvoices(),
        selectedInvoice?.id === invoice.id
          ? api.getInvoiceDetails(invoice.id)
          : Promise.resolve(null),
      ]);

      setInvoices(listOf(invoiceData));

      if (detail) {
        setSelectedInvoice(detail);
      }

      notify(
        result?.message ||
          `\u062a\u0645 ${actionLabel} \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629 \u0628\u0646\u062c\u0627\u062d.`,
      );
    } catch (error) {
      console.error("Invoice review error:", error);
      notify(
        error.message ||
          "\u062a\u0639\u0630\u0631\u062a \u0645\u0631\u0627\u062c\u0639\u0629 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function openInvoiceDetails(invoice) {
    setSelectedInvoice(invoice);
    setInvoiceDetailsLoading(true);
    setInvoiceForm({});

    try {
      const detail = await api.getInvoiceDetails(invoice.id);

      setSelectedInvoice(detail);
      setInvoiceForm({
        invoice_number: detail.invoice_number ?? "",
        supplier_name: detail.supplier ?? "",
        invoice_date: detail.date ?? "",
        amount: detail.amount ?? "",
        tax_amount: detail.tax_amount ?? "",
        currency: detail.currency ?? "",
        raw_text: detail.raw_text ?? "",
      });
    } catch (error) {
      notify(error.message || "تعذر فتح تفاصيل الفاتورة");
      setSelectedInvoice(null);
    } finally {
      setInvoiceDetailsLoading(false);
    }
  }

  function closeInvoiceDetails() {
    if (invoiceSaving) return;
    setSelectedInvoice(null);
    setInvoiceForm({});
  }

  async function saveInvoiceDetails() {
    if (!selectedInvoice?.id || invoiceSaving) return;

    setInvoiceSaving(true);

    try {
      await api.updateInvoice(selectedInvoice.id, {
        invoice_number: invoiceForm.invoice_number,
        supplier_name: invoiceForm.supplier_name,
        invoice_date: invoiceForm.invoice_date || null,
        amount: invoiceForm.amount,
        tax_amount:
          invoiceForm.tax_amount === "" ? null : invoiceForm.tax_amount,
        currency: invoiceForm.currency || null,
        raw_text: invoiceForm.raw_text || null,
      });

      const [detail, invoiceData] = await Promise.all([
        api.getInvoiceDetails(selectedInvoice.id),
        api.getInvoices(),
      ]);

      setSelectedInvoice(detail);
      setInvoices(listOf(invoiceData));
      setInvoiceForm({
        invoice_number: detail.invoice_number ?? "",
        supplier_name: detail.supplier ?? "",
        invoice_date: detail.date ?? "",
        amount: detail.amount ?? "",
        tax_amount: detail.tax_amount ?? "",
        currency: detail.currency ?? "",
        raw_text: detail.raw_text ?? "",
      });

      notify("تم حفظ تعديلات الفاتورة بنجاح");
    } catch (error) {
      notify(error.message || "فشل حفظ تعديلات الفاتورة");
    } finally {
      setInvoiceSaving(false);
    }
  }

  async function sendMessage(text) {
    if (!text.trim() || busy) return;

    setChat((current) => [...current, { who: "user", text }]);

    setMsg("");
    setBusy(true);

    try {
      const result = await api.chat(text);

      setChat((current) => [
        ...current,
        {
          who: "ai",
          mode: result.mode || "default",
          text:
            result.reply ||
            result.answer ||
            result.message ||
            "وصلت الإجابة من الخادم، لكن لم يتم العثور على حقل النص.",
        },
      ]);
    } catch (error) {
      setChat((current) => [...current, { who: "ai", text: error.message }]);
    } finally {
      setBusy(false);
    }
  }

  async function generateReport(type = "audit_summary") {
    setBusy(true);

    try {
      const result = await api.generateReport(type, "pdf");

      notify(result.message || "تم إنشاء التقرير");

      await loadPage("reports");
    } catch (error) {
      notify(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function downloadReport(reportId) {
    try {
      const blob = await api.downloadReport(reportId);
      const url = URL.createObjectURL(blob);

      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `audit-report-${reportId}.pdf`;
      anchor.click();

      URL.revokeObjectURL(url);
    } catch (error) {
      notify(error.message);
    }
  }

  async function deleteReport(reportId) {
    if (!reportId) {
      notify(
        "\u0631\u0642\u0645 \u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u063a\u064a\u0631 \u0635\u0627\u0644\u062d.",
      );
      return;
    }

    const confirmed = window.confirm(
      `\u0647\u0644 \u062a\u0631\u064a\u062f \u062d\u0630\u0641 \u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u0631\u0642\u0645 ${reportId}؟\n\u0633\u064a\u062a\u0645 \u062d\u0630\u0641 \u0633\u062c\u0644 \u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u0648\u0645\u0644\u0641 PDF \u0627\u0644\u0645\u0631\u062a\u0628\u0637 \u0628\u0647.`,
    );

    if (!confirmed) return;

    setBusy(true);

    try {
      const result = await api.deleteReport(reportId);
      notify(
        result.message ||
          "\u062a\u0645 \u062d\u0630\u0641 \u0627\u0644\u062a\u0642\u0631\u064a\u0631 \u0628\u0646\u062c\u0627\u062d.",
      );
      await loadPage("reports");
    } catch (error) {
      notify(
        error.message ||
          "\u062a\u0639\u0630\u0631 \u062d\u0630\u0641 \u0627\u0644\u062a\u0642\u0631\u064a\u0631.",
      );
    } finally {
      setBusy(false);
    }
  }

  const filteredInvoices = invoices.filter((invoice) =>
    Object.values(invoice)
      .join(" ")
      .toLowerCase()
      .includes(query.toLowerCase()),
  );

  const auditEligibleInvoices = invoices.filter((invoice) => {
    const status = String(invoice.status ?? "")
      .trim()
      .toLowerCase();

    return !["مكتملة", "مرفوضة", "مرفوض", "rejected"].includes(status);
  });

  const auditFilteredInvoices = auditEligibleInvoices.filter((invoice) => {
    const search = auditQuery.trim().toLowerCase();

    return (
      !search ||
      [
        invoice.invoice_number,
        invoice.supplier,
        invoice.supplier_name,
        invoice.status,
        invoice.id,
      ].some((value) =>
        String(value ?? "")
          .toLowerCase()
          .includes(search),
      )
    );
  });

  const riskCounts = risks.reduce(
    (counts, risk) => {
      const level = risk.risk_level;

      if (level === "مرتفع" || level === "high") counts.high++;
      else if (level === "متوسط" || level === "medium") counts.medium++;
      else counts.low++;

      return counts;
    },
    { high: 0, medium: 0, low: 0 },
  );

  const pieData = [
    { name: "منخفض", value: riskCounts.low },
    { name: "متوسط", value: riskCounts.medium },
    { name: "مرتفع", value: riskCounts.high },
  ];

  const pieColors = ["#16b887", "#f4b740", "#ef6472"];

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">✦</div>
          <div>
            <b>
              AUDIT <i>AI</i>
            </b>
            <small>التدقيق المالي الذكي</small>
          </div>
        </div>

        <div className="company">
          <b>شركة النخبة القابضة</b>
          <small>مساحة العمل الرئيسية</small>
        </div>

        <small className="navcap">القائمة الرئيسية</small>

        {nav.map(([id, label, Icon]) => (
          <button
            key={id}
            onClick={() => setPage(id)}
            className={`nav ${page === id ? "selected" : ""}`}
          >
            <Icon size={18} />
            {label}
            {id === "risks" && risks.length > 0 && <em>{risks.length}</em>}
          </button>
        ))}

        <div className="sidefoot">
          <b>مركز الذكاء الاصطناعي</b>
          <p>راقب المخاطر وحسّن جودة التدقيق.</p>
          <span>نسخة متصلة بالـBackend</span>
        </div>
      </aside>

      <main>
        <header>
          <button
            className="mobile"
            onClick={() =>
              document.querySelector(".sidebar")?.classList.toggle("show")
            }
          >
            <Menu />
          </button>

          <div className="crumb">
            مساحة العمل　/　<b>{title}</b>
          </div>

          <div className="headright">
            <div className="search">
              <Search size={16} />
              <input
                placeholder="ابحث عن فاتورة أو مورد..."
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>

            <Bell />

            <div className="user">
              <b>م</b>
              <span>
                مدير التدقيق
                <small>مسؤول النظام</small>
              </span>
            </div>
          </div>
        </header>

        <section className="content">
          {loading && (
            <div className="loading">جارٍ تحميل البيانات من الخادم...</div>
          )}

          {page === "dashboard" && (
            <>
              {(() => {
                const totalDocuments = documents.length;

                const auditedDocuments = documents.filter(
                  (doc) => doc.status === "تم التدقيق",
                ).length;

                const pendingDocuments = totalDocuments - auditedDocuments;

                const recentDocuments = documents.slice(0, 5);

                const formatFileSize = (bytes) => {
                  if (!bytes) return "0 بايت";

                  if (bytes < 1024) {
                    return `${bytes} بايت`;
                  }

                  if (bytes < 1024 * 1024) {
                    return `${(bytes / 1024).toFixed(1)} كيلوبايت`;
                  }

                  return `${(bytes / (1024 * 1024)).toFixed(1)} ميجابايت`;
                };

                const formatDate = (value) => {
                  if (!value) return "—";

                  const date = new Date(value);

                  if (Number.isNaN(date.getTime())) {
                    return "—";
                  }

                  return date.toLocaleDateString("ar-YE-u-nu-latn", {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  });
                };

                return (
                  <div className="dashboard-page">
                    <div className="heading">
                      <div>
                        <small>لوحة إدارة المستندات</small>
                        <h1>مرحباً بك في لوحة التدقيق الذكي</h1>
                        <p>
                          متابعة المستندات المرفوعة وحالة التدقيق وآخر الملفات
                          المسجلة في النظام.
                        </p>
                      </div>

                      <button
                        className="primary"
                        onClick={() => setPage("documents")}
                      >
                        <FolderOpen size={16} />
                        مركز المستندات
                      </button>
                    </div>

                    <div className="stats">
                      {[
                        {
                          Icon: FileText,
                          label: "إجمالي المستندات",
                          value: totalDocuments,
                          color: "blue",
                        },
                        {
                          Icon: ClipboardCheck,
                          label: "المستندات المدققة",
                          value: auditedDocuments,
                          color: "purple",
                        },
                        {
                          Icon: Clock3,
                          label: "بانتظار التدقيق",
                          value: pendingDocuments,
                          color: "orange",
                        },
                      ].map(({ Icon, label, value, color }) => (
                        <div className="stat" key={label}>
                          <div>
                            <small>{label}</small>
                            <i className={color}>
                              <Icon size={19} />
                            </i>
                          </div>

                          <b>{value.toLocaleString("en-US")}</b>
                        </div>
                      ))}
                    </div>

                    <div className="panel">
                      <div className="panelhead">
                        <div>
                          <b>أحدث المستندات</b>
                          <small>آخر المستندات التي تم رفعها إلى النظام</small>
                        </div>

                        <button
                          className="secondary"
                          onClick={() => setPage("documents")}
                        >
                          عرض جميع المستندات
                        </button>
                      </div>

                      {recentDocuments.length === 0 ? (
                        <div className="empty-state">
                          <FileText size={36} />

                          <b>لا توجد مستندات حتى الآن</b>

                          <p>
                            ابدئي برفع المستندات من مركز المستندات لتظهر هنا.
                          </p>

                          <button
                            className="primary"
                            onClick={() => setPage("documents")}
                          >
                            الانتقال إلى مركز المستندات
                          </button>
                        </div>
                      ) : (
                        <div className="tablewrap">
                          <table>
                            <thead>
                              <tr>
                                <th>اسم المستند</th>
                                <th>حجم الملف</th>
                                <th>تاريخ الإضافة</th>
                                <th>الحالة</th>
                              </tr>
                            </thead>

                            <tbody>
                              {recentDocuments.map((doc) => (
                                <tr key={doc.id}>
                                  <td>
                                    <div className="document-name-cell">
                                      <FileText size={17} />
                                      <span>{doc.filename}</span>
                                    </div>
                                  </td>

                                  <td>{formatFileSize(doc.size_bytes)}</td>

                                  <td>{formatDate(doc.created_at)}</td>

                                  <td>
                                    <span
                                      className={`status ${
                                        doc.status === "تم التدقيق"
                                          ? "success"
                                          : "pending"
                                      }`}
                                    >
                                      {doc.status || "تم الرفع"}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>

                    <div className="panel">
                      <div className="panelhead">
                        <div>
                          <b>الفحوصات والتدقيق الذكي</b>
                          <small>
                            الوصول إلى أدوات تدقيق المستندات ومقارنتها
                          </small>
                        </div>

                        <button
                          className="primary"
                          onClick={() => setPage("audits")}
                        >
                          <Sparkles size={16} />
                          فتح صفحة التدقيق
                        </button>
                      </div>

                      <p>
                        يمكنك اختيار مستند محفوظ، وفحص محتواه، أو مقارنته بمستند
                        آخر لاكتشاف السجلات المتطابقة والبيانات المتشابهة.
                      </p>
                    </div>
                  </div>
                );
              })()}
            </>
          )}

          {page === "audits" && (
            <>
              <div className="heading">
                <div>
                  <h1>الفحوصات والتدقيق الذكي</h1>
                  <p>
                    افحص محتوى المستندات بالكامل أو قارن بين مستندين لاكتشاف
                    السجلات المتطابقة.
                  </p>
                </div>
              </div>

              <div className="stats audit-stats">
                <div className="stat">
                  <div>
                    <small>إجمالي المستندات</small>
                    <i className="blue">
                      <FileText size={17} />
                    </i>
                  </div>
                  <b>{documents.length}</b>
                  <span>مستند محفوظ</span>
                </div>

                <div className="stat">
                  <div>
                    <small>نتائج التدقيق</small>
                    <i className="purple">
                      <ClipboardCheck size={17} />
                    </i>
                  </div>
                  <b>
                    {documentAuditResult
                      ? (documentAuditResult.finding_count ?? 0)
                      : 0}
                  </b>
                  <span>ملاحظة مكتشفة</span>
                </div>

                <div className="stat">
                  <div>
                    <small>نتائج المقارنة</small>
                    <i className="orange">
                      <ShieldAlert size={17} />
                    </i>
                  </div>
                  <b>{documentCompareResult?.match_count ?? 0}</b>
                  <span>سجل متطابق</span>
                </div>
              </div>

              <div className="panel audit-page audit-single">
                <div className="panelhead">
                  <div>
                    <b>أولاً: تدقيق مستند واحد</b>
                    <small>
                      فحص محتوى المستند بالكامل واكتشاف الأخطاء والتكرارات
                      داخله.
                    </small>
                  </div>
                </div>

                <div className="toolbar">
                  <select
                    value={selectedAuditDocumentId}
                    onChange={(event) => {
                      setSelectedAuditDocumentId(event.target.value);
                      setDocumentAuditResult(null);
                    }}
                  >
                    <option value="">اختر المستند المراد تدقيقه</option>
                    {documents.map((doc) => (
                      <option key={doc.id} value={String(doc.id)}>
                        {doc.filename}
                      </option>
                    ))}
                  </select>

                  <button
                    type="button"
                    className="primary"
                    disabled={
                      !selectedAuditDocumentId ||
                      documentAuditLoadingId !== null
                    }
                    onClick={() => {
                      const doc = documents.find(
                        (item) => String(item.id) === selectedAuditDocumentId,
                      );
                      if (doc) runDocumentAudit(doc);
                    }}
                  >
                    <ClipboardCheck size={16} />
                    {documentAuditLoadingId !== null
                      ? "جاري تدقيق المستند..."
                      : "بدء التدقيق"}
                  </button>
                </div>

                {documents.length === 0 && (
                  <p className="audit-empty">
                    لا توجد مستندات. ارفعي المستندات أولاً من مركز المستندات.
                  </p>
                )}
              </div>

              <div className="panel audit-page audit-compare">
                <div className="panelhead">
                  <div>
                    <b>ثانياً: مقارنة مستندين</b>
                    <small>
                      اكتشاف السجلات المتطابقة بين محتوى المستند الأول والثاني.
                    </small>
                  </div>
                </div>

                <div className="toolbar">
                  <select
                    value={compareDocumentIds[0]}
                    onChange={(event) => {
                      setCompareDocumentIds((current) => [
                        event.target.value,
                        current[1],
                      ]);
                      setDocumentCompareResult(null);
                    }}
                  >
                    <option value="">اختر المستند الأول</option>
                    {documents.map((doc) => (
                      <option key={doc.id} value={String(doc.id)}>
                        {doc.filename}
                      </option>
                    ))}
                  </select>

                  <select
                    value={compareDocumentIds[1]}
                    onChange={(event) => {
                      setCompareDocumentIds((current) => [
                        current[0],
                        event.target.value,
                      ]);
                      setDocumentCompareResult(null);
                    }}
                  >
                    <option value="">اختر المستند الثاني</option>
                    {documents.map((doc) => (
                      <option key={doc.id} value={String(doc.id)}>
                        {doc.filename}
                      </option>
                    ))}
                  </select>

                  <button
                    type="button"
                    className="primary"
                    onClick={runDocumentComparison}
                    disabled={
                      documentCompareLoading ||
                      !compareDocumentIds[0] ||
                      !compareDocumentIds[1] ||
                      compareDocumentIds[0] === compareDocumentIds[1]
                    }
                  >
                    <ClipboardCheck size={16} />
                    {documentCompareLoading
                      ? "جاري المقارنة..."
                      : "مقارنة المستندين"}
                  </button>
                </div>

                {documentCompareResult?.status === "incompatible" && (
                  <p className="audit-empty">{documentCompareResult.message}</p>
                )}

                {documentCompareResult?.status === "completed" && (
                  <div className="document-audit-result">
                    <div className="comparison-result-header">
                      <div>
                        <h3>نتيجة مقارنة المستندين</h3>
                        <p>{documentCompareResult.summary}</p>
                      </div>

                      <button
                        type="button"
                        className="comparison-download-btn"
                        onClick={downloadMatchingRecords}
                        disabled={!documentCompareResult.matches?.length}
                      >
                        <FileText size={16} />
                        تنزيل السجلات المتطابقة
                      </button>
                    </div>

                    <div className="document-audit-summary">
                      <span>
                        <strong>سجلات المستند الأول:</strong>{" "}
                        {documentCompareResult.first_record_count}
                      </span>
                      <span>
                        <strong>سجلات المستند الثاني:</strong>{" "}
                        {documentCompareResult.second_record_count}
                      </span>
                      <span>
                        <strong>عدد التطابقات:</strong>{" "}
                        {documentCompareResult.match_count}
                      </span>
                    </div>

                    {documentCompareResult.matches?.length > 0 ? (
                      <div className="document-audit-findings">
                        {documentCompareResult.matches.map((match) => (
                          <article
                            className="document-audit-finding"
                            key={match.match_id}
                          >
                            <h3>التطابق رقم {match.match_id}</h3>
                            <p>
                              <strong>نوع التطابق:</strong> {match.match_type}
                            </p>
                            <p>
                              <strong>القيمة المتطابقة:</strong>{" "}
                              {typeof match.matched_value === "object"
                                ? JSON.stringify(match.matched_value, null, 2)
                                : String(match.matched_value ?? "-")}
                            </p>
                            <p>
                              <strong>موقع المستند الأول:</strong>{" "}
                              {JSON.stringify(match.first_location ?? "-")}
                            </p>
                            <p>
                              <strong>موقع المستند الثاني:</strong>{" "}
                              {JSON.stringify(match.second_location ?? "-")}
                            </p>

                            <details className="comparison-record-details">
                              <summary>عرض تفاصيل السجلين المتطابقين</summary>

                              <div className="comparison-record-table-wrap">
                                <table className="comparison-record-table">
                                  <thead>
                                    <tr>
                                      <th>الحقل</th>
                                      <th>السجل الأول</th>
                                      <th>السجل الثاني</th>
                                    </tr>
                                  </thead>

                                  <tbody>
                                    {(() => {
                                      const flattenRecord = (record) => {
                                        if (!record) return {};

                                        const {
                                          source_fields: sourceFields = {},
                                          ...standardFields
                                        } = record;

                                        return {
                                          ...standardFields,
                                          ...(sourceFields &&
                                          typeof sourceFields === "object"
                                            ? sourceFields
                                            : {}),
                                        };
                                      };

                                      const firstRecord = flattenRecord(
                                        match.first_record,
                                      );
                                      const secondRecord = flattenRecord(
                                        match.second_record,
                                      );

                                      const recordKeys = [
                                        ...new Set([
                                          ...Object.keys(firstRecord),
                                          ...Object.keys(secondRecord),
                                        ]),
                                      ];

                                      const formatValue = (value) => {
                                        if (
                                          value === null ||
                                          value === undefined ||
                                          value === ""
                                        ) {
                                          return "—";
                                        }

                                        if (typeof value === "object") {
                                          return JSON.stringify(value);
                                        }

                                        return String(value);
                                      };

                                      return recordKeys.map((key) => (
                                        <tr key={key}>
                                          <td>{key}</td>
                                          <td>
                                            {formatValue(firstRecord[key])}
                                          </td>
                                          <td>
                                            {formatValue(secondRecord[key])}
                                          </td>
                                        </tr>
                                      ));
                                    })()}
                                  </tbody>
                                </table>
                              </div>
                            </details>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p>لم يتم العثور على سجلات متطابقة بين المستندين.</p>
                    )}
                  </div>
                )}
              </div>

              {documentAuditResult && (
                <section className="panel document-audit-result">
                  <div className="heading">
                    <div>
                      <h2>نتيجة تدقيق المستند</h2>
                      <p>{documentAuditResult.filename}</p>
                    </div>

                    <button
                      type="button"
                      className="details-button"
                      onClick={() => setDocumentAuditResult(null)}
                    >
                      إغلاق
                    </button>
                  </div>

                  <p>{documentAuditResult.summary}</p>

                  <div className="document-audit-summary">
                    <span>
                      <strong>مستوى الخطورة:</strong>{" "}
                      {documentAuditResult.risk_level || "غير محدد"}
                    </span>
                    <span>
                      <strong>درجة الخطورة:</strong>{" "}
                      {documentAuditResult.risk_score ?? 0}/100
                    </span>
                    <span>
                      <strong>عدد الملاحظات:</strong>{" "}
                      {documentAuditResult.finding_count ?? 0}
                    </span>
                    <span>
                      <strong>الأحرف المستخرجة:</strong>{" "}
                      {documentAuditResult.extracted_chars ?? 0}
                    </span>
                  </div>

                  {documentAuditResult.findings?.length > 0 ? (
                    <div className="document-audit-findings">
                      {documentAuditResult.findings.map((finding, index) => (
                        <article
                          className="document-audit-finding"
                          key={finding.id || index}
                        >
                          <h3>
                            {index + 1}. {finding.title}
                          </h3>
                          <p>{finding.description}</p>

                          {finding.evidence && (
                            <p>
                              <strong>الدليل:</strong> {finding.evidence}
                            </p>
                          )}

                          {finding.recommendation && (
                            <p>
                              <strong>التوصية:</strong> {finding.recommendation}
                            </p>
                          )}

                          <small>
                            <strong>مستوى الخطورة:</strong>{" "}
                            {finding.risk_level || "غير محدد"}
                            {" | "}
                            <strong>عدد مرات التكرار:</strong>{" "}
                            {finding.occurrence_count ?? 0}
                          </small>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p>لم تظهر مؤشرات مراجعة في هذا الفحص.</p>
                  )}

                  <small className="document-audit-disclaimer">
                    نتائج آلية أولية للمراجعة، وليست حكمًا نهائيًا بوجود مخالفة.
                  </small>
                </section>
              )}
            </>
          )}

          {page === "transactions" && (
            <>
              <div className="heading">
                <div>
                  <h1>المعاملات البنكية</h1>
                  <p>مراجعة الحركات البنكية المسجلة في النظام.</p>
                </div>
              </div>

              <div className="panel">
                <Table rows={transactions} columns={transactionColumns} />
              </div>
            </>
          )}

          {page === "reconciliation" && (
            <>
              <div className="heading">
                <div>
                  <h1>التسوية البنكية</h1>
                  <p>قارن كشف البنك بالقيود المحاسبية وحدد الفروقات.</p>
                </div>

                <button
                  className="primary"
                  onClick={runReconciliation}
                  disabled={busy}
                >
                  <RefreshCw size={16} />
                  {busy ? "جارٍ التنفيذ..." : "بدء المطابقة"}
                </button>
              </div>

              <div className="stats">
                <div className="stat">
                  <small>إجمالي نتائج المطابقة</small>
                  <b>{reconciliation.length}</b>
                </div>

                <div className="stat">
                  <small>مطابق</small>
                  <b>
                    {
                      reconciliation.filter((item) =>
                        String(item.status).includes("مطابق"),
                      ).length
                    }
                  </b>
                </div>

                <div className="stat">
                  <small>غير مطابق</small>
                  <b>
                    {
                      reconciliation.filter((item) =>
                        String(item.status).includes("غير"),
                      ).length
                    }
                  </b>
                </div>
              </div>

              <div className="panel">
                <Table rows={reconciliation} columns={reconciliationColumns} />
              </div>
            </>
          )}

          {page === "risks" && (
            <>
              <div className="heading">
                <div>
                  <h1>كشف المخاطر والاحتيال</h1>
                  <p>نتائج فحص المخاطر الفعلية من النظام.</p>
                </div>

                <button className="primary" onClick={scanRisks} disabled={busy}>
                  <Sparkles size={16} />
                  {busy ? "جارٍ الفحص..." : "فحص جديد"}
                </button>
              </div>

              <div className="panel">
                <Table rows={risks} columns={riskColumns} />
              </div>
            </>
          )}

          {page === "assistant" && (
            <>
              <div className="heading">
                <div>
                  <h1>مساعد التدقيق الذكي</h1>
                  <p>اسأل عن البيانات المالية أو مؤشرات التدقيق.</p>
                </div>

                <Tag t="purple">Ollama AI</Tag>
              </div>

              <div className="panel chat">
                <div className="chatmsgs">
                  {chat.map((message, index) => (
                    <div
                      className={`bubble ${message.who} ${message.mode === "database_risk_overview" ? "risk-bubble" : ""} ${message.mode === "database_count" ? "count-bubble" : ""}`}
                      key={index}
                    >
                      {message.mode === "database_risk_overview" ? (
                        <RiskOverview text={message.text} />
                      ) : message.mode === "database_count" ? (
                        <DocumentCountAnswer text={message.text} />
                      ) : message.who === "ai" ? (
                        <AssistantAnswer text={message.text} />
                      ) : (
                        message.text
                      )}
                    </div>
                  ))}

                  {busy && <div className="bubble">جارٍ التفكير...</div>}
                </div>

                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    sendMessage(msg);
                  }}
                >
                  <Paperclip />

                  <input
                    value={msg}
                    onChange={(event) => setMsg(event.target.value)}
                    placeholder="اكتب سؤالك هنا..."
                  />

                  <button type="submit" disabled={busy}>
                    <Send />
                  </button>
                </form>

                <div className="quick">
                  {[
                    "ما أبرز المخاطر الحالية؟",
                    "اشرح التسوية البنكية",
                    "كيف أراجع فاتورة مشبوهة؟",
                  ].map((question) => (
                    <button
                      key={question}
                      onClick={() => sendMessage(question)}
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {page === "reports" && (
            <div className="reports-page">
              <div className="heading reports-heading">
                <div>
                  <h1>
                    {
                      "\u0627\u0644\u062a\u0642\u0627\u0631\u064a\u0631 \u0648\u0627\u0644\u062a\u062d\u0644\u064a\u0644\u0627\u062a"
                    }
                  </h1>
                  <p>
                    {
                      "\u0625\u0646\u0634\u0627\u0621 \u0627\u0644\u062a\u0642\u0627\u0631\u064a\u0631 \u0627\u0644\u0645\u0627\u0644\u064a\u0629 \u0645\u0646 \u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0646\u0638\u0627\u0645."
                    }
                  </p>
                </div>

                <button
                  className="primary"
                  onClick={() => generateReport("audit_summary")}
                  disabled={busy}
                >
                  <Download size={16} />
                  {
                    "\u0625\u0646\u0634\u0627\u0621 \u062a\u0642\u0631\u064a\u0631"
                  }
                </button>
              </div>

              <div className="panel reports-panel">
                {reports.length === 0 ? (
                  <p className="reports-empty">
                    {
                      "\u0644\u0627 \u062a\u0648\u062c\u062f \u062a\u0642\u0627\u0631\u064a\u0631 \u0645\u062d\u0641\u0648\u0638\u0629 \u062d\u062a\u0649 \u0627\u0644\u0622\u0646."
                    }
                  </p>
                ) : (
                  <div className="reports-list">
                    {reports.map((report) => (
                      <div key={report.id} className="report-card">
                        <div className="report-info">
                          <strong>
                            {report.title ||
                              `\u0627\u0644\u062a\u0642\u0631\u064a\u0631 ${report.id}`}
                          </strong>
                          <div>
                            {
                              "\u0631\u0642\u0645 \u0627\u0644\u062a\u0642\u0631\u064a\u0631"
                            }
                            : {report.id} |{" "}
                            {"\u0627\u0644\u0635\u064a\u063a\u0629"}:{" "}
                            {report.format || "PDF"}
                          </div>
                          <div>
                            {"\u0627\u0644\u062d\u0627\u0644\u0629"}:{" "}
                            {report.status || "\u0645\u062c\u0647\u0648\u0644"}{" "}
                            |{" "}
                            {
                              "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0625\u0646\u0634\u0627\u0621"
                            }
                            : {report.created_at}
                          </div>
                        </div>

                        <div className="report-actions">
                          <button
                            className="report-action report-download-btn"
                            onClick={() => downloadReport(report.id)}
                            disabled={busy}
                          >
                            <Download size={14} />{" "}
                            {"\u062a\u0646\u0632\u064a\u0644"}{" "}
                          </button>

                          <button
                            className="report-action report-delete-btn"
                            onClick={() => deleteReport(report.id)}
                            disabled={busy}
                          >
                            {"\u062d\u0630\u0641"}{" "}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {page === "documents" && (
            <>
              <div className="heading documents-heading">
                <div>
                  <h1>مركز المستندات</h1>
                  <p>المستندات المحفوظة في قاعدة البيانات.</p>
                </div>

                <button
                  className="primary documents-upload-btn"
                  onClick={() => fileRef.current?.click()}
                >
                  <Upload size={16} /> إضافة مستند
                </button>

                <input
                  ref={fileRef}
                  hidden
                  type="file"
                  onChange={(event) => uploadDocument(event.target.files?.[0])}
                />
              </div>

              <div className="panel documents-panel">
                <Table
                  rows={documents}
                  columns={[
                    {
                      key: "filename",
                      label:
                        "\u0627\u0633\u0645 \u0627\u0644\u0645\u0644\u0641",
                    },
                  ]}
                  renderActions={(doc) => {
                    const extension = String(doc.filename || "")
                      .split(".")
                      .pop()
                      .toLowerCase();

                    const canPreview = ["pdf", "png", "jpg", "jpeg"].includes(
                      extension,
                    );
                    const canTabularPreview = ["xlsx", "xls", "csv"].includes(
                      extension,
                    );

                    return (
                      <div className="invoice-actions documents-actions">
                        {canPreview && (
                          <a
                            className="details-button document-action document-view-action"
                            href={api.getDocumentFileUrl(doc.id)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {"\u0639\u0631\u0636"}
                          </a>
                        )}
                        {canTabularPreview && (
                          <button
                            type="button"
                            className="details-button document-action document-preview-action"
                            onClick={() => openDocumentPreview(doc)}
                          >
                            {"\u0645\u0639\u0627\u064a\u0646\u0629"}
                          </button>
                        )}
                        <a
                          className="details-button document-action document-download-action"
                          href={api.getDocumentDownloadUrl(doc.id)}
                        >
                          {"\u062a\u0646\u0632\u064a\u0644"}
                        </a>
                        <button
                          type="button"
                          className="details-button document-action document-delete-action"
                          onClick={() => deleteDocument(doc)}
                          disabled={busy}
                        >
                          {"\u062d\u0630\u0641"}
                        </button>
                      </div>
                    );
                  }}
                />
              </div>

              {documentAuditResult && (
                <section className="panel document-audit-result">
                  <div className="heading">
                    <div>
                      <h2>نتيجة تدقيق المستند</h2>
                      <p>{documentAuditResult.filename}</p>
                    </div>

                    <button
                      type="button"
                      className="details-button"
                      onClick={() => setDocumentAuditResult(null)}
                    >
                      إغلاق
                    </button>
                  </div>

                  <p>{documentAuditResult.summary}</p>

                  <div className="document-audit-summary">
                    <span>
                      <strong>مستوى الخطورة:</strong>{" "}
                      {documentAuditResult.risk_level || "غير محدد"}
                    </span>

                    <span>
                      <strong>درجة الخطورة:</strong>{" "}
                      {documentAuditResult.risk_score ?? 0}/100
                    </span>

                    <span>
                      <strong>عدد الملاحظات:</strong>{" "}
                      {documentAuditResult.finding_count ?? 0}
                    </span>

                    <span>
                      <strong>الأحرف المستخرجة:</strong>{" "}
                      {documentAuditResult.extracted_chars ?? 0}
                    </span>
                  </div>

                  {documentAuditResult.findings?.length > 0 ? (
                    <div className="document-audit-findings">
                      {documentAuditResult.findings.map((finding, index) => (
                        <article
                          className="document-audit-finding"
                          key={finding.id || index}
                        >
                          <h3>
                            {index + 1}. {finding.title}
                          </h3>

                          <p>{finding.description}</p>

                          {finding.evidence && (
                            <p>
                              <strong>الدليل:</strong> {finding.evidence}
                            </p>
                          )}

                          {finding.recommendation && (
                            <p>
                              <strong>التوصية:</strong> {finding.recommendation}
                            </p>
                          )}

                          <small>
                            <strong>مستوى الخطورة:</strong>{" "}
                            {finding.risk_level || "غير محدد"}
                            {" | "}
                            <strong>عدد مرات التكرار:</strong>{" "}
                            {finding.occurrence_count ?? 0}
                          </small>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p>لم تظهر مؤشرات مراجعة في هذا الفحص.</p>
                  )}

                  <small className="document-audit-disclaimer">
                    نتائج آلية أولية للمراجعة، وليست حكمًا نهائيًا بوجود مخالفة.
                  </small>
                </section>
              )}
            </>
          )}

          {page === "settings" && (
            <div className="settings-page">
              <div className="heading settings-heading">
                <div>
                  <h1>
                    {"\u0627\u0644\u0625\u0639\u062f\u0627\u062f\u0627\u062a"}
                  </h1>
                  <p>
                    {
                      "\u0625\u062f\u0627\u0631\u0629 \u0625\u0639\u062f\u0627\u062f\u0627\u062a \u0627\u0644\u0645\u0646\u0635\u0629 \u0648\u0645\u0639\u0644\u0648\u0645\u0627\u062a \u0627\u0644\u062e\u062f\u0645\u0627\u062a \u0627\u0644\u0645\u0631\u062a\u0628\u0637\u0629."
                    }
                  </p>
                </div>
                <div className="settings-heading-icon">
                  <Settings size={22} />
                </div>
              </div>

              <div className="settings-overview">
                <div className="settings-overview-card">
                  <span className="settings-overview-icon settings-blue">
                    <Server size={19} />
                  </span>
                  <div>
                    <small>
                      {
                        "\u062e\u062f\u0645\u0629 \u0627\u0644\u062e\u0627\u062f\u0645"
                      }
                    </small>
                    <strong>Python + FastAPI</strong>
                    <span>
                      {
                        "\u0627\u0644\u062e\u0644\u0641\u064a\u0629 \u0627\u0644\u0628\u0631\u0645\u062c\u064a\u0629"
                      }
                    </span>
                  </div>
                </div>

                <div className="settings-overview-card">
                  <span className="settings-overview-icon settings-purple">
                    <Database size={19} />
                  </span>
                  <div>
                    <small>
                      {
                        "\u0642\u0627\u0639\u062f\u0629 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a"
                      }
                    </small>
                    <strong>PostgreSQL</strong>
                    <span>
                      {
                        "\u062a\u062e\u0632\u064a\u0646 \u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0646\u0638\u0627\u0645"
                      }
                    </span>
                  </div>
                </div>

                <div className="settings-overview-card">
                  <span className="settings-overview-icon settings-green">
                    <ShieldCheck size={19} />
                  </span>
                  <div>
                    <small>
                      {
                        "\u0646\u0645\u0637 \u0627\u0644\u0627\u062a\u0635\u0627\u0644"
                      }
                    </small>
                    <strong>API</strong>
                    <span>
                      {
                        "\u0627\u0644\u0648\u0635\u0648\u0644 \u0639\u0628\u0631 \u0627\u0644\u0648\u0627\u062c\u0647\u0629 \u0627\u0644\u0628\u0631\u0645\u062c\u064a\u0629"
                      }
                    </span>
                  </div>
                </div>
              </div>

              <div className="settings-section-title">
                <div>
                  <h2>
                    {
                      "\u0628\u064a\u0626\u0629 \u0627\u0644\u062a\u0634\u063a\u064a\u0644"
                    }
                  </h2>
                  <p>
                    {
                      "\u0645\u0639\u0644\u0648\u0645\u0627\u062a \u0627\u0644\u062e\u062f\u0645\u0627\u062a \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u0629 \u0641\u064a \u0627\u0644\u0645\u0646\u0635\u0629."
                    }
                  </p>
                </div>
              </div>

              <div className="settings-details-grid">
                <section className="panel settings-detail-card">
                  <div className="settings-card-heading">
                    <span className="settings-card-icon settings-blue">
                      <Server size={20} />
                    </span>
                    <div>
                      <h3>
                        {
                          "\u0627\u0644\u0627\u062a\u0635\u0627\u0644 \u0628\u0627\u0644\u062e\u0627\u062f\u0645"
                        }
                      </h3>
                      <p>
                        {
                          "\u0625\u0639\u062f\u0627\u062f\u0627\u062a \u0627\u0644\u0648\u0627\u062c\u0647\u0629 \u0627\u0644\u062e\u0644\u0641\u064a\u0629"
                        }
                      </p>
                    </div>
                  </div>

                  <div className="settings-detail-row">
                    <span>{"\u0627\u0644\u0645\u0646\u0635\u0629"}</span>
                    <strong>Python + FastAPI</strong>
                  </div>

                  <div className="settings-detail-row settings-api-row">
                    <span>{"\u0639\u0646\u0648\u0627\u0646 API"}</span>
                    <code>
                      {import.meta.env.VITE_API_BASE_URL || "??? ????"}
                    </code>
                  </div>

                  <div className="settings-card-footer">
                    <Tag t="green">
                      {
                        "\u0627\u0644\u0627\u062a\u0635\u0627\u0644 \u0639\u0628\u0631 API"
                      }
                    </Tag>
                    <span>
                      {
                        "\u0645\u0639\u0644\u0648\u0645\u0627\u062a \u0627\u0644\u0625\u0639\u062f\u0627\u062f \u0627\u0644\u062d\u0627\u0644\u064a\u0629"
                      }
                    </span>
                  </div>
                </section>

                <section className="panel settings-detail-card">
                  <div className="settings-card-heading">
                    <span className="settings-card-icon settings-purple">
                      <Database size={20} />
                    </span>
                    <div>
                      <h3>
                        {
                          "\u0642\u0627\u0639\u062f\u0629 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a"
                        }
                      </h3>
                      <p>
                        {
                          "\u0645\u0635\u062f\u0631 \u062a\u062e\u0632\u064a\u0646 \u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0646\u0638\u0627\u0645"
                        }
                      </p>
                    </div>
                  </div>

                  <div className="settings-detail-row">
                    <span>
                      {
                        "\u0646\u0648\u0639 \u0642\u0627\u0639\u062f\u0629 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a"
                      }
                    </span>
                    <strong>PostgreSQL</strong>
                  </div>

                  <div className="settings-detail-row">
                    <span>
                      {
                        "\u0637\u0631\u064a\u0642\u0629 \u0627\u0644\u0627\u062a\u0635\u0627\u0644"
                      }
                    </span>
                    <strong>
                      {"\u0639\u0628\u0631 \u062e\u062f\u0645\u0629 Backend"}
                    </strong>
                  </div>

                  <div className="settings-card-footer">
                    <Tag t="green">
                      {
                        "\u0645\u0639\u0632\u0648\u0644\u0629 \u0639\u0646 \u0627\u0644\u0648\u0627\u062c\u0647\u0629"
                      }
                    </Tag>
                    <span>
                      {
                        "\u0627\u0644\u0648\u0627\u062c\u0647\u0629 \u0644\u0627 \u062a\u062a\u0635\u0644 \u0645\u0628\u0627\u0634\u0631\u0629\u064b \u0628\u0627\u0644\u0642\u0627\u0639\u062f\u0629"
                      }
                    </span>
                  </div>
                </section>
              </div>

              <div className="settings-note">
                <ShieldCheck size={19} />
                <div>
                  <strong>
                    {
                      "\u0645\u0644\u0627\u062d\u0638\u0629 \u0623\u0645\u0627\u0646"
                    }
                  </strong>
                  <p>
                    {
                      "\u062a\u0639\u062f\u064a\u0644 \u0625\u0639\u062f\u0627\u062f\u0627\u062a \u0627\u0644\u062e\u0627\u062f\u0645 \u0648\u0642\u0627\u0639\u062f\u0629 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u064a\u062a\u0645 \u0645\u0646 \u062e\u0644\u0627\u0644 \u0628\u064a\u0626\u0629 \u0627\u0644\u062e\u0627\u062f\u0645\u060c \u0648\u0644\u064a\u0633 \u0645\u0646 \u0647\u0630\u0647 \u0627\u0644\u0635\u0641\u062d\u0629."
                    }
                  </p>
                </div>
              </div>
            </div>
          )}

          {selectedInvoice && (
            <div className="invoice-modal-overlay">
              <section
                className="invoice-modal"
                role="dialog"
                aria-modal="true"
                aria-label="تفاصيل الفاتورة"
              >
                <div className="invoice-modal-header">
                  <div>
                    <h2>تفاصيل الفاتورة</h2>
                    <p>رقم الفاتورة: {selectedInvoice.invoice_number || "—"}</p>
                  </div>

                  <button
                    type="button"
                    className="modal-close"
                    onClick={closeInvoiceDetails}
                    disabled={invoiceSaving}
                    aria-label="إغلاق"
                  >
                    ×
                  </button>
                </div>

                {invoiceDetailsLoading ? (
                  <div className="invoice-modal-loading">
                    جارٍ تحميل تفاصيل الفاتورة...
                  </div>
                ) : (
                  <div className="invoice-modal-body">
                    <div className="invoice-edit-section">
                      <h3>بيانات الفاتورة</h3>

                      <div className="invoice-form-grid">
                        <label>
                          رقم الفاتورة
                          <input
                            value={invoiceForm.invoice_number ?? ""}
                            onChange={(event) =>
                              setInvoiceForm((current) => ({
                                ...current,
                                invoice_number: event.target.value,
                              }))
                            }
                          />
                        </label>

                        <label>
                          المورد
                          <input
                            value={invoiceForm.supplier_name ?? ""}
                            onChange={(event) =>
                              setInvoiceForm((current) => ({
                                ...current,
                                supplier_name: event.target.value,
                              }))
                            }
                          />
                        </label>

                        <label>
                          تاريخ الفاتورة
                          <input
                            type="date"
                            value={invoiceForm.invoice_date ?? ""}
                            onChange={(event) =>
                              setInvoiceForm((current) => ({
                                ...current,
                                invoice_date: event.target.value,
                              }))
                            }
                          />
                        </label>

                        <label>
                          المبلغ
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={invoiceForm.amount ?? ""}
                            onChange={(event) =>
                              setInvoiceForm((current) => ({
                                ...current,
                                amount: event.target.value,
                              }))
                            }
                          />
                        </label>

                        <label>
                          الضريبة
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={invoiceForm.tax_amount ?? ""}
                            onChange={(event) =>
                              setInvoiceForm((current) => ({
                                ...current,
                                tax_amount: event.target.value,
                              }))
                            }
                          />
                        </label>

                        <label>
                          العملة
                          <input
                            maxLength={10}
                            value={invoiceForm.currency ?? ""}
                            onChange={(event) =>
                              setInvoiceForm((current) => ({
                                ...current,
                                currency: event.target.value,
                              }))
                            }
                            placeholder="مثال: YER"
                          />
                        </label>
                      </div>

                      <label className="invoice-raw-text">
                        النص المستخرج من المستند
                        <textarea
                          rows={7}
                          value={invoiceForm.raw_text ?? ""}
                          onChange={(event) =>
                            setInvoiceForm((current) => ({
                              ...current,
                              raw_text: event.target.value,
                            }))
                          }
                        />
                      </label>

                      <div className="invoice-modal-footer">
                        {[
                          "\u0628\u0627\u0646\u062a\u0638\u0627\u0631 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
                          "\u0642\u064a\u062f \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
                          "\u0645\u0633\u0648\u062f\u0629 - \u062a\u062d\u062a\u0627\u062c \u0645\u0631\u0627\u062c\u0639\u0629",
                        ].includes(
                          String(selectedInvoice.status || "").trim(),
                        ) && (
                          <>
                            <button
                              type="button"
                              className="primary"
                              onClick={() =>
                                reviewInvoice(selectedInvoice, "approve")
                              }
                              disabled={busy || invoiceSaving}
                            >
                              {
                                "\u0627\u0639\u062a\u0645\u0627\u062f \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629"
                              }
                            </button>

                            <button
                              type="button"
                              className="reject-button"
                              onClick={() =>
                                reviewInvoice(selectedInvoice, "reject")
                              }
                              disabled={busy || invoiceSaving}
                            >
                              {
                                "\u0631\u0641\u0636 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629"
                              }
                            </button>
                          </>
                        )}

                        <button
                          type="button"
                          onClick={closeInvoiceDetails}
                          disabled={invoiceSaving}
                        >
                          إغلاق
                        </button>

                        <button
                          type="button"
                          className="primary"
                          onClick={saveInvoiceDetails}
                          disabled={
                            invoiceSaving ||
                            selectedInvoice.status === "مكتملة" ||
                            selectedInvoice.status === "مرفوضة"
                          }
                        >
                          {invoiceSaving ? "جارٍ الحفظ..." : "حفظ التعديلات"}
                        </button>
                      </div>

                      {(selectedInvoice.status === "مكتملة" ||
                        selectedInvoice.status === "مرفوضة") && (
                        <p className="invoice-locked-note">
                          هذه الفاتورة مقفلة ولا يمكن تعديل بياناتها.
                        </p>
                      )}
                    </div>

                    <div className="invoice-preview-section">
                      <h3>معاينة المستند الأصلي</h3>

                      {selectedInvoice.document?.id ? (
                        selectedInvoice.document.content_type ===
                        "application/pdf" ? (
                          <iframe
                            title="معاينة الفاتورة PDF"
                            src={api.getDocumentFileUrl(
                              selectedInvoice.document.id,
                            )}
                            className="invoice-file-preview"
                          />
                        ) : selectedInvoice.document.content_type?.startsWith(
                            "image/",
                          ) ? (
                          <img
                            src={api.getDocumentFileUrl(
                              selectedInvoice.document.id,
                            )}
                            alt="صورة الفاتورة الأصلية"
                            className="invoice-image-preview"
                          />
                        ) : (
                          <p>
                            نوع الملف لا يدعم المعاينة المباشرة.
                            <br />
                            {selectedInvoice.document.filename}
                          </p>
                        )
                      ) : (
                        <p>لا يوجد ملف مستند مرتبط بهذه الفاتورة.</p>
                      )}
                    </div>
                  </div>
                )}
              </section>
            </div>
          )}

          <footer>
            © 2026 AUDIT AI
            <span>منصة التدقيق المالي الذكي</span>
            <b>● متصلة بالـBackend</b>
          </footer>
        </section>
      </main>

      {previewDocument && (
        <div
          className="document-preview-overlay"
          onClick={closeDocumentPreview}
        >
          <div
            className="document-preview-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="document-preview-header">
              <div>
                <h2>{previewDocument.filename}</h2>
                <p>
                  {
                    "\u0645\u0639\u0627\u064a\u0646\u0629 \u0645\u062d\u062a\u0648\u0649 \u0627\u0644\u0645\u0644\u0641"
                  }
                </p>
              </div>
              <button
                type="button"
                className="details-button"
                onClick={closeDocumentPreview}
              >
                {"\u0625\u063a\u0644\u0627\u0642"}
              </button>
            </div>

            {previewLoading && (
              <p className="document-preview-message">
                {
                  "\u062c\u0627\u0631\u064d \u062a\u062d\u0645\u064a\u0644 \u0627\u0644\u0645\u0639\u0627\u064a\u0646\u0629..."
                }
              </p>
            )}

            {!previewLoading && previewData && (
              <div className="document-preview-content">
                {previewData.sheets?.length ? (
                  previewData.sheets.map((sheet, sheetIndex) => (
                    <section
                      className="document-preview-sheet"
                      key={sheetIndex}
                    >
                      <h3>{sheet.name}</h3>
                      <div className="document-preview-table-wrap">
                        <table className="document-preview-table">
                          <thead>
                            <tr>
                              {sheet.columns.map((column, columnIndex) => (
                                <th key={columnIndex}>{column}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {sheet.rows.map((row, rowIndex) => (
                              <tr key={rowIndex}>
                                {row.map((cell, cellIndex) => (
                                  <td key={cellIndex}>{cell}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </section>
                  ))
                ) : (
                  <p className="document-preview-message">
                    {
                      "\u0644\u0627 \u062a\u0648\u062c\u062f \u0628\u064a\u0627\u0646\u0627\u062a \u0644\u0639\u0631\u0636\u0647\u0627"
                    }
                  </p>
                )}
                <p className="document-preview-note">
                  {
                    "\u062a\u064f\u0639\u0631\u0636 \u0623\u0648\u0644 200 \u0635\u0641 \u0645\u0646 \u0643\u0644 \u0648\u0631\u0642\u0629."
                  }
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {toast && (
        <div className="toast">
          <CheckCircle2 size={17} />
          {toast}
          <button onClick={() => setToast("")}>×</button>
        </div>
      )}
    </div>
  );
}
