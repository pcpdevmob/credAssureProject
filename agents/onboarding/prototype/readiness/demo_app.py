"""Stand-alone backend for running the Onboarding Agent on its own: Swagger, demos, and
pointing the FinBridge UI at it before the team's backend is ready.

    uvicorn readiness.demo_app:app --reload      then open http://127.0.0.1:8000/docs

The team's real backend includes `readiness.api.router` instead of using this file.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import case_store
from .api import router as readiness_router
from .generate_hr_data import ensure_hr_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_hr_store()
    case_store.seed_demo_cases()
    yield


app = FastAPI(title="CredAssure: Employee Onboarding Agent", lifespan=lifespan)

# Let the FinBridge UI (npm run dev on port 3000) call this backend from the browser.
app.add_middleware(CORSMiddleware,
                   allow_origins=os.getenv("CREDASSURE_UI_ORIGINS",
                                           "http://localhost:3000,http://localhost:5173").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["*"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/cases")
def list_cases() -> list[dict]:
    return case_store.list_cases()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> dict:
    case = case_store.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return case


app.include_router(readiness_router)
