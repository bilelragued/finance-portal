"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database URL - supports both SQLite (local) and PostgreSQL (production)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback to SQLite for local development
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'finance.db')}"

# Fix for SQLAlchemy 1.4+ with Supabase
# Supabase uses postgres:// but SQLAlchemy 1.4+ requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine with appropriate settings
connect_args = {}
is_sqlite = DATABASE_URL.startswith("sqlite")
if is_sqlite:
    connect_args = {"check_same_thread": False}

# Pool settings - SQLite doesn't support connection pooling
pool_settings = {
    "pool_pre_ping": True,  # Verify connections before using
    "pool_recycle": 300,  # Recycle connections after 5 minutes
}

# Add connection pool settings for PostgreSQL (not supported by SQLite)
if not is_sqlite:
    pool_settings.update({
        "pool_size": 10,  # Maintain 10 connections in pool
        "max_overflow": 20,  # Allow up to 20 extra temporary connections
        "pool_timeout": 30,  # Wait up to 30 seconds for a connection
    })

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **pool_settings
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    from app import models  # Import models to register them
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as e:
        # Tables/types may already exist, which is fine
        print(f"Database init note: {e}")


