from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE (?P<schema>[a-z_][\w]*)\.(?P<table>[a-z_][\w]*) \(\n(?P<body>.*?)\n\);",
    re.IGNORECASE | re.DOTALL,
)
TABLE_COMMENT_RE = re.compile(
    r"COMMENT ON TABLE (?P<schema>[a-z_][\w]*)\.(?P<table>[a-z_][\w]*) IS '(?P<comment>(?:''|[^'])*)';",
    re.IGNORECASE,
)
COLUMN_COMMENT_RE = re.compile(
    r"COMMENT ON COLUMN (?P<schema>[a-z_][\w]*)\.(?P<table>[a-z_][\w]*)\.(?P<column>[a-z_][\w]*) IS '(?P<comment>(?:''|[^'])*)';",
    re.IGNORECASE,
)
PRIMARY_KEY_RE = re.compile(
    r"ALTER TABLE ONLY (?P<schema>[a-z_][\w]*)\.(?P<table>[a-z_][\w]*)\s+ADD CONSTRAINT .*? PRIMARY KEY \((?P<columns>.*?)\);",
    re.IGNORECASE | re.DOTALL,
)
FOREIGN_KEY_RE = re.compile(
    r"ALTER TABLE ONLY (?P<schema>[a-z_][\w]*)\.(?P<table>[a-z_][\w]*)\s+ADD CONSTRAINT .*? FOREIGN KEY \((?P<columns>.*?)\) REFERENCES (?P<ref_schema>[a-z_][\w]*)\.(?P<ref_table>[a-z_][\w]*)\((?P<ref_columns>.*?)\)",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool
    default: str | None = None
    comment: str | None = None


@dataclass
class TableInfo:
    schema: str
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    comment: str | None = None
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.schema}.{self.name}"


def _unescape_comment(value: str) -> str:
    return value.replace("''", "'")


def _split_columns(value: str) -> list[str]:
    return [part.strip().strip('"') for part in value.split(",")]


def _parse_column(line: str) -> ColumnInfo | None:
    stripped = line.strip().rstrip(",")
    if not stripped or stripped.upper().startswith("CONSTRAINT "):
        return None

    match = re.match(r'"?(?P<name>[a-z_][\w]*)"?\s+(?P<rest>.+)$', stripped, re.IGNORECASE)
    if not match:
        return None

    name = match.group("name")
    rest = match.group("rest")
    nullable = "NOT NULL" not in rest.upper()
    default = None

    default_match = re.search(r"\sDEFAULT\s+(?P<default>.*?)(?:\s+NOT NULL|\s+NULL)?$", rest, re.IGNORECASE)
    if default_match:
        default = default_match.group("default").strip()
        rest = rest[: default_match.start()].strip()

    data_type = re.sub(r"\s+NOT NULL$", "", rest, flags=re.IGNORECASE).strip()
    return ColumnInfo(name=name, data_type=data_type, nullable=nullable, default=default)


class SchemaCatalog:
    def __init__(self, tables: dict[str, TableInfo]) -> None:
        self.tables = tables

    @property
    def allowed_table_names(self) -> set[str]:
        return set(self.tables)

    def summary(self) -> dict[str, list[str]]:
        schemas: dict[str, list[str]] = {}
        for table in self.tables.values():
            schemas.setdefault(table.schema, []).append(table.name)
        return {schema: sorted(tables) for schema, tables in sorted(schemas.items())}

    def prompt_context(self, blocked_tables: tuple[str, ...] = ()) -> str:
        lines: list[str] = []
        for full_name in sorted(self.tables):
            if full_name in blocked_tables:
                continue
            table = self.tables[full_name]
            lines.append(f"Table: {table.full_name}")
            if table.comment:
                lines.append(f"Description: {table.comment}")
            for column in table.columns:
                nullable = "nullable" if column.nullable else "not null"
                comment = f" - {column.comment}" if column.comment else ""
                lines.append(f"- {column.name}: {column.data_type}, {nullable}{comment}")
            if table.primary_key:
                lines.append(f"Primary key: {', '.join(table.primary_key)}")
            if table.foreign_keys:
                lines.append("Foreign keys:")
                lines.extend(f"- {fk}" for fk in table.foreign_keys)
            lines.append("")
        return "\n".join(lines).strip()


def load_schema_catalog(path: Path, allowed_schemas: tuple[str, ...]) -> SchemaCatalog:
    sql = path.read_text(encoding="utf-8")
    allowed = set(allowed_schemas)
    tables: dict[str, TableInfo] = {}

    for match in CREATE_TABLE_RE.finditer(sql):
        schema = match.group("schema")
        table_name = match.group("table")
        if schema not in allowed:
            continue

        columns = [
            column
            for line in match.group("body").splitlines()
            if (column := _parse_column(line)) is not None
        ]
        table = TableInfo(schema=schema, name=table_name, columns=columns)
        tables[table.full_name] = table

    for match in TABLE_COMMENT_RE.finditer(sql):
        full_name = f"{match.group('schema')}.{match.group('table')}"
        if full_name in tables:
            tables[full_name].comment = _unescape_comment(match.group("comment"))

    column_comments: dict[tuple[str, str, str], str] = {}
    for match in COLUMN_COMMENT_RE.finditer(sql):
        column_comments[(match.group("schema"), match.group("table"), match.group("column"))] = _unescape_comment(
            match.group("comment")
        )

    for table in tables.values():
        table.columns = [
            ColumnInfo(
                name=column.name,
                data_type=column.data_type,
                nullable=column.nullable,
                default=column.default,
                comment=column_comments.get((table.schema, table.name, column.name)),
            )
            for column in table.columns
        ]

    for match in PRIMARY_KEY_RE.finditer(sql):
        full_name = f"{match.group('schema')}.{match.group('table')}"
        if full_name in tables:
            tables[full_name].primary_key = _split_columns(match.group("columns"))

    for match in FOREIGN_KEY_RE.finditer(sql):
        full_name = f"{match.group('schema')}.{match.group('table')}"
        if full_name not in tables:
            continue
        columns = ", ".join(_split_columns(match.group("columns")))
        ref = f"{match.group('ref_schema')}.{match.group('ref_table')}"
        ref_columns = ", ".join(_split_columns(match.group("ref_columns")))
        tables[full_name].foreign_keys.append(f"({columns}) -> {ref}({ref_columns})")

    return SchemaCatalog(tables)
