from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    requirement: str = Field(min_length=3)
    execute: bool = True


class BuilderResult(BaseModel):
    sql: str
    explanation: str = ""
    tables_used: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class ValidationRequest(BaseModel):
    sql: str = Field(min_length=1)


class ValidationResult(BaseModel):
    is_valid: bool
    sanitized_sql: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    tables_used: list[str] = Field(default_factory=list)


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class AskResponse(BaseModel):
    requirement: str
    builder: BuilderResult | None = None
    validation: ValidationResult
    result: QueryResult | None = None
