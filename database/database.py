"""Camada de persistencia do bolao da Copa do Mundo.

Este modulo concentra conexao, migracao de schema, autenticao segura e CRUD
principal do projeto.
"""

from __future__ import annotations

import re
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import bcrypt
import streamlit as st

from settings import SESSION_IDLE_TIMEOUT_MINUTES
from utils.datetime_utils import bloquear_palpite_para_jogo, parse_iso_datetime
from utils.team_assets import get_team_logo_url

from .connection import (
    DEFAULT_SQLITE_PATH,
    DatabaseConfigurationError,
    DatabaseError,
    DatabaseConnection,
    DatabaseIntegrityError,
    get_database_kind,
    get_connection,
    is_streamlit_cloud,
)
from .models import (
    ClassificacaoGrupo,
    Jogo,
    PalpiteEspecial,
    PalpitePartida,
    PontuacaoUsuario,
    ResultadoOficial,
    Usuario,
)


DB_PATH = Path(os.getenv("DB_PATH") or str(DEFAULT_SQLITE_PATH))
COMPETICAO_PADRAO = "Copa do Mundo"
FASE_NAO_MAPEADA = "Não mapeada"
FASES_VALIDAS_COPA = (
    "Fase de Grupos",
    "16-avos de Final",
    "Oitavas de Final",
    "Quartas de Final",
    "Semifinal",
    "Disputa de 3\u00ba Lugar",
    "Final",
    FASE_NAO_MAPEADA,
)
GRUPOS_VALIDOS_COPA = tuple(f"Grupo {chr(ord('A') + indice)}" for indice in range(12))
_GRUPOS_VALIDOS_COPA_NORMALIZADOS = {grupo.upper(): grupo for grupo in GRUPOS_VALIDOS_COPA}
_PLACEHOLDER_BRACKET_TOKEN_RE = re.compile(r"^(?:[WL]\d+|\d+[A-Z]|3[A-L])(?:/(?:[WL]\d+|\d+[A-Z]|3[A-L]))*$", re.IGNORECASE)


def hash_password(password: str) -> str:
    """Gera um hash bcrypt para a senha informada."""
    if password is None:
        raise ValueError("Senha nao pode ser nula.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _is_bcrypt_hash(hashed: str) -> bool:
    return isinstance(hashed, str) and hashed.startswith("$2")


def _legacy_sha256_matches(password: str, hashed: str) -> bool:
    import hashlib

    return hashlib.sha256(password.encode("utf-8")).hexdigest() == hashed


def verify_password(password: str, hashed: str) -> bool:
    """Valida a senha suportando migração segura de SHA-256 para bcrypt."""
    if not password or not hashed:
        return False

    if _is_bcrypt_hash(hashed):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False

    return _legacy_sha256_matches(password, hashed)


def _row_to_usuario(row: object) -> Usuario:
    return Usuario(
        id=row["id"],
        nome=row["nome"],
        senha=row["senha"],
        pontuacao_total=row["pontuacao_total"],
        is_admin=bool(_row_get(row, "is_admin", default=0)),
    )


def _row_get(row: object, *keys: str, default: Optional[object] = None) -> Optional[object]:
    available = set(row.keys())
    for key in keys:
        if key in available:
            value = row[key]
            if value is not None:
                return value
    return default


def _row_to_jogo(row: object) -> Jogo:
    time_casa = _row_get(row, "time_casa", "time_a", default="")
    time_fora = _row_get(row, "time_fora", "time_b", default="")
    gols_casa = _row_get(row, "gols_casa", "placar_a")
    gols_fora = _row_get(row, "gols_fora", "placar_b")
    return Jogo(
        id=row["id"],
        time_a=str(time_casa or ""),
        time_b=str(time_fora or ""),
        placar_a=gols_casa if gols_casa is None else int(gols_casa),
        placar_b=gols_fora if gols_fora is None else int(gols_fora),
        finalizado=bool(_row_get(row, "finalizado", default=0)),
        fase=str(_row_get(row, "fase", default=FASE_NAO_MAPEADA) or FASE_NAO_MAPEADA),
        grupo=_row_get(row, "grupo"),
        data_jogo=_row_get(row, "data_jogo"),
        status=str(_row_get(row, "status", default="agendado") or "agendado"),
        proximo_jogo_id=_row_get(row, "proximo_jogo_id"),
        api_id=_row_get(row, "api_id"),
        round_number=_row_get(row, "round_number"),
        is_placeholder_bracket=_is_placeholder_bracket(str(time_casa or ""), str(time_fora or "")),
        home_team_id=_row_get(row, "home_team_id"),
        away_team_id=_row_get(row, "away_team_id"),
        home_team_logo_url=_row_get(row, "home_team_logo_url"),
        away_team_logo_url=_row_get(row, "away_team_logo_url"),
        estadio=_row_get(row, "estadio"),
        competicao=str(_row_get(row, "competicao", default=COMPETICAO_PADRAO) or COMPETICAO_PADRAO),
    )


def _row_to_palpite_partida(row: object) -> PalpitePartida:
    return PalpitePartida(
        id=row["id"],
        user_id=row["user_id"],
        match_id=row["match_id"],
        palpite_a=row["palpite_a"],
        palpite_b=row["palpite_b"],
    )


def _row_to_palpite_especial(row: object) -> PalpiteEspecial:
    return PalpiteEspecial(
        id=row["id"],
        user_id=row["user_id"],
        campeao=row["campeao"] or "",
        vice=row["vice"] or "",
        artilheiro=row["artilheiro"] or "",
        melhor_jogador=row["melhor_jogador"] or "",
        primeiro_grupo_a=row["primeiro_grupo_a"] or "",
        segundo_grupo_a=row["segundo_grupo_a"] or "",
    )


def _row_to_classificacao(row: object) -> ClassificacaoGrupo:
    return ClassificacaoGrupo(
        id=row["id"],
        grupo=row["grupo"],
        time_nome=row["time_nome"],
        posicao=row["posicao"],
        pontos=row["pontos"],
        jogos=row["jogos"],
        vitorias=row["vitorias"],
        empates=row["empates"],
        derrotas=row["derrotas"],
        gols_pro=row["gols_pro"],
        gols_contra=row["gols_contra"],
        saldo_gols=row["saldo_gols"],
    )


def _row_to_resultado_oficial(row: object) -> ResultadoOficial:
    return ResultadoOficial(
        id=row["id"],
        campeao=row["campeao"] or "",
        vice=row["vice"] or "",
        artilheiro=row["artilheiro"] or "",
        melhor_jogador=row["melhor_jogador"] or "",
        primeiro_grupo_a=row["primeiro_grupo_a"] or "",
        segundo_grupo_a=row["segundo_grupo_a"] or "",
    )


def _row_to_sessao(row: object) -> Dict[str, Optional[object]]:
    return {
        "id": row["id"],
        "session_token": row["session_token"],
        "user_id": row["user_id"],
        "created_at": row["created_at"],
        "last_activity_at": row["last_activity_at"],
        "expires_at": row["expires_at"],
        "revoked": bool(row["revoked"]),
    }


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _sessao_expirada_row(row: object, agora: Optional[datetime] = None) -> bool:
    expires_at = parse_iso_datetime(_row_get(row, "expires_at"))
    if expires_at is None:
        return True

    referencia = agora or _agora_utc()
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=timezone.utc)
    else:
        referencia = referencia.astimezone(timezone.utc)

    return referencia >= expires_at.astimezone(timezone.utc)


