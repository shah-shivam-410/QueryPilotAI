# AI Query Agent

Agentic natural-language-to-SQL service for Postgres with deterministic guardrails.

The LLM only generates candidate SQL. Validation and execution are handled by normal code.

## Current Scope

- Allowed schemas: `production`, `sales`
- Schema source: `schema_Adventureworks_DB.sql`
- Query policy: single `SELECT` statement only
- Execution: read-only transaction, statement timeout, row limit
- Sensitive defaults: blocks `sales.creditcard`, `sales.personcreditcard`, and card/password-like columns

## Setup

Create a local `.env` file:

```env
DATABASE_URL=postgresql+psycopg://ai_query_agent:your_password@localhost:5432/your_db_name
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
MAX_ROWS=100
STATEMENT_TIMEOUT_MS=5000
```

Install dependencies:

```bash
uv sync
```

Run the API:

```bash
uv run python main.py
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Example

POST `/ask`

```json
{
  "requirement": "Give me the most ordered product name and id that was ordered in last 30 days.",
  "execute": true
}
```

POST `/validate`

```json
{
  "sql": "SELECT p.productid, p.name FROM production.product p LIMIT 10"
}
```

## Architecture

```text
User requirement
  -> SQL builder using LLM and schema context
  -> deterministic SQL validator
  -> read-only Postgres executor
  -> JSON result
```
