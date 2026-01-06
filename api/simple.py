"""Simple FastAPI test without database."""
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/simple")
async def simple():
    return {"status": "ok", "message": "Simple FastAPI works!"}
