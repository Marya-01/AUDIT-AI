# API Contract — FastAPI
Base URL: `/api/v1`
- GET `/dashboard/summary`
- GET `/dashboard/cashflow?period=6m`
- GET `/invoices?search=&status=&page=1`
- POST `/invoices/upload` (multipart field: `file`)
- GET `/transactions?search=&status=`
- POST `/reconciliation/run`
- GET `/reconciliation/results`
- GET `/risks`
- POST `/risks/scan`
- GET `/documents`
- POST `/documents/upload` (multipart field: `file`)
- POST `/assistant/chat` JSON `{ "message": "...", "conversation_id": null }`
- GET `/reports`
- POST `/reports/generate` JSON `{ "type": "audit_summary", "format": "pdf" }`

أخطاء API المقترحة: `{ "detail": "رسالة واضحة", "code": "VALIDATION_ERROR" }`.
استخدم JWT للمصادقة، وتحقق من صلاحيات الملفات في الخادم.