def _ensure_column(conn: DatabaseConnection, table: str, column: str, column_sql: str) -> None:
    if not conn.table_exists(table):
        return

    existing = conn.table_columns(table)
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_sql}")


def _clear_data_cache() -> None:
    try:
        st.cache_data.clear()
    except Exception:
        pass


def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _is_placeholder_bracket_text(value: Optional[str]) -> bool:
    token = "".join(str(value or "").split()).upper()
    return bool(token and _PLACEHOLDER_BRACKET_TOKEN_RE.fullmatch(token))


def _is_placeholder_bracket(time_a: Optional[str], time_b: Optional[str]) -> bool:
    return _is_placeholder_bracket_text(time_a) or _is_placeholder_bracket_text(time_b)


def validar_fase_copa(fase: Optional[str]) -> str:
    """Normaliza a fase para os valores oficiais da Copa do Mundo."""
    fase_normalizada = _normalize_text(fase)
    mapa = {
        "nao mapeada": FASE_NAO_MAPEADA,
        "não mapeada": FASE_NAO_MAPEADA,
        "fase nao mapeada": FASE_NAO_MAPEADA,
        "fase não mapeada": FASE_NAO_MAPEADA,
        "fase de grupos": "Fase de Grupos",
        "group stage": "Fase de Grupos",
        "groups": "Fase de Grupos",
        "16 avos de final": "16-avos de Final",
        "16-avos de final": "16-avos de Final",
        "round of 32": "16-avos de Final",
        "round of thirty two": "16-avos de Final",
        "32nd": "16-avos de Final",
        "round of 16": "Oitavas de Final",
        "oitavas": "Oitavas de Final",
        "oitavas de final": "Oitavas de Final",
        "quarterfinal": "Quartas de Final",
        "quarters": "Quartas de Final",
        "quartas": "Quartas de Final",
        "quartas de final": "Quartas de Final",
        "semifinal": "Semifinal",
        "semi-final": "Semifinal",
        "semi final": "Semifinal",
        "third place": "Disputa de 3\u00ba Lugar",
        "third-place": "Disputa de 3\u00ba Lugar",
        "3rd place": "Disputa de 3\u00ba Lugar",
        "disputa de 3 lugar": "Disputa de 3\u00ba Lugar",
        "disputa de 3\u00ba lugar": "Disputa de 3\u00ba Lugar",
        "final": "Final",
    }
    if fase_normalizada in mapa:
        return mapa[fase_normalizada]

    for fase_valida in FASES_VALIDAS_COPA:
        if _normalize_text(fase_valida) == fase_normalizada:
            return fase_valida

    return FASE_NAO_MAPEADA


def validar_grupo_copa(grupo: Optional[str]) -> Optional[str]:
    """Normaliza o grupo para Grupo A-L quando aplicavel."""
    if not grupo:
        return None
    grupo_normalizado = _normalize_text(grupo).upper()
    if grupo_normalizado in _GRUPOS_VALIDOS_COPA_NORMALIZADOS:
        return _GRUPOS_VALIDOS_COPA_NORMALIZADOS[grupo_normalizado]

    correspondencia = re.search(r"(?:GRUPO|GROUP)\s*([A-L])\b", grupo_normalizado)
    if correspondencia:
        return f"Grupo {correspondencia.group(1)}"

    correspondencia = re.search(r"\b([A-L])\b", grupo_normalizado)
    if correspondencia:
        return f"Grupo {correspondencia.group(1)}"

    return None


def validar_competicao_copa(_: Optional[str] = None) -> str:
    """A competicao do sistema e fixa na Copa do Mundo."""
    return COMPETICAO_PADRAO


def _existing_game_id(conn: DatabaseConnection, jogo: Jogo) -> Optional[int]:
    if jogo.api_id is not None:
        row = conn.execute(
            "SELECT id FROM Jogos WHERE api_id = ?",
            (int(jogo.api_id),),
        ).fetchone()
        if row:
            return int(row["id"])

    row = conn.execute(
        """
        SELECT id
        FROM Jogos
        WHERE (
            (LOWER(time_a) = ? AND LOWER(time_b) = ?)
            OR
            (LOWER(time_a) = ? AND LOWER(time_b) = ?)
        )
          AND COALESCE(LOWER(fase), '') = ?
          AND COALESCE(LOWER(competicao), '') = ?
        LIMIT 1
        """,
        (
            _normalize_text(jogo.time_a),
            _normalize_text(jogo.time_b),
            _normalize_text(jogo.time_b),
            _normalize_text(jogo.time_a),
            _normalize_text(validar_fase_copa(jogo.fase)),
            _normalize_text(validar_competicao_copa(jogo.competicao)),
        ),
    ).fetchone()
    if row:
        return int(row["id"])
    return None


