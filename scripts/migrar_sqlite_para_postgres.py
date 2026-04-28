"""Migra dados do SQLite local para o PostgreSQL configurado em DATABASE_URL.

Uso:
    python scripts/migrar_sqlite_para_postgres.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import DB_PATH, init_db
from database.connection import get_connection, get_database_url, is_sqlite_url


TABLES = [
    "Usuarios",
    "Jogos",
    "Sessoes",
    "Palpites_Partidas",
    "Palpites_Especiais",
    "Classificacao_Grupos",
    "Resultados_Oficiais",
]

BOOLEAN_FIELDS = {"is_admin", "revoked", "finalizado"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migra o bolao do SQLite local para PostgreSQL.")
    parser.add_argument(
        "--sqlite-path",
        default=str(DB_PATH),
        help="Caminho do arquivo SQLite local. Padrao: bolao_copa.db.",
    )
    return parser


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _fetch_sqlite_rows(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]


def _converter_booleano_sqlite(value: Any) -> Any:
    if value in (0, "0"):
        return False
    if value in (1, "1"):
        return True
    return value


def converter_valores_para_postgres(row: dict[str, Any]) -> dict[str, Any]:
    novo = dict(row)
    for field in BOOLEAN_FIELDS:
        if field in novo:
            novo[field] = _converter_booleano_sqlite(novo[field])
    return novo


def _upsert_rows(table: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    with get_connection() as conn:
        target_columns = conn.table_columns(table)
        columns = [column for column in rows[0].keys() if column in target_columns]
        if "id" not in columns:
            raise RuntimeError(f"Tabela {table} sem coluna id para preservar registros.")

        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(columns)
        update_columns = [column for column in columns if column != "id"]
        update_sql = ", ".join(f"{column} = excluded.{column}" for column in update_columns)
        conflict_sql = f"DO UPDATE SET {update_sql}" if update_sql else "DO NOTHING"
        sql = f"""
            INSERT INTO {table} ({column_sql})
            VALUES ({placeholders})
            ON CONFLICT(id) {conflict_sql}
        """
        rows_convertidas = [converter_valores_para_postgres(row) for row in rows]
        conn.executemany(
            sql,
            [tuple(row.get(column) for column in columns) for row in rows_convertidas],
        )
        conn.commit()
    return len(rows)


def _sync_postgres_sequence(table: str) -> None:
    if table == "Resultados_Oficiais":
        return
    with get_connection() as conn:
        if conn.is_sqlite:
            return
        conn.execute(
            """
            SELECT setval(
                pg_get_serial_sequence(?, 'id'),
                COALESCE((SELECT MAX(id) FROM {table}), 1),
                (SELECT MAX(id) FROM {table}) IS NOT NULL
            )
            """.format(table=table),
            (table.lower(),),
        )
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sqlite_path = Path(args.sqlite_path)
    database_url = get_database_url()

    if is_sqlite_url(database_url):
        print("DATABASE_URL nao aponta para PostgreSQL. Configure a variavel antes de migrar.")
        return 1
    if not sqlite_path.exists():
        print(f"SQLite nao encontrado: {sqlite_path}")
        return 1
    if not os.getenv("DATABASE_URL"):
        print("Aviso: DATABASE_URL nao esta no ambiente; tentando usar Streamlit Secrets.")

    init_db()
    resumo: dict[str, int] = {}

    with sqlite3.connect(str(sqlite_path)) as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        for table in TABLES:
            if not _sqlite_columns(sqlite_conn, table):
                resumo[table] = 0
                continue
            rows = _fetch_sqlite_rows(sqlite_conn, table)
            resumo[table] = _upsert_rows(table, rows)
            _sync_postgres_sequence(table)

    print("Migracao concluida:")
    for table in TABLES:
        print(f"- {table}: {resumo.get(table, 0)} registros copiados/atualizados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
