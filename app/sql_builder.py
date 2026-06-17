from __future__ import annotations

import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.config import Settings
from app.models import BuilderResult
from app.schema_loader import SchemaCatalog


SYSTEM_PROMPT = """You are a PostgreSQL SQL builder for a read-only analytics agent.
Generate exactly one SELECT query for the user's requirement.
Use only the provided schema context.
Use fully-qualified table names.
Do not use blocked tables or sensitive columns.
Do not generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, COPY, CALL, or DO.
Prefer simple, auditable SQL over clever SQL.
Return valid JSON with these keys: sql, explanation, tables_used, assumptions.
"""

class SqlBuilder:
    def __init__(self, settings: Settings, catalog: SchemaCatalog) -> None:
        self.settings = settings
        self.catalog = catalog
        self.client = ChatGoogleGenerativeAI(
            google_api_key=self.settings.gemini_api_key,
            model=self.settings.gemini_model,
            temperature=0,
        ) if self.settings.gemini_api_key else None

    def build(self, requirement: str) -> BuilderResult:
        if self.client is None:
            raise RuntimeError("GEMINI_API_KEY is not configured in .env")

        user_prompt = f"""Allowed schemas: {", ".join(self.settings.allowed_schemas)}
            Blocked tables: {", ".join(self.settings.blocked_tables)}
            Blocked columns: {", ".join(self.settings.blocked_columns)}
            Default maximum rows: {self.settings.max_rows}

            Schema context:
            {self.catalog.prompt_context(self.settings.blocked_tables)}

            User requirement:
            {requirement}
            """
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        parser = JsonOutputParser()

        chain = prompt | self.client | parser

        result = chain.invoke({
            "schemas": ", ".join(self.settings.allowed_schemas),
            "blocked_tables": ", ".join(self.settings.blocked_tables),
            "blocked_columns": ", ".join(self.settings.blocked_columns),
            "max_rows": self.settings.max_rows,
            "schema_context": self.catalog.prompt_context(self.settings.blocked_tables),
            "requirement": requirement,
        })

        return BuilderResult(
            sql=result.get("sql", ""),
            explanation=result.get("explanation", ""),
            tables_used=result.get("tables_used", []),
            assumptions=result.get("assumptions", []),
        )
        
