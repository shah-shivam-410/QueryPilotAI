from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
import logging

from app.config import get_settings
from app.db import QueryExecutor
from app.models import AskRequest, AskResponse, ValidationRequest, ValidationResult
from app.schema_loader import SchemaCatalog, load_schema_catalog
from app.sql_builder import SqlBuilder
from app.sql_validator import SqlValidator

logging.basicConfig(
    level=logging.INFO, # Set the lowest severity level to capture
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),   # Save logs to a file
        logging.StreamHandler()          # Print logs to the console
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Query Agent",
    description="Natural-language-to-SQL service with deterministic SELECT-only guardrails.",
    version="0.1.0",
)


@lru_cache
def get_catalog() -> SchemaCatalog:
    settings = get_settings()
    return load_schema_catalog(settings.schema_file, settings.allowed_schemas)


@lru_cache
def get_validator() -> SqlValidator:
    return SqlValidator(get_settings(), get_catalog())


@lru_cache
def get_builder() -> SqlBuilder:
    return SqlBuilder(get_settings(), get_catalog())


@lru_cache
def get_executor() -> QueryExecutor:
    return QueryExecutor(get_settings())


@app.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    catalog = get_catalog()
    return {
        "status": "ok",
        "allowed_schemas": settings.allowed_schemas,
        "tables_loaded": len(catalog.tables),
        "database_configured": bool(settings.database_url),
        "llm_configured": bool(settings.openai_api_key),
    }


@app.get("/schema/summary")
def schema_summary() -> dict[str, list[str]]:
    return get_catalog().summary()


@app.post("/validate", response_model=ValidationResult)
def validate_sql(request: ValidationRequest) -> ValidationResult:
    return get_validator().validate(request.sql)


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    try:
        builder_result = get_builder().build(request.requirement)
    except Exception as exc:
        logger.error(f"SQL builder failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"SQL builder failed: {exc}") from exc

    validation_result = get_validator().validate(builder_result.sql)
    if not validation_result.is_valid or not request.execute:
        return AskResponse(
                requirement = request.requirement, 
                query = validation_result.sanitized_sql or builder_result.sql,
                explanation = builder_result.explanation,
                tables_used = builder_result.tables_used,
                assumptions = builder_result.assumptions,
            )

    try:
        result = get_executor().execute(validation_result.sanitized_sql or builder_result.sql)
    except Exception as exc:
        logger.error(f"SQL execution failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"SQL execution failed: {exc}") from exc

    resp = AskResponse(
        requirement=request.requirement,
        query=validation_result.sanitized_sql or builder_result.sql,
        explanation=builder_result.explanation,
        tables_used=builder_result.tables_used,
        assumptions=builder_result.assumptions,
        result=result,
    )
    # logger.info(f"AskResponse: {resp}")
    logger.info(f"AskResponse: {resp}")
    return resp


@app.post("/test", response_model=str)
def ask(request: AskRequest) -> AskResponse:
    try:
        builder_result = get_builder().build(request.requirement)
        logger.info("-"*30)
        logger.info(f"Built SQL: {builder_result.sql}")
        logger.info("-"*30)
        logger.info(f"explanation: {builder_result.explanation}")
        logger.info("-"*30)
        logger.info(f"tables_used: {builder_result.tables_used}")
        logger.info("-"*30)
        logger.info(f"assumptions: {builder_result.assumptions}")
        logger.info("-"*30)
        logger.info(f"requirement: {request.requirement}")
        logger.info("-"*30)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SQL builder failed: {exc}") from exc

    return builder_result.sql
