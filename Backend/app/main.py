from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import Base, engine
from . import models
from .routers import dashboard,invoices,transactions,reconciliation,risks,documents,assistant,reports,audits

app=FastAPI(title="AUDIT AI API",description="واجهة API لمنصة التدقيق المالي الذكي",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.get("/health",tags=["الصحة"])
def health(): return {"status":"ok","service":"AUDIT AI API"}
app.include_router(dashboard.router,prefix="/api/v1")
app.include_router(invoices.router,prefix="/api/v1")
app.include_router(transactions.router,prefix="/api/v1")
app.include_router(reconciliation.router,prefix="/api/v1")
app.include_router(risks.router,prefix="/api/v1")
app.include_router(documents.router,prefix="/api/v1")
app.include_router(assistant.router,prefix="/api/v1")
app.include_router(reports.router,prefix="/api/v1")

app.include_router(audits.router,prefix="/api/v1")