def _existing_jogo_row(conn: DatabaseConnection, jogo_id: int) -> Optional[object]:
    return conn.execute(
        """
        SELECT id, api_id, competicao, time_a, time_b, placar_a, placar_b, finalizado,
               fase, grupo, data_jogo, status, proximo_jogo_id, round_number,
               time_casa, time_fora, home_team_id, away_team_id,
               home_team_logo_url, away_team_logo_url,
               gols_casa, gols_fora, estadio
        FROM Jogos
        WHERE id = ?
        """,
        (int(jogo_id),),
    ).fetchone()


def init_db() -> None:
    """Cria tabelas e executa migracoes leves de schema."""
    with get_connection() as conn:
        if conn.is_sqlite:
            schema_sql = """
            CREATE TABLE IF NOT EXISTS Usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                senha TEXT NOT NULL,
                pontuacao_total INTEGER NOT NULL DEFAULT 0,
                is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS Sessoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_token TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                last_activity_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0, 1)),
                FOREIGN KEY (user_id) REFERENCES Usuarios (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Jogos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_id INTEGER,
                competicao TEXT NOT NULL DEFAULT 'Copa do Mundo',
                time_a TEXT NOT NULL,
                time_b TEXT NOT NULL,
                placar_a INTEGER,
                placar_b INTEGER,
                finalizado INTEGER NOT NULL DEFAULT 0 CHECK (finalizado IN (0, 1)),
                fase TEXT NOT NULL DEFAULT 'Fase de Grupos',
                grupo TEXT,
                data_jogo TEXT,
                status TEXT NOT NULL DEFAULT 'agendado',
                proximo_jogo_id INTEGER,
                estadio TEXT,
                time_casa TEXT,
                time_fora TEXT,
                home_team_id INTEGER,
                away_team_id INTEGER,
                home_team_logo_url TEXT,
                away_team_logo_url TEXT,
                gols_casa INTEGER,
                gols_fora INTEGER
            );

            CREATE TABLE IF NOT EXISTS Palpites_Partidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                palpite_a INTEGER NOT NULL,
                palpite_b INTEGER NOT NULL,
                UNIQUE (user_id, match_id),
                FOREIGN KEY (user_id) REFERENCES Usuarios (id) ON DELETE CASCADE,
                FOREIGN KEY (match_id) REFERENCES Jogos (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Palpites_Especiais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                campeao TEXT,
                vice TEXT,
                artilheiro TEXT,
                melhor_jogador TEXT,
                primeiro_grupo_a TEXT,
                segundo_grupo_a TEXT,
                FOREIGN KEY (user_id) REFERENCES Usuarios (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Classificacao_Grupos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grupo TEXT NOT NULL,
                time_nome TEXT NOT NULL,
                posicao INTEGER NOT NULL DEFAULT 0,
                pontos INTEGER NOT NULL DEFAULT 0,
                jogos INTEGER NOT NULL DEFAULT 0,
                vitorias INTEGER NOT NULL DEFAULT 0,
                empates INTEGER NOT NULL DEFAULT 0,
                derrotas INTEGER NOT NULL DEFAULT 0,
                gols_pro INTEGER NOT NULL DEFAULT 0,
                gols_contra INTEGER NOT NULL DEFAULT 0,
                saldo_gols INTEGER NOT NULL DEFAULT 0,
                atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (grupo, time_nome)
            );

            CREATE TABLE IF NOT EXISTS Resultados_Oficiais (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                campeao TEXT,
                vice TEXT,
                artilheiro TEXT,
                melhor_jogador TEXT,
                primeiro_grupo_a TEXT,
                segundo_grupo_a TEXT,
                atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        else:
            schema_sql = """
            CREATE TABLE IF NOT EXISTS Usuarios (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL UNIQUE,
                senha TEXT NOT NULL,
                pontuacao_total INTEGER NOT NULL DEFAULT 0,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS Sessoes (
                id SERIAL PRIMARY KEY,
                session_token TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                last_activity_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked BOOLEAN NOT NULL DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES Usuarios (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Jogos (
                id SERIAL PRIMARY KEY,
                api_id INTEGER,
                competicao TEXT NOT NULL DEFAULT 'Copa do Mundo',
                time_a TEXT NOT NULL,
                time_b TEXT NOT NULL,
                placar_a INTEGER,
                placar_b INTEGER,
                finalizado BOOLEAN NOT NULL DEFAULT FALSE,
                fase TEXT NOT NULL DEFAULT 'Fase de Grupos',
                grupo TEXT,
                data_jogo TEXT,
                status TEXT NOT NULL DEFAULT 'agendado',
                proximo_jogo_id INTEGER,
                estadio TEXT,
                time_casa TEXT,
                time_fora TEXT,
                home_team_id INTEGER,
                away_team_id INTEGER,
                home_team_logo_url TEXT,
                away_team_logo_url TEXT,
                gols_casa INTEGER,
                gols_fora INTEGER,
                round_number INTEGER
            );

            CREATE TABLE IF NOT EXISTS Palpites_Partidas (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                palpite_a INTEGER NOT NULL,
                palpite_b INTEGER NOT NULL,
                UNIQUE (user_id, match_id),
                FOREIGN KEY (user_id) REFERENCES Usuarios (id) ON DELETE CASCADE,
                FOREIGN KEY (match_id) REFERENCES Jogos (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Palpites_Especiais (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE,
                campeao TEXT,
                vice TEXT,
                artilheiro TEXT,
                melhor_jogador TEXT,
                primeiro_grupo_a TEXT,
                segundo_grupo_a TEXT,
                FOREIGN KEY (user_id) REFERENCES Usuarios (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Classificacao_Grupos (
                id SERIAL PRIMARY KEY,
                grupo TEXT NOT NULL,
                time_nome TEXT NOT NULL,
                posicao INTEGER NOT NULL DEFAULT 0,
                pontos INTEGER NOT NULL DEFAULT 0,
                jogos INTEGER NOT NULL DEFAULT 0,
                vitorias INTEGER NOT NULL DEFAULT 0,
                empates INTEGER NOT NULL DEFAULT 0,
                derrotas INTEGER NOT NULL DEFAULT 0,
                gols_pro INTEGER NOT NULL DEFAULT 0,
                gols_contra INTEGER NOT NULL DEFAULT 0,
                saldo_gols INTEGER NOT NULL DEFAULT 0,
                atualizado_em TEXT NOT NULL,
                UNIQUE (grupo, time_nome)
            );

            CREATE TABLE IF NOT EXISTS Resultados_Oficiais (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                campeao TEXT,
                vice TEXT,
                artilheiro TEXT,
                melhor_jogador TEXT,
                primeiro_grupo_a TEXT,
                segundo_grupo_a TEXT,
                atualizado_em TEXT NOT NULL
            );
            """

        conn.executescript(schema_sql)

        # Migra a tabela Jogos para as colunas novas sem quebrar a base antiga.
        _ensure_column(conn, "Usuarios", "pontuacao_total", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(
            conn,
            "Usuarios",
            "is_admin",
            "INTEGER NOT NULL DEFAULT 0" if conn.is_sqlite else "BOOLEAN NOT NULL DEFAULT FALSE",
        )
        _ensure_column(conn, "Sessoes", "created_at", "TEXT")
        _ensure_column(conn, "Sessoes", "last_activity_at", "TEXT")
        _ensure_column(conn, "Sessoes", "expires_at", "TEXT")
        _ensure_column(
            conn,
            "Sessoes",
            "revoked",
            "INTEGER NOT NULL DEFAULT 0" if conn.is_sqlite else "BOOLEAN NOT NULL DEFAULT FALSE",
        )
        _ensure_column(conn, "Jogos", "api_id", "INTEGER")
        _ensure_column(conn, "Jogos", "competicao", "TEXT NOT NULL DEFAULT 'Copa do Mundo'")
        _ensure_column(conn, "Jogos", "fase", "TEXT NOT NULL DEFAULT 'Fase de Grupos'")
        _ensure_column(conn, "Jogos", "grupo", "TEXT")
        _ensure_column(conn, "Jogos", "data_jogo", "TEXT")
        _ensure_column(conn, "Jogos", "status", "TEXT NOT NULL DEFAULT 'agendado'")
        _ensure_column(conn, "Jogos", "proximo_jogo_id", "INTEGER")
        _ensure_column(conn, "Jogos", "round_number", "INTEGER")
        _ensure_column(conn, "Jogos", "time_casa", "TEXT")
        _ensure_column(conn, "Jogos", "time_fora", "TEXT")
        _ensure_column(conn, "Jogos", "home_team_id", "INTEGER")
        _ensure_column(conn, "Jogos", "away_team_id", "INTEGER")
        _ensure_column(conn, "Jogos", "home_team_logo_url", "TEXT")
        _ensure_column(conn, "Jogos", "away_team_logo_url", "TEXT")
        _ensure_column(conn, "Jogos", "gols_casa", "INTEGER")
        _ensure_column(conn, "Jogos", "gols_fora", "INTEGER")
        _ensure_column(conn, "Jogos", "estadio", "TEXT")

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_jogos_api_id ON Jogos(api_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jogos_match_lookup ON Jogos(competicao, fase, grupo, data_jogo, time_a, time_b)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jogos_fase ON Jogos(fase)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jogos_grupo ON Jogos(grupo)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jogos_data_jogo ON Jogos(data_jogo)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_palpites_usuario_jogo ON Palpites_Partidas(user_id, match_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_palpites_especiais_usuario ON Palpites_Especiais(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_pontuacao ON Usuarios(pontuacao_total)")

        # Preenche os novos campos com os valores legados quando existirem.
        is_admin_default = "0" if conn.is_sqlite else "FALSE"
        conn.execute(
            f"""
            UPDATE Usuarios
            SET is_admin = COALESCE(is_admin, {is_admin_default}),
                pontuacao_total = COALESCE(pontuacao_total, 0)
            """
        )

        conn.execute(
            """
            UPDATE Jogos
            SET competicao = COALESCE(NULLIF(TRIM(competicao), ''), 'Copa do Mundo'),
                fase = COALESCE(NULLIF(TRIM(fase), ''), 'Fase de Grupos'),
                grupo = CASE
                    WHEN TRIM(COALESCE(grupo, '')) = '' THEN NULL
                    ELSE UPPER(TRIM(grupo))
                END,
                time_casa = COALESCE(time_casa, time_a),
                time_fora = COALESCE(time_fora, time_b),
                home_team_logo_url = CASE
                    WHEN TRIM(COALESCE(home_team_logo_url, '')) = '' AND home_team_id IS NOT NULL
                        THEN 'https://sports.bzzoiro.com/img/team/' || home_team_id || '/'
                    ELSE home_team_logo_url
                END,
                away_team_logo_url = CASE
                    WHEN TRIM(COALESCE(away_team_logo_url, '')) = '' AND away_team_id IS NOT NULL
                        THEN 'https://sports.bzzoiro.com/img/team/' || away_team_id || '/'
                    ELSE away_team_logo_url
                END,
                gols_casa = COALESCE(gols_casa, placar_a),
                gols_fora = COALESCE(gols_fora, placar_b)
            """
        )

        conn.execute("INSERT INTO Resultados_Oficiais (id, atualizado_em) VALUES (1, ?) ON CONFLICT(id) DO NOTHING", (_agora_utc().isoformat(),))

        conn.commit()


def cadastrar_usuario(nome: str, senha: str, is_admin: bool = False) -> Tuple[bool, str]:
    """Cadastra um novo usuario."""
    nome = nome.strip()
    if not nome or not senha:
        return False, "Informe nome e senha."

    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO Usuarios (nome, senha, is_admin) VALUES (?, ?, ?)",
                (nome, hash_password(senha), bool(is_admin)),
            )
            conn.commit()
        _clear_data_cache()
        return True, "Usuario cadastrado com sucesso."
    except DatabaseIntegrityError:
        return False, "Esse nome de usuario ja existe."


def autenticar_usuario(nome: str, senha: str) -> Optional[Usuario]:
    """Autentica um usuario pelo nome e senha."""
    nome = nome.strip()
    if not nome or not senha:
        return None

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, nome, senha, pontuacao_total, is_admin
            FROM Usuarios
            WHERE nome = ?
            """,
            (nome,),
        ).fetchone()

    if row is None:
        return None

    if not verify_password(senha, row["senha"]):
        return None

    if not _is_bcrypt_hash(row["senha"]):
        with get_connection() as conn:
            conn.execute(
                "UPDATE Usuarios SET senha = ? WHERE id = ?",
                (hash_password(senha), int(row["id"])),
            )
            conn.commit()
        _clear_data_cache()
        return buscar_usuario_por_id(int(row["id"]))

    return _row_to_usuario(row)


def buscar_usuario_por_id(user_id: int) -> Optional[Usuario]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, nome, senha, pontuacao_total, is_admin
            FROM Usuarios
            WHERE id = ?
            """,
            (int(user_id),),
        ).fetchone()
    return _row_to_usuario(row) if row else None


def criar_sessao_usuario(user_id: int, session_token: Optional[str] = None) -> Dict[str, object]:
    """Cria uma sessao autenticada com renovacao por atividade."""
    token = (session_token or uuid.uuid4().hex).strip()
    if not token:
        token = uuid.uuid4().hex

    agora = _agora_utc()
    expires_at = agora + timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES)
    created_at = agora.isoformat()
    expires_at_text = expires_at.isoformat()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO Sessoes (
                session_token, user_id, created_at, last_activity_at, expires_at, revoked
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_token)
            DO UPDATE SET
                user_id = excluded.user_id,
                created_at = excluded.created_at,
                last_activity_at = excluded.last_activity_at,
                expires_at = excluded.expires_at,
                revoked = 0
            """,
            (
                token,
                int(user_id),
                created_at,
                created_at,
                expires_at_text,
                False,
            ),
        )
        conn.commit()

    return {
        "session_token": token,
        "user_id": int(user_id),
        "created_at": created_at,
        "last_activity_at": created_at,
        "expires_at": expires_at_text,
        "revoked": False,
    }


def buscar_sessao_por_token(session_token: Optional[str]) -> Optional[Dict[str, object]]:
    """Busca uma sessao pelo token persistido no cookie."""
    token = str(session_token or "").strip()
    if not token:
        return None

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, session_token, user_id, created_at, last_activity_at, expires_at, revoked
            FROM Sessoes
            WHERE session_token = ?
            """,
            (token,),
        ).fetchone()

    return _row_to_sessao(row) if row else None


def renovar_sessao_por_atividade(session_token: Optional[str]) -> Optional[Dict[str, object]]:
    """Renova o vencimento da sessao se ela ainda estiver ativa."""
    sessao = buscar_sessao_por_token(session_token)
    if sessao is None:
        return None
    if sessao.get("revoked"):
        return None

    row = None
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, session_token, user_id, created_at, last_activity_at, expires_at, revoked
            FROM Sessoes
            WHERE session_token = ?
            """,
            (str(session_token or "").strip(),),
        ).fetchone()

        if row is None or row["revoked"]:
            return None
        if _sessao_expirada_row(row):
            return None

        agora = _agora_utc()
        expires_at = agora + timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES)
        conn.execute(
            """
            UPDATE Sessoes
            SET last_activity_at = ?, expires_at = ?
            WHERE session_token = ? AND revoked = 0
            """,
            (agora.isoformat(), expires_at.isoformat(), str(session_token or "").strip()),
        )
        conn.commit()

    return {
        "id": row["id"],
        "session_token": row["session_token"],
        "user_id": row["user_id"],
        "created_at": row["created_at"],
        "last_activity_at": agora.isoformat(),
        "expires_at": expires_at.isoformat(),
        "revoked": False,
    }


def revogar_sessao(session_token: Optional[str]) -> bool:
    """Revoga a sessao persistida no banco."""
    token = str(session_token or "").strip()
    if not token:
        return False

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE Sessoes
            SET revoked = 1
            WHERE session_token = ?
            """,
            (token,),
        )
        conn.commit()
    return cursor.rowcount > 0


def usuario_eh_admin(user_id: Optional[int]) -> bool:
    if user_id is None:
        return False

    usuario = buscar_usuario_por_id(int(user_id))
    return bool(usuario and usuario.is_admin)


def promover_usuario_para_admin(user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE Usuarios SET is_admin = 1 WHERE id = ?",
            (int(user_id),),
        )
        conn.commit()
    alterou = cursor.rowcount > 0
    if alterou:
        _clear_data_cache()
    return alterou


@st.cache_data(ttl=60, show_spinner=False)
def listar_usuarios() -> List[Usuario]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, nome, senha, pontuacao_total, is_admin FROM Usuarios ORDER BY nome ASC"
        ).fetchall()
    return [_row_to_usuario(row) for row in rows]


@st.cache_data(ttl=60, show_spinner=False)
def listar_usuarios_ranking() -> List[Usuario]:
    """Retorna os usuarios ordenados pela pontuacao total."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, nome, senha, pontuacao_total, is_admin
            FROM Usuarios
            ORDER BY pontuacao_total DESC, nome ASC
            """
        ).fetchall()
    return [_row_to_usuario(row) for row in rows]


def atualizar_pontuacao_usuario(user_id: int, pontuacao_total: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE Usuarios SET pontuacao_total = ? WHERE id = ?",
            (int(pontuacao_total), int(user_id)),
        )
        conn.commit()
    _clear_data_cache()


@st.cache_data(ttl=60, show_spinner=False)
def listar_jogos() -> List[Jogo]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, api_id, competicao, time_a, time_b, placar_a, placar_b, finalizado,
                   fase, grupo, data_jogo, status, proximo_jogo_id, round_number,
                   time_casa, time_fora, home_team_id, away_team_id,
                   home_team_logo_url, away_team_logo_url, gols_casa, gols_fora, estadio
            FROM Jogos
            ORDER BY
                CASE fase
                    WHEN 'Fase de Grupos' THEN 0
                    WHEN '16-avos de Final' THEN 1
                    WHEN 'Oitavas de Final' THEN 2
                    WHEN 'Quartas de Final' THEN 3
                    WHEN 'Semifinal' THEN 4
                    WHEN 'Disputa de 3\u00ba Lugar' THEN 5
                    WHEN 'Final' THEN 6
                    WHEN 'Não mapeada' THEN 7
                    ELSE 99
                END,
                COALESCE(grupo, ''),
                CASE WHEN data_jogo IS NULL THEN 1 ELSE 0 END,
                data_jogo,
                id
            """
        ).fetchall()
    return [_row_to_jogo(row) for row in rows]


def listar_jogos_por_fase(fase: Optional[str] = None) -> List[Jogo]:
    jogos = [jogo for jogo in listar_jogos() if _normalize_text(jogo.competicao) == _normalize_text(COMPETICAO_PADRAO)]
    if not fase:
        return jogos
    fase_normalizada = _normalize_text(validar_fase_copa(fase))
    return [jogo for jogo in jogos if _normalize_text(jogo.fase) == fase_normalizada]


def listar_jogo_por_id(jogo_id: int) -> Optional[Jogo]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, api_id, competicao, time_a, time_b, placar_a, placar_b, finalizado,
                   fase, grupo, data_jogo, status, proximo_jogo_id, round_number,
                   time_casa, time_fora, home_team_id, away_team_id,
                   home_team_logo_url, away_team_logo_url, gols_casa, gols_fora, estadio
            FROM Jogos
            WHERE id = ?
            """,
            (int(jogo_id),),
        ).fetchone()
    return _row_to_jogo(row) if row else None


def buscar_jogo_por_api_id(api_id: int) -> Optional[Jogo]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, api_id, competicao, time_a, time_b, placar_a, placar_b, finalizado,
                   fase, grupo, data_jogo, status, proximo_jogo_id, round_number,
                   time_casa, time_fora, home_team_id, away_team_id,
                   home_team_logo_url, away_team_logo_url, gols_casa, gols_fora, estadio
            FROM Jogos
            WHERE api_id = ?
            """,
            (int(api_id),),
        ).fetchone()
    return _row_to_jogo(row) if row else None


def salvar_ou_atualizar_jogo(jogo: Jogo, connection: Optional[DatabaseConnection] = None) -> int:
    """Insere ou atualiza um jogo de forma consistente."""
    conn = connection or get_connection()
    owns_connection = connection is None
    try:
        jogo_id = jogo.id or _existing_game_id(conn, jogo)
        existing_row = _existing_jogo_row(conn, jogo_id) if jogo_id else None
        existing = dict(existing_row) if existing_row else {}
        from_api = jogo.api_id is not None

        def _merge_text(value: Optional[str], existing_key: str, fallback: str = "") -> str:
            if value is None:
                return str(existing.get(existing_key, fallback) or fallback)
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return str(existing.get(existing_key, fallback) or fallback)
                return value
            return str(value)

        time_a = _merge_text(jogo.time_a, "time_a")
        time_b = _merge_text(jogo.time_b, "time_b")
        time_casa = _merge_text(jogo.time_casa or time_a, "time_casa", time_a)
        time_fora = _merge_text(jogo.time_fora or time_b, "time_fora", time_b)
        home_team_id = jogo.home_team_id if jogo.home_team_id is not None else existing.get("home_team_id")
        away_team_id = jogo.away_team_id if jogo.away_team_id is not None else existing.get("away_team_id")
        home_team_logo_url = _merge_text(
            getattr(jogo, "home_team_logo_url", None) or get_team_logo_url(home_team_id),
            "home_team_logo_url",
        )
        away_team_logo_url = _merge_text(
            getattr(jogo, "away_team_logo_url", None) or get_team_logo_url(away_team_id),
            "away_team_logo_url",
        )
        placar_a = jogo.placar_a if jogo.placar_a is not None else existing.get("placar_a")
        placar_b = jogo.placar_b if jogo.placar_b is not None else existing.get("placar_b")
        gols_casa = jogo.gols_casa if jogo.gols_casa is not None else placar_a
        gols_fora = jogo.gols_fora if jogo.gols_fora is not None else placar_b
        estadio = _merge_text(getattr(jogo, "estadio", None), "estadio")
        competicao = validar_competicao_copa(jogo.competicao)
        fase = validar_fase_copa(jogo.fase if from_api else (jogo.fase or existing.get("fase")))
        grupo = validar_grupo_copa(jogo.grupo)
        if grupo is None:
            grupo = validar_grupo_copa(existing.get("grupo"))
        status = _merge_text(jogo.status, "status", "agendado")
        finalizado = bool(jogo.finalizado)
        api_id = jogo.api_id if jogo.api_id is not None else existing.get("api_id")
        round_number = jogo.round_number if jogo.round_number is not None else existing.get("round_number")
        data_jogo = jogo.data_jogo or existing.get("data_jogo")
        proximo_jogo_id = jogo.proximo_jogo_id if jogo.proximo_jogo_id is not None else existing.get("proximo_jogo_id")
        params = (
            api_id,
            competicao,
            time_a,
            time_b,
            placar_a,
            placar_b,
            finalizado,
            fase,
            grupo,
            data_jogo,
            status,
            proximo_jogo_id,
            round_number,
            time_casa,
            time_fora,
            home_team_id,
            away_team_id,
            home_team_logo_url,
            away_team_logo_url,
            gols_casa,
            gols_fora,
            estadio,
        )
        if jogo_id:
            conn.execute(
                """
                UPDATE Jogos
                SET api_id = ?, competicao = ?, time_a = ?, time_b = ?, placar_a = ?, placar_b = ?,
                    finalizado = ?, fase = ?, grupo = ?, data_jogo = ?,
                    status = ?, proximo_jogo_id = ?, round_number = ?,
                    time_casa = ?, time_fora = ?, home_team_id = ?, away_team_id = ?,
                    home_team_logo_url = ?, away_team_logo_url = ?, gols_casa = ?, gols_fora = ?, estadio = ?
                WHERE id = ?
                """,
                params + (int(jogo_id),),
            )
            resultado = int(jogo_id)
        else:
            cursor = conn.execute(
                """
                INSERT INTO Jogos (
                    api_id, competicao, time_a, time_b, placar_a, placar_b, finalizado,
                    fase, grupo, data_jogo, status, proximo_jogo_id, round_number,
                    time_casa, time_fora, home_team_id, away_team_id,
                    home_team_logo_url, away_team_logo_url, gols_casa, gols_fora, estadio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                params,
            )
            resultado = int(cursor.lastrowid)
        if owns_connection:
            conn.commit()
            _clear_data_cache()
        return resultado
    finally:
        if owns_connection:
            conn.close()


def salvar_jogo(jogo: Jogo, connection: Optional[DatabaseConnection] = None) -> int:
    """Compatibilidade com o nome antigo do salvamento."""
    return salvar_ou_atualizar_jogo(jogo, connection=connection)


def salvar_jogos_em_lote(jogos: Sequence[Jogo], connection: Optional[DatabaseConnection] = None) -> List[int]:
    ids: List[int] = []
    conn = connection or get_connection()
    owns_connection = connection is None
    try:
        for jogo in jogos:
            ids.append(salvar_ou_atualizar_jogo(jogo, connection=conn))
        if owns_connection:
            conn.commit()
            _clear_data_cache()
        return ids
    finally:
        if owns_connection:
            conn.close()


def atualizar_jogo_resultado(
    jogo_id: int,
    placar_a: int,
    placar_b: int,
    finalizado: bool = True,
    status: str = "finalizado",
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE Jogos
            SET placar_a = ?, placar_b = ?,
                gols_casa = ?, gols_fora = ?,
                finalizado = ?, status = ?
            WHERE id = ?
            """,
            (
                int(placar_a),
                int(placar_b),
                int(placar_a),
                int(placar_b),
                bool(finalizado),
                status,
                int(jogo_id),
            ),
        )
        conn.commit()
    _clear_data_cache()


@st.cache_data(ttl=60, show_spinner=False)
def listar_palpites_partidas_usuario(user_id: int) -> List[PalpitePartida]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, match_id, palpite_a, palpite_b
            FROM Palpites_Partidas
            WHERE user_id = ?
            ORDER BY match_id ASC
            """,
            (int(user_id),),
        ).fetchall()
    return [_row_to_palpite_partida(row) for row in rows]


def carregar_palpites_partidas(user_id: int) -> Dict[int, Dict[str, int]]:
    """Retorna os palpites de partidas em formato amigavel para a interface."""
    return {
        item.match_id: {"palpite_a": item.palpite_a, "palpite_b": item.palpite_b}
        for item in listar_palpites_partidas_usuario(user_id)
    }


def salvar_palpites_partida(user_id: int, match_id: int, palpite_a: int, palpite_b: int) -> None:
    jogo = listar_jogo_por_id(int(match_id))
    if jogo is None:
        raise ValueError("Jogo nao encontrado.")

    if bloquear_palpite_para_jogo(jogo):
        tentativa = datetime.now().astimezone().isoformat()
        print(
            "[BSD] Palpite bloqueado: "
            f"user_id={int(user_id)}, jogo_id={int(match_id)}, "
            f"data_jogo={jogo.data_jogo or '-'}, status={jogo.status or '-'}, "
            f"tentativa={tentativa}"
        )
        raise ValueError("Palpite bloqueado: o jogo já começou.")

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO Palpites_Partidas (user_id, match_id, palpite_a, palpite_b)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, match_id)
            DO UPDATE SET
                palpite_a = excluded.palpite_a,
                palpite_b = excluded.palpite_b
            """,
            (int(user_id), int(match_id), int(palpite_a), int(palpite_b)),
        )
        conn.commit()
    _clear_data_cache()


