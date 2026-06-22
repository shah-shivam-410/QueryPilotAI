from __future__ import annotations

import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticToolsParser, JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.config import Settings
from app.models import BuilderResult
from app.schema_loader import SchemaCatalog

SYSTEM_PROMPT = """You are a PostgreSQL SQL builder for a read-only analytics agent.
You will be given a SQL query with errors. Your task is to revise the SQL to fix the errors while keeping it as close to the original as possible.
Only make changes necessary to fix the errors. Do not change the intent of the query.
Return valid JSON with these keys: sql, explanation, tables_used, assumptions.
"""        

USER_PROMPT_TEMPLATE = """Allowed schemas: {schemas}
Blocked tables: {blocked_tables}
Blocked columns: {blocked_columns}
Default maximum rows: {max_rows}

Schema context:
{schema_context}

User requirement:
{requirement}
"""



class SqlRevisor:
    def __init__(self, settings: Settings, catalog: SchemaCatalog) -> None:
        self.settings = settings
        self.catalog = catalog
        self.client = ChatGoogleGenerativeAI(
            google_api_key=self.settings.gemini_api_key,
            model=self.settings.gemini_model,
            temperature=0,
        ) if self.settings.gemini_api_key else None

    def revise(self, requirement: str) -> BuilderResult:
        if self.client is None:
            raise RuntimeError("GEMINI_API_KEY is not configured in .env")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", USER_PROMPT_TEMPLATE),
        ])

        parser = PydanticToolsParser(tools=[BuilderResult], first_tool_only=True)

        chain = prompt | self.client.bind_tools(
                    tools=[BuilderResult], tool_choice="BuilderResult"
                ) | parser

        result = chain.invoke({
            "schemas": ", ".join(self.settings.allowed_schemas),
            "blocked_tables": ", ".join(self.settings.blocked_tables),
            "blocked_columns": ", ".join(self.settings.blocked_columns),
            "max_rows": self.settings.max_rows,
            "schema_context": self.catalog.prompt_context(self.settings.blocked_tables),
            "requirement": requirement,
        })

        return result