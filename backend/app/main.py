from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai import provider_router, router as ai_router
from app.api.export import router as export_router
from app.api.projects import router as projects_router
from app.api.prompts import router as prompts_router
from app.api.samples import router as samples_router
from app.api.statistics import router as statistics_router
from app import models
from app.config import CORS_ORIGINS, SEED_SAMPLE_DATA
from app.database import SessionLocal, init_db
from app.services.dataset import seed_database

app = FastAPI(title="QA Review Workbench API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(samples_router)
app.include_router(prompts_router)
app.include_router(ai_router)
app.include_router(provider_router)
app.include_router(statistics_router)
app.include_router(export_router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        db.query(models.Sample).filter(models.Sample.review_status == "SKIP").update({"review_status": "PASS"})
        db.commit()
        if SEED_SAMPLE_DATA:
            seed_database(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"ok": True}