@st.cache_data(ttl=60, show_spinner=False)
def listar_palpites_especiais_usuario(user_id: int) -> Optional[PalpiteEspecial]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, campeao, vice, artilheiro, melhor_jogador,
                   primeiro_grupo_a, segundo_grupo_a
            FROM Palpites_Especiais
            WHERE user_id = ?
            """,
            (int(user_id),),
        ).fetchone()
    return _row_to_palpite_especial(row) if row else None


# Nome mantido para facilitar a migracao da interface antiga.
carregar_palpites_especiais = listar_palpites_especiais_usuario


def salvar_palpites_especiais(
    user_id: int,
    campeao: str,
    vice: str,
    artilheiro: str,
    melhor_jogador: str,
    primeiro_grupo_a: str,
    segundo_grupo_a: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO Palpites_Especiais (
                user_id, campeao, vice, artilheiro, melhor_jogador,
                primeiro_grupo_a, segundo_grupo_a
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                campeao = excluded.campeao,
                vice = excluded.vice,
                artilheiro = excluded.artilheiro,
                melhor_jogador = excluded.melhor_jogador,
                primeiro_grupo_a = excluded.primeiro_grupo_a,
                segundo_grupo_a = excluded.segundo_grupo_a
            """,
            (
                int(user_id),
                campeao.strip(),
                vice.strip(),
                artilheiro.strip(),
                melhor_jogador.strip(),
                primeiro_grupo_a.strip(),
                segundo_grupo_a.strip(),
            ),
        )
        conn.commit()
    _clear_data_cache()


