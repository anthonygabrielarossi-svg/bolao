"""Conexao centralizada com o banco de dados.

Usa PostgreSQL quando DATABASE_URL estiver configurada em Streamlit Secrets ou
variavel de ambiente. Para desenvolvimento local, cai para SQLite.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import streamlit as st
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError, NoSuchTableError, SQLAlchemyError


DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent.parent / "bolao_copa.db"


class DatabaseConfigurationError(RuntimeError):
    """Erro de configuracao do banco em ambiente hospedado."""


def is_streamlit_cloud() -> bool:
    return bool(os.getenv("STREAMLIT_SHARING") or os.getenv("STREAMLIT_CLOUD") or os.getenv("HOSTNAME"))


def get_database_url() -> str:
    """Retorna a URL do banco na ordem: Streamlit Secrets, env, SQLite local."""
    try:
        import streamlit as st

        if "DATABASE_URL" in st.secrets:
            secret_url = st.secrets["DATABASE_URL"]
            if secret_url:
                return str(secret_url)

        connections = st.secrets.get("connections", {})
        for connection_name in ("postgresql", "postgres", "neon", "supabase"):
            connection_config = connections.get(connection_name, {})
            if isinstance(connection_config, Mapping) and connection_config.get("url"):
                return str(connection_config["url"])
    except Exception:
        pass

    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    if is_streamlit_cloud():
        raise DatabaseConfigurationError("DATABASE_URL nao configurado no Streamlit Secrets.")

    sqlite_path = Path(os.getenv("DB_PATH") or DEFAULT_SQLITE_PATH)
    return f"sqlite:///{sqlite_path.as_posix()}"


def get_database_kind() -> str:
    url = get_database_url()
    if url.startswith("postgresql"):
        return "PostgreSQL/Supabase"
    if url.startswith("sqlite"):
        return "SQLite local"
    return "Desconhecido"


def is_sqlite_url(database_url: Optional[str] = None) -> bool:
    return (database_url or get_database_url()).startswith("sqlite")


def _postgres_connect_args(url: str) -> dict[str, Any]:
    """Ajustes seguros para PostgreSQL hospedado, mantendo localhost simples."""
    try:
        parsed_url = make_url(url)
    except Exception:
        return {}

    if not parsed_url.drivername.startswith("postgresql"):
        return {}

    query = dict(parsed_url.query)
    if "sslmode" in query:
        return {}

    host = (parsed_url.host or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return {}

    return {"sslmode": "require"}


@st.cache_resource(show_spinner=False)
def get_engine(database_url: Optional[str] = None) -> Engine:
    """Cria/reutiliza a engine SQLAlchemy."""
    url = database_url or get_database_url()
    if is_sqlite_url(url):
        connect_args = {"check_same_thread": False}
        return create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)
    return create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        connect_args=_postgres_connect_args(url),
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,
    )


class ResultProxy:
    """Resultado com a pequena API usada pelo projeto."""

    def __init__(self, result: Any, lastrowid: Optional[int] = None) -> None:
        self._result = result
        self.lastrowid = lastrowid
        self.rowcount = getattr(result, "rowcount", -1)

    def fetchone(self) -> Optional[Any]:
        return self._result.mappings().fetchone() if self._result.returns_rows else None

    def fetchall(self) -> list[Any]:
        if not self._result.returns_rows:
            return []
        return list(self._result.mappings().fetchall())


class DatabaseConnection:
    """Adaptador fino para aceitar as chamadas legadas com placeholders `?`."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.dialect = engine.dialect.name
        self._conn = engine.connect()
        self._tx = self._conn.begin()

    @property
    def is_sqlite(self) -> bool:
        return self.dialect == "sqlite"

    def execute(self, sql: str, params: Optional[Sequence[Any] | dict[str, Any]] = None) -> ResultProxy:
        statement, bound = self._prepare_sql(sql, params)
        result = self._conn.execute(text(statement), bound)
        lastrowid = self._extract_lastrowid(statement, result)
        return ResultProxy(result, lastrowid=lastrowid)

    def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any] | dict[str, Any]]) -> ResultProxy:
        prepared_params = list(seq_of_params)
        if not prepared_params:
            return ResultProxy(_EmptyResult())

        statement, first_bound = self._prepare_sql(sql, prepared_params[0])
        if isinstance(prepared_params[0], dict):
            bound = [dict(item) for item in prepared_params]  # type: ignore[arg-type]
        else:
            names = list(first_bound.keys())
            bound = [
                {name: value for name, value in zip(names, item)}
                for item in prepared_params  # type: ignore[arg-type]
            ]
        result = self._conn.execute(text(statement), bound)
        return ResultProxy(result)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def commit(self) -> None:
        if self._tx and self._tx.is_active:
            self._tx.commit()
        self._tx = self._conn.begin()

    def rollback(self) -> None:
        if self._tx and self._tx.is_active:
            self._tx.rollback()
        self._tx = self._conn.begin()

    def close(self) -> None:
        if self._tx and self._tx.is_active:
            self._tx.rollback()
        self._conn.close()

    def table_exists(self, table: str) -> bool:
        inspector = inspect(self._conn)
        if inspector.has_table(table):
            return True
        if not self.is_sqlite and table.lower() != table:
            return inspector.has_table(table.lower())
        return False

    def table_columns(self, table: str) -> set[str]:
        inspector = inspect(self._conn)
        try:
            columns = inspector.get_columns(table)
        except NoSuchTableError:
            columns = []
        if not columns and not self.is_sqlite and table.lower() != table:
            try:
                columns = inspector.get_columns(table.lower())
            except NoSuchTableError:
                columns = []
        return {column["name"] for column in columns}

    def __enter__(self) -> "DatabaseConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is None:
            if self._tx and self._tx.is_active:
                self._tx.commit()
        else:
            if self._tx and self._tx.is_active:
                self._tx.rollback()
        self._conn.close()

    def _prepare_sql(
        self,
        sql: str,
        params: Optional[Sequence[Any] | dict[str, Any]],
    ) -> tuple[str, dict[str, Any]]:
        sql = self._normalize_sql(sql)
        if params is None:
            return sql, {}
        if isinstance(params, dict):
            return sql, params

        names: list[str] = []

        def repl(_: re.Match[str]) -> str:
            name = f"p{len(names)}"
            names.append(name)
            return f":{name}"

        statement = re.sub(r"\?", repl, sql)
        return statement, {name: value for name, value in zip(names, params)}

    def _normalize_sql(self, sql: str) -> str:
        normalized = sql
        if not self.is_sqlite:
            normalized = normalized.replace("INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1))", "BOOLEAN NOT NULL DEFAULT FALSE")
            normalized = normalized.replace("INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0, 1))", "BOOLEAN NOT NULL DEFAULT FALSE")
            normalized = normalized.replace("INTEGER NOT NULL DEFAULT 0 CHECK (finalizado IN (0, 1))", "BOOLEAN NOT NULL DEFAULT FALSE")
            normalized = normalized.replace("revoked = 0", "revoked = FALSE")
            normalized = normalized.replace("revoked = 1", "revoked = TRUE")
            normalized = normalized.replace("is_admin = 1", "is_admin = TRUE")
            normalized = normalized.replace("finalizado = 1", "finalizado = TRUE")
        return normalized

    def _extract_lastrowid(self, statement: str, result: Any) -> Optional[int]:
        if result.returns_rows and "RETURNING" in statement.upper():
            row = result.fetchone()
            if row is not None and "id" in row._mapping:
                return int(row._mapping["id"])
        return getattr(result, "lastrowid", None)


class _EmptyResult:
    returns_rows = False
    rowcount = 0


def get_connection() -> DatabaseConnection:
    return DatabaseConnection(get_engine())


DatabaseError = SQLAlchemyError
DatabaseIntegrityError = IntegrityError
