from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from app.config import Settings
from app.models import ValidationResult
from app.schema_loader import SchemaCatalog


WRITE_KEYWORDS_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|GRANT|REVOKE|COPY|CALL|DO|VACUUM|ANALYZE)\b",
    re.IGNORECASE,
)
COMMENT_RE = re.compile(r"(--|/\*)")
LIMIT_RE = re.compile(r"\bLIMIT\s+(?P<limit>\d+)\b", re.IGNORECASE)


class SqlValidator:
    def __init__(self, settings: Settings, catalog: SchemaCatalog) -> None:
        self.settings = settings
        self.catalog = catalog

    def validate(self, sql: str) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        cleaned_sql = sql.strip().rstrip(";").strip()

        if not cleaned_sql:
            return ValidationResult(is_valid=False, errors=["SQL is empty."])
        if COMMENT_RE.search(cleaned_sql):
            errors.append("SQL comments are not allowed.")
        if WRITE_KEYWORDS_RE.search(cleaned_sql):
            errors.append("Only read-only SELECT queries are allowed.")

        try:
            parsed_statements = sqlglot.parse(cleaned_sql, read="postgres")
        except sqlglot.errors.ParseError as exc:
            return ValidationResult(is_valid=False, errors=[f"SQL parse error: {exc}"])

        if len(parsed_statements) != 1:
            errors.append("Only one SQL statement is allowed.")

        expression = parsed_statements[0]
        if not isinstance(expression, (exp.Select, exp.Union, exp.With)):
            errors.append("The statement must be a SELECT query.")

        tables_used = self._extract_tables(expression)
        for table in tables_used:
            schema, _, name = table.partition(".")
            if schema not in self.settings.allowed_schemas:
                errors.append(f"Schema '{schema}' is not allowed.")
            if table not in self.catalog.allowed_table_names:
                errors.append(f"Table '{table}' is not in the loaded schema allowlist.")
            if table in self.settings.blocked_tables:
                errors.append(f"Table '{table}' is blocked because it may contain sensitive data.")
            if not name:
                errors.append(f"Table '{table}' must be schema-qualified.")

        blocked_columns = {column.lower() for column in self.settings.blocked_columns}
        for column in expression.find_all(exp.Column):
            if column.name.lower() in blocked_columns:
                errors.append(f"Column '{column.name}' is blocked because it may contain sensitive data.")

        sanitized_sql = None
        if not errors:
            sanitized_sql, limit_warnings = self._apply_limit(cleaned_sql)
            warnings.extend(limit_warnings)

        return ValidationResult(
            is_valid=not errors,
            sanitized_sql=sanitized_sql,
            errors=errors,
            warnings=warnings,
            tables_used=tables_used,
        )

    def _extract_tables(self, expression: exp.Expression) -> list[str]:
        tables: set[str] = set()
        for table in expression.find_all(exp.Table):
            schema = table.db
            table_name = table.name
            full_name = f"{schema}.{table_name}" if schema else table_name
            tables.add(full_name.lower())
        return sorted(tables)

    def _apply_limit(self, sql: str) -> tuple[str, list[str]]:
        warnings: list[str] = []
        match = LIMIT_RE.search(sql)
        if not match:
            warnings.append(f"No LIMIT found; added LIMIT {self.settings.max_rows}.")
            return f"{sql}\nLIMIT {self.settings.max_rows}", warnings

        requested_limit = int(match.group("limit"))
        if requested_limit <= self.settings.max_rows:
            return sql, warnings

        warnings.append(f"LIMIT {requested_limit} reduced to {self.settings.max_rows}.")
        return LIMIT_RE.sub(f"LIMIT {self.settings.max_rows}", sql, count=1), warnings