@st.cache_data(ttl=60, show_spinner=False)
def carregar_resultados_oficiais() -> ResultadoOficial:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, campeao, vice, artilheiro, melhor_jogador,
                   primeiro_grupo_a, segundo_grupo_a
            FROM Resultados_Oficiais
            WHERE id = 1
            """
        ).fetchone()
    return _row_to_resultado_oficial(row) if row else ResultadoOficial()


def salvar_resultados_oficiais(
    campeao: str,
    vice: str,
    artilheiro: str,
    melhor_jogador: str,
    primeiro_grupo_a: str,
    segundo_grupo_a: str,
    executed_by_user_id: Optional[int] = None,
) -> None:
    if executed_by_user_id is not None and not usuario_eh_admin(executed_by_user_id):
        raise PermissionError("Apenas administradores podem editar o gabarito oficial.")

    atualizado_em = _agora_utc().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO Resultados_Oficiais (
                id, campeao, vice, artilheiro, melhor_jogador,
                primeiro_grupo_a, segundo_grupo_a, atualizado_em
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id)
            DO UPDATE SET
                campeao = excluded.campeao,
                vice = excluded.vice,
                artilheiro = excluded.artilheiro,
                melhor_jogador = excluded.melhor_jogador,
                primeiro_grupo_a = excluded.primeiro_grupo_a,
                segundo_grupo_a = excluded.segundo_grupo_a,
                atualizado_em = excluded.atualizado_em
            """,
            (
                campeao.strip(),
                vice.strip(),
                artilheiro.strip(),
                melhor_jogador.strip(),
                primeiro_grupo_a.strip(),
                segundo_grupo_a.strip(),
                atualizado_em,
            ),
        )
        conn.commit()
    _clear_data_cache()


