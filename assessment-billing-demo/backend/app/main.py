from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import assessments, billing

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Assessment Billing Demo API",
    description="Portfolio demo: FastAPI microservice for user assessments and billing status.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assessments.router, prefix="/api")
app.include_router(billing.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
