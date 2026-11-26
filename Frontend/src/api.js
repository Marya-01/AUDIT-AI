const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1"
).replace(/\/+$/, "");

const API_ROOT = BASE_URL.replace(/\/api\/v1\/?$/, "");

// إنشاء FormData لرفع الملفات
function uploadForm(file) {
  const formData = new FormData();
  formData.append("file", file);
  return formData;
}

// دالة موحدة لجميع طلبات API
async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;

  const headers = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...options.headers,
  };

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;

    try {
      const error = await response.json();

      if (typeof error.detail === "string") {
        message = error.detail;
      } else if (Array.isArray(error.detail)) {
        message = error.detail
          .map((item) => item.msg || JSON.stringify(item))
          .join("، ");
      } else {
        message = error.message || message;
      }
    } catch {
      // الاحتفاظ برسالة HTTP إذا لم تكن الاستجابة JSON
    }

    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

// تنزيل الملفات
async function downloadFile(path) {
  const response = await fetch(`${BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(`تعذر تنزيل الملف: HTTP ${response.status}`);
  }

  return response.blob();
}

export const api = {
  mock: false,

  // اختبار اتصال Backend
  async health() {
    const response = await fetch(`${API_ROOT}/health`);

    if (!response.ok) {
      throw new Error("Backend غير متصل");
    }

    return response.json();
  },

  // لوحة التحكم
  getDashboard() {
    return request("/dashboard/summary");
  },

  getCashflow() {
    return request("/dashboard/cashflow");
  },

  // الفواتير
  getInvoices() {
    return request("/invoices");
  },

  getInvoiceDetails(invoiceId) {
    return request(`/invoices/${encodeURIComponent(invoiceId)}`);
  },

  updateInvoice(invoiceId, data) {
    return request(`/invoices/${encodeURIComponent(invoiceId)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  getDocumentFileUrl(documentId) {
    return `${BASE_URL}/documents/${encodeURIComponent(documentId)}/file`;
  },

  getDocumentDownloadUrl(documentId) {
    return `${BASE_URL}/documents/${encodeURIComponent(documentId)}/download`;
  },

  previewDocument(documentId) {
    return request(`/documents/${encodeURIComponent(documentId)}/preview`);
  },

  uploadInvoice(file) {
    return request("/invoices/upload", {
      method: "POST",
      body: uploadForm(file),
    });
  },

  uploadInvoiceBatch(file) {
    return request("/invoices/upload-batch", {
      method: "POST",
      body: uploadForm(file),
    });
  },

  reviewInvoice(invoiceId, action) {
    return request(`/invoices/${invoiceId}/review`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
  },

  // المعاملات البنكية
  uploadLedger(file) {
    return request("/transactions/upload-ledger", {
      method: "POST",
      body: uploadForm(file),
    });
  },

  getTransactions() {
    return request("/transactions");
  },

  // المطابقة
  runReconciliation() {
    return request("/reconciliation/run", {
      method: "POST",
    });
  },

  getReconciliationResults() {
    return request("/reconciliation/results");
  },

  // المخاطر
  getRisks() {
    return request("/risks");
  },

  scanRisks() {
    return request("/risks/scan", {
      method: "POST",
    });
  },

  // المستندات
  // Smart audit
  runDuplicateAudit(invoiceIds) {
    return request("/audits/duplicate", {
      method: "POST",
      body: JSON.stringify({ invoice_ids: invoiceIds }),
    });
  },

  getDocuments() {
    return request("/documents");
  },

  runDocumentAudit(documentId) {
    return request(`/documents/${encodeURIComponent(documentId)}/audit`, {
      method: "POST",
    });
  },

  getDocumentAudit(documentId) {
    return request(`/documents/${encodeURIComponent(documentId)}/audit`);
  },

  compareDocuments(firstDocumentId, secondDocumentId) {
    return request("/documents/compare", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        first_document_id: firstDocumentId,
        second_document_id: secondDocumentId,
      }),
    });
  },

  uploadDocument(file) {
    return request("/documents/upload", {
      method: "POST",
      body: uploadForm(file),
    });
  },

  deleteDocument(documentId) {
    return request(`/documents/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
    });
  },

  // المساعد الذكي
  chat(message, conversationId = null) {
    return request("/assistant/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
      }),
    });
  },

  // التقارير
  getReports() {
    return request("/reports");
  },

  generateReport(type = "audit_summary", format = "pdf") {
    return request("/reports/generate", {
      method: "POST",
      body: JSON.stringify({
        type,
        format,
      }),
    });
  },

  duplicateAuditExportUrl(invoiceIds = []) {
    const params = new URLSearchParams();

    invoiceIds.forEach((id) => {
      params.append("invoice_ids", String(id));
    });

    return `${BASE_URL}/audits/duplicate/export?${params.toString()}`;
  },

  downloadReport(reportId) {
    return downloadFile(`/reports/${encodeURIComponent(reportId)}/download`);
  },

  deleteReport(reportId) {
    return request(`/reports/${encodeURIComponent(reportId)}`, {
      method: "DELETE",
    });
  },
};
