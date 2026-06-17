from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    database_url: str = Field(default="", alias="DATABASE_URL")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    schema_file: Path = Field(default=ROOT_DIR / "schema_Adventureworks_DB.sql", alias="SCHEMA_FILE")
    allowed_schemas: tuple[str, ...] = ("production", "sales")
    max_rows: int = Field(default=100, alias="MAX_ROWS")
    statement_timeout_ms: int = Field(default=5000, alias="STATEMENT_TIMEOUT_MS")
    blocked_tables: tuple[str, ...] = (
        "sales.creditcard",
        "sales.personcreditcard",
    )
    blocked_columns: tuple[str, ...] = (
        "cardnumber",
        "cardtype",
        "expmonth",
        "expyear",
        "passwordhash",
        "passwordsalt",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
