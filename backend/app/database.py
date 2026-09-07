import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://mf_admin:change_this_local_password@localhost:5432/mf_tracker"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


DEMO_PASSWORD_HASH = "pbkdf2_sha256$600000$Swm2_mffPgtNNnZAkpMVNQ==$v6xRO-FaApTjvJnGMdAbEDNwY3t-Z-IIqfq0ndMJn8E="


def run_migrations() -> None:
    """Apply the small, idempotent compatibility migrations used by this demo."""
    statements = (
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
        "ALTER TABLE mutual_funds ADD COLUMN IF NOT EXISTS amfi_scheme_code VARCHAR(20)",
        "ALTER TABLE fund_nav ADD COLUMN IF NOT EXISTS nav_source VARCHAR(20) NOT NULL DEFAULT 'seed'",
        """CREATE TABLE IF NOT EXISTS nav_sync_runs (
            id BIGSERIAL PRIMARY KEY,
            started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMPTZ,
            status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'success', 'failed')),
            matched_funds INTEGER NOT NULL DEFAULT 0,
            fetched_records INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_mutual_funds_amfi_scheme_code ON mutual_funds (amfi_scheme_code) WHERE amfi_scheme_code IS NOT NULL",
        "UPDATE mutual_funds SET category = 'Flexi Cap' WHERE ticker_symbol = 'QUANTACTIVE'",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(
            text("UPDATE users SET password_hash = :password_hash WHERE email = :email AND password_hash IS NULL"),
            {"password_hash": DEMO_PASSWORD_HASH, "email": "demo@mftracker.local"},
        )


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
