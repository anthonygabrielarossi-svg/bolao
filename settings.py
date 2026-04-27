"""Configuracao central da integracao com a API BSD.

O projeto carrega automaticamente um arquivo `.env` simples na raiz e expõe
uma fonte unica para a API key e os headers usados nas chamadas HTTP.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
_API_KEY_LOGGED = False


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _parse_env_line(line: str) -> Optional[tuple[str, str]]:
    texto = line.strip()
    if not texto or texto.startswith("#") or "=" not in texto:
        return None

    chave, valor = texto.split("=", 1)
    chave = chave.strip()
    valor = valor.strip()
    if not chave:
        return None

    if len(valor) >= 2 and ((valor.startswith('"') and valor.endswith('"')) or (valor.startswith("'") and valor.endswith("'"))):
        valor = valor[1:-1]

    return chave, valor


def load_env_file(path: Optional[Path] = None) -> None:
    """Carrega um arquivo `.env` simples para `os.environ`."""
    env_path = Path(path) if path is not None else ENV_PATH
    if not env_path.exists() or not env_path.is_file():
        return

    try:
        linhas = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for linha in linhas:
        parsed = _parse_env_line(linha)
        if parsed is None:
            continue
        chave, valor = parsed
        os.environ.setdefault(chave, valor)


def get_api_key() -> str:
    """Retorna a chave fixa da API da sports.bzzoiro.com."""
    global _API_KEY_LOGGED

    token = os.getenv("SPORTS_API_KEY", "").strip()
    if not token:
        raise RuntimeError("Variável de ambiente SPORTS_API_KEY não definida")

    if not _API_KEY_LOGGED:
        print("[BSD] API KEY carregada do ambiente")
        _API_KEY_LOGGED = True

    return token


def get_headers() -> dict[str, str]:
    """Monta os headers padronizados para a API BSD."""
    token = get_api_key()
    print("[BSD] API chamada com autenticação OK")
    return {
        "Authorization": f"Token {token}",
        "Accept": "application/json",
    }


load_env_file()


SESSION_IDLE_TIMEOUT_MINUTES = _get_int_env("SESSION_IDLE_TIMEOUT_MINUTES", 15)
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "bolao_session_token").strip() or "bolao_session_token"
SESSION_COOKIE_MAX_AGE_DAYS = _get_int_env("SESSION_COOKIE_MAX_AGE_DAYS", 30)
TEST_MODE_AO_VIVO = _get_bool_env("TEST_MODE_AO_VIVO", True)
