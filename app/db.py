from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import Settings
from app.models import QueryResult


class QueryExecutor:
    def __init__(self, settings: Settings) -> None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured in .env")
        self.settings = settings
        self.engine: Engine = create_engine(settings.database_url, pool_pre_ping=True)

    def execute(self, sql: str) -> QueryResult:
        with self.engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text(f"SET LOCAL statement_timeout = {int(self.settings.statement_timeout_ms)}"))
                result = connection.execute(text(sql))
                rows = [dict(row._mapping) for row in result]
                transaction.commit()
            except Exception:
                transaction.rollback()
                raise

        columns = list(rows[0].keys()) if rows else []
        return QueryResult(columns=columns, rows=rows, row_count=len(rows))
