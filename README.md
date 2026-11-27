# AUDIT-AI | منصة التدقيق المالي الذكية

منصة عربية ذكية لتحليل البيانات المالية، ومراجعة الفواتير، ومطابقة المعاملات  واكتشاف مؤشرات المخاطر، وإعداد تقارير التدقيق، مع مساعد ذكي مدعوم بتقنيات الذكاء الاصطناعي.

## مكونات النظام

- **Frontend:** React + Vite، واجهة عربية تدعم RTL.
- **Backend:** Python + FastAPI.
- **Database:** PostgreSQL 16.
- **AI Assistant:** Ollama باستخدام النموذج `qwen2.5:7b-instruct`.
- **API Documentation:** Swagger عبر FastAPI.

تعتمد عمليات الاستخراج والحساب والمطابقة وتقييم المخاطر على قواعد برمجية محددة. ويستخدم المساعد الذكاء الاصطناعي لشرح النتائج وتقديم التوصيات، ولا يُعد حكمًا نهائيًا بوقوع الاحتيال.

---

## 1. متطلبات التشغيل

قبل تشغيل المشروع، يجب تثبيت البرامج التالية:

1. Python 3.11 أو أحدث.
2. Node.js 18 أو أحدث مع npm.
3. Docker Desktop مع Docker Compose.
4. Ollama لتشغيل المساعد الذكي محليًا.

## 2. تنزيل المشروع

افتح PowerShell ونفّذ:

```powershell
git clone https://github.com/Marya-01/AUDIT-AI.git
cd AUDIT-AI
```

## 3. تشغيل قاعدة البيانات

من المجلد الرئيسي للمشروع:

```powershell
docker compose -f Backend/docker-compose.yml up -d
```

سيتم تشغيل PostgreSQL وإنشاء قاعدة البيانات `audit_ai` والمستخدم `audit_user` وفق إعدادات Docker Compose.

## 4. إعداد وتشغيل Backend

انتقل إلى مجلد Backend:

```powershell
cd Backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

تأكد من إعداد ملف `Backend/.env` بالقيم التالية:

```env
DATABASE_URL=postgresql+psycopg://audit_user:audit_password@localhost:5432/audit_ai
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
UPLOAD_DIR=storage
MAX_UPLOAD_MB=20
```

بعد ذلك شغّل الخادم:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

روابط Backend:

- واجهة API:
  http://127.0.0.1:8000/api/v1

- توثيق Swagger:
  http://127.0.0.1:8000/docs

- فحص حالة الخادم:
  http://127.0.0.1:8000/health

عند بدء التشغيل، ينشئ التطبيق الجداول الناقصة في قاعدة البيانات المحددة في الإعدادات.

## 5. إعداد وتشغيل Frontend

افتح نافذة PowerShell ثانية، ثم انتقل إلى مجلد المشروع الرئيسي:

```powershell
cd Frontend
npm install
Copy-Item .env.example .env
```

تأكد من إعداد ملف `Frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_USE_MOCKS=false
```

ثم شغّل الواجهة:

```powershell
npm run dev
```

افتح المتصفح على:

http://localhost:5173

## 6. تشغيل المساعد الذكي

يستخدم المشروع Ollama لتشغيل نموذج الذكاء الاصطناعي محليًا.

أولًا، حمّل Ollama من الموقع الرسمي:

https://ollama.com/download

ثم افتح نافذة PowerShell ونفّذ:

```powershell
ollama pull qwen2.5:7b-instruct
```

للتحقق من تحميل النموذج:

```powershell
ollama list
```

يجب أن تكون خدمة Ollama متاحة على العنوان:

`http://127.0.0.1:11434`

يستدعي Backend النموذج تلقائيًا عند استخدام المساعد الذكي.

إذا تعذر الاتصال بـ Ollama، يستخدم التطبيق ردودًا احتياطية مبنية على القواعد والبيانات المتاحة، وقد لا تتوفر جميع قدرات المحادثة الذكية.

## 7. اختبار المشروع

بعد تشغيل الخدمات، يمكن للجنة التحكيم تنفيذ الاختبارات التالية:

1. فتح لوحة التحكم والتحقق من ظهور البيانات.
2. التحقق من حالة Backend عبر `/health`.
3. مراجعة واجهات API عبر `/docs`.
4. تجربة إدارة الفواتير.
5. تجربة المعاملات والتسوية.
6. تجربة اكتشاف مؤشرات المخاطر.
7. تجربة مركز المستندات ورفع ملفات الاختبار.
8. تجربة التقارير وتصديرها.
9. اختبار المساعد الذكي بعد تشغيل Ollama وتحميل النموذج.

يُفضّل استخدام بيانات وملفات اختبار غير حساسة.

## 8. البيانات والخصوصية

- تُخزّن البيانات في قاعدة PostgreSQL المحلية.
- تُحفظ الملفات المرفوعة محليًا وفق إعداد `UPLOAD_DIR`.
- لا يتضمن مستودع GitHub ملفات قاعدة البيانات أو المستندات المحلية.
- لا ترفع ملفات `.env` أو كلمات المرور أو مفاتيح API إلى GitHub.
- يحتاج كل جهاز اختبار إلى إعداد بيئته وقاعدة بياناته الخاصة.
- لا تستخدم بيانات مالية حقيقية أو سرية دون موافقات وضوابط مناسبة.

## 9. الأمان وحدود نسخة الاختبار

هذه النسخة مخصصة للتشغيل والتقييم المحلي.

قبل نشر النظام على الإنترنت، يجب إضافة المصادقة وإدارة الصلاحيات ومراجعة إعدادات الأمان.

نتائج تحليل المخاطر تمثل مؤشرات تستدعي مراجعة المدقق، ولا تمثل إثباتًا قاطعًا لوقوع الاحتيال.

## 10. بنية المشروع

```text
AUDIT-AI/
│
├── Backend/
│   ├── app/
│   ├── tests/
│   ├── .env.example
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── Frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── .env.example
│
├── .gitignore
└── README.md
```

## معلومات المشروع

**اسم المشروع:** AUDIT-AI

**التصنيف:** الذكاء الاصطناعي والتقنية المالية (FinTech).

**التقنيات:** Python, FastAPI, React, Vite, PostgreSQL, Ollama.

**مستودع المشروع:**

https://github.com/Marya-01/AUDIT-AI

للمزيد من التفاصيل حول مكونات النظام، راجع ملفات README الموجودة داخل مجلدي Backend وFrontend.
