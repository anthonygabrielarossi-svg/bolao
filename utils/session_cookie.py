"""Ponte minima para ler e gravar o cookie da sessao no navegador."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components

from settings import SESSION_COOKIE_MAX_AGE_DAYS, SESSION_COOKIE_NAME


_COMPONENT_DIR = Path(__file__).resolve().parent.parent / "components" / "session_cookie"
_SESSION_COOKIE_COMPONENT = components.declare_component("session_cookie", path=_COMPONENT_DIR)


def _max_age_seconds(max_age_days: Optional[int] = None) -> int:
    dias = SESSION_COOKIE_MAX_AGE_DAYS if max_age_days is None else int(max_age_days)
    dias = max(int(dias), 1)
    return dias * 24 * 60 * 60


def ler_cookie_sessao(default: str = "") -> str:
    """Lê o token da sessao salvo no cookie do navegador."""
    valor = _SESSION_COOKIE_COMPONENT(
        action="get",
        cookie_name=SESSION_COOKIE_NAME,
        default=default,
        key="session_cookie_reader",
    )
    return str(valor or default or "")


def definir_cookie_sessao(session_token: Optional[str], max_age_days: Optional[int] = None) -> str:
    """Grava o token da sessao no cookie do navegador."""
    token = str(session_token or "").strip()
    valor = _SESSION_COOKIE_COMPONENT(
        action="set",
        cookie_name=SESSION_COOKIE_NAME,
        session_token=token,
        max_age_seconds=_max_age_seconds(max_age_days),
        default=token,
        key="session_cookie_writer",
    )
    return str(valor or token or "")


def limpar_cookie_sessao() -> str:
    """Remove o cookie da sessao do navegador."""
    valor = _SESSION_COOKIE_COMPONENT(
        action="clear",
        cookie_name=SESSION_COOKIE_NAME,
        default="",
        key="session_cookie_clear",
    )
    return str(valor or "")


__all__ = [
    "definir_cookie_sessao",
    "limpar_cookie_sessao",
    "ler_cookie_sessao",
]
