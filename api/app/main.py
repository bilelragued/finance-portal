"""FastAPI application entry point."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import accounts, transactions, upload, categories, categorization, reports, nlp
from app.auth import verify_credentials


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    init_db()
    yield
    # Shutdown (nothing to do)


# Create FastAPI app
app = FastAPI(
    title="Finance Portal API",
    description="Personal finance management with intelligent categorization",
    version="1.0.0",
    lifespan=lifespan,
    dependencies=[Depends(verify_credentials)]  # Apply auth to all routes
)

# Get allowed origins from environment or use defaults
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]

# Add production frontend URL if set
if frontend_url not in allowed_origins:
    allowed_origins.append(frontend_url)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(accounts.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(categorization.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(nlp.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Finance Portal API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