def limpar_dados_invalidos(preservar_usuarios: bool = True) -> Dict[str, int]:
    """Remove dados contaminados e deixa o banco pronto para a Copa do Mundo."""
    with get_connection() as conn:
        resumo = {
            "jogos": conn.execute("SELECT COUNT(*) AS total FROM Jogos").fetchone()["total"],
            "palpites_partidas": conn.execute("SELECT COUNT(*) AS total FROM Palpites_Partidas").fetchone()["total"],
            "palpites_especiais": conn.execute("SELECT COUNT(*) AS total FROM Palpites_Especiais").fetchone()["total"],
            "classificacao": conn.execute("SELECT COUNT(*) AS total FROM Classificacao_Grupos").fetchone()["total"],
            "usuarios": conn.execute("SELECT COUNT(*) AS total FROM Usuarios").fetchone()["total"],
        }

        conn.execute("DELETE FROM Palpites_Partidas")
        conn.execute("DELETE FROM Palpites_Especiais")
        conn.execute("DELETE FROM Classificacao_Grupos")
        conn.execute("DELETE FROM Jogos")
        if not preservar_usuarios:
            conn.execute("DELETE FROM Usuarios")
        else:
            conn.execute("UPDATE Usuarios SET pontuacao_total = 0")

        atualizado_em = _agora_utc().isoformat()
        conn.execute(
            "INSERT INTO Resultados_Oficiais (id, atualizado_em) VALUES (1, ?) ON CONFLICT(id) DO NOTHING",
            (atualizado_em,),
        )
        conn.execute(
            """
            UPDATE Resultados_Oficiais
            SET campeao = '',
                vice = '',
                artilheiro = '',
                melhor_jogador = '',
                primeiro_grupo_a = '',
                segundo_grupo_a = '',
                atualizado_em = ?
            WHERE id = 1
            """,
            (atualizado_em,),
        )
        if conn.is_sqlite:
            conn.execute(
                "DELETE FROM sqlite_sequence WHERE name IN ('Jogos', 'Palpites_Partidas', 'Palpites_Especiais', 'Classificacao_Grupos', 'Usuarios')"
            )

        conn.commit()

    _clear_data_cache()
    return resumo


