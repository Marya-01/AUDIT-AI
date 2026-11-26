# AUDIT AI — Backend (Python + FastAPI + PostgreSQL)

Backend فقط، جاهز للربط مع واجهة React/Vite السابقة.

## 1) المتطلبات
- Python 3.11 أو أحدث
- Docker Desktop (موصى به لتشغيل PostgreSQL) أو PostgreSQL 15+
- مشروع Frontend يعمل على `http://localhost:5173`

## 2) تشغيل قاعدة البيانات
من مجلد المشروع:
```powershell
docker compose up -d
```
ينشئ PostgreSQL قاعدة `audit_ai` والمستخدم `audit_user`.

## 3) إعداد Python
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```
افتح `.env` وتأكد من `DATABASE_URL`. لا ترفع ملف `.env` إلى Git.

## 4) تشغيل الخادم
```powershell
uvicorn app.main:app --reload
```
- API: http://127.0.0.1:8000/api/v1
- توثيق Swagger: http://127.0.0.1:8000/docs
- فحص الصحة: http://127.0.0.1:8000/health

عند أول تشغيل تُنشأ الجداول وتُضاف بيانات تجريبية إن كانت قاعدة البيانات فارغة.

## 5) ربطه مع Frontend
في مجلد Frontend السابق:
1. افتح `.env` (أنشئه من `.env.example` إذا لم يوجد).
2. ضع:
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_USE_MOCKS=false
```
3. أوقف Vite ثم أعد تشغيله:
```powershell
npm run dev
```
لا تضع بيانات اتصال PostgreSQL في Frontend. المتصفح يتصل بـ FastAPI، وFastAPI وحده يتصل بقاعدة البيانات.

## 6) المسارات المتاحة
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/dashboard/cashflow?period=6m`
- `GET /api/v1/invoices?search=&status=&page=1`
- `POST /api/v1/invoices/upload` (multipart: `file`)
- `GET /api/v1/transactions?search=&status=`
- `POST /api/v1/reconciliation/run`
- `GET /api/v1/reconciliation/results`
- `GET /api/v1/risks`
- `POST /api/v1/risks/scan`
- `GET /api/v1/documents`
- `POST /api/v1/documents/upload` (multipart: `file`)
- `POST /api/v1/assistant/chat` JSON `{ "message": "...", "conversation_id": null }`
- `GET /api/v1/reports`
- `POST /api/v1/reports/generate` JSON `{ "type": "audit_summary", "format": "pdf" }`
- `GET /api/v1/reports/{report_id}/download`

## 7) ملاحظات مهمة
- البيانات الأولية توضيحية فقط؛ استبدلها ببيانات المؤسسة الحقيقية بعد مراجعتها.
- رفع الملفات يخزنها محلياً في `storage/` ويسجل بياناتها في PostgreSQL. لا يوجد OCR فعلي في هذه النسخة.
- محرك كشف المخاطر الحالي قواعد أولية قابلة للتفسير (مثل تكرار رقم/مبلغ الفاتورة). لا يُعد حكماً بوقوع احتيال.
- مساعد التدقيق يعمل بردود احتياطية مبنية على السجلات؛ لم يتم ربط نموذج لغوي خارجي أو Ollama بعد.
- لا توجد مصادقة مستخدمين في نسخة التطوير. أضف تسجيل الدخول والصلاحيات قبل النشر.
