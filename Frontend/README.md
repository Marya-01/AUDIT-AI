# AUDIT AI Frontend
واجهة عربية RTL تفاعلية باستخدام React + Vite، مجهزة للربط مع Backend Python/FastAPI وقاعدة PostgreSQL.

## التشغيل
يتطلب Node.js 18+
```bash
npm install
npm run dev
```
ثم افتح http://localhost:5173

## بناء الإنتاج
```bash
npm run build
```

## الربط مع FastAPI
انسخ `.env.example` إلى `.env` ثم اجعل `VITE_USE_MOCKS=false` واضبط `VITE_API_BASE_URL`.
عقد المسارات المقترح موجود في `docs/API_CONTRACT.md`.
قاعدة PostgreSQL تتصل بها واجهة FastAPI فقط، ولا يجب الاتصال بها مباشرة من المتصفح.

## تنبيه
هذه نسخة Frontend فقط. البيانات والفحوص والمساعد تجريبية، ورفع الملفات محلي للعرض ولا يرسلها إلى خادم.