def salvar_classificacao_grupos(classificacoes: Sequence[ClassificacaoGrupo]) -> None:
    atualizado_em = _agora_utc().isoformat()
    with get_connection() as conn:
        conn.execute("DELETE FROM Classificacao_Grupos")
        conn.executemany(
            """
            INSERT INTO Classificacao_Grupos (
                grupo, time_nome, posicao, pontos, jogos, vitorias,
                empates, derrotas, gols_pro, gols_contra, saldo_gols,
                atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.grupo,
                    item.time_nome,
                    item.posicao,
                    item.pontos,
                    item.jogos,
                    item.vitorias,
                    item.empates,
                    item.derrotas,
                    item.gols_pro,
                    item.gols_contra,
                    item.saldo_gols,
                    atualizado_em,
                )
                for item in classificacoes
            ],
        )
        conn.commit()
    _clear_data_cache()


@st.cache_data(ttl=60, show_spinner=False)
def listar_classificacao_grupos(grupo: Optional[str] = None) -> List[ClassificacaoGrupo]:
    sql = """
        SELECT id, grupo, time_nome, posicao, pontos, jogos, vitorias,
               empates, derrotas, gols_pro, gols_contra, saldo_gols
        FROM Classificacao_Grupos
    """
    params: Tuple[object, ...] = ()
    if grupo:
        sql += " WHERE grupo = ?"
        params = (grupo,)
    sql += " ORDER BY grupo ASC, posicao ASC, time_nome ASC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_classificacao(row) for row in rows]


# Alias util para facilitar a transicao de nomes.
carregar_classificacao_grupos = listar_classificacao_grupos


def obter_resumo_banco() -> Dict[str, int]:
    """Retorna contagens simples para confirmar o banco conectado."""
    with get_connection() as conn:
        usuarios = conn.execute("SELECT COUNT(*) AS total FROM Usuarios").fetchone()["total"]
        jogos = conn.execute("SELECT COUNT(*) AS total FROM Jogos").fetchone()["total"]
        palpites_partidas = conn.execute("SELECT COUNT(*) AS total FROM Palpites_Partidas").fetchone()["total"]
        palpites_especiais = conn.execute("SELECT COUNT(*) AS total FROM Palpites_Especiais").fetchone()["total"]
    return {
        "usuarios": int(usuarios or 0),
        "jogos": int(jogos or 0),
        "palpites": int((palpites_partidas or 0) + (palpites_especiais or 0)),
    }




