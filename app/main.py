from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

app = FastAPI(title="SAGE - Strategic Analytics for Guided Execution")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "SAGE API"}


@app.get("/health/db")
def db_health_check(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1")).scalar()
    return {"status": "ok", "db_response": result}