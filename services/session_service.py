"""Servico de sessao persistente com expiracao por inatividade."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import streamlit as st

from database import (
    Usuario,
    buscar_sessao_por_token,
    buscar_usuario_por_id,
    criar_sessao_usuario,
    renovar_sessao_por_atividade,
    revogar_sessao,
)
from utils.datetime_utils import parse_iso_datetime
from utils.session_cookie import definir_cookie_sessao, limpar_cookie_sessao, ler_cookie_sessao

SESSION_RENEW_THROTTLE_SECONDS = 300


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _deve_renovar_sessao() -> bool:
    agora = _agora_utc()
    ultima = st.session_state.get("last_session_renewal_at")
    if not isinstance(ultima, datetime):
        return True
    if ultima.tzinfo is None:
        ultima = ultima.replace(tzinfo=timezone.utc)
    return (agora - ultima.astimezone(timezone.utc)).total_seconds() >= SESSION_RENEW_THROTTLE_SECONDS


def _marcar_renovacao_sessao() -> None:
    st.session_state["last_session_renewal_at"] = _agora_utc()


def _sessao_expirada(sessao: dict[str, object], agora: Optional[datetime] = None) -> bool:
    expires_at = parse_iso_datetime(str(sessao.get("expires_at") or ""))
    if expires_at is None:
        return True

    referencia = agora or _agora_utc()
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=timezone.utc)
    else:
        referencia = referencia.astimezone(timezone.utc)

    return referencia >= expires_at.astimezone(timezone.utc)


def _aplicar_estado_autenticado(usuario: Usuario, session_token: str) -> None:
    st.session_state.logged_in = True
    st.session_state.user_id = usuario.id
    st.session_state.user_name = usuario.nome
    st.session_state.is_admin = bool(usuario.is_admin)
    st.session_state.current_screen = "menu"
    st.session_state.session_token = session_token
    st.session_state.auth_flash_message = ""


def _limpar_estado_sessao(mensagem: Optional[str] = None) -> None:
    st.session_state.clear()
    if mensagem:
        st.session_state.auth_flash_message = mensagem


def criar_sessao_autenticada(usuario: Usuario) -> str:
    """Cria a sessao persistida e grava o token no cookie do navegador."""
    sessao = criar_sessao_usuario(usuario.id)
    token = str(sessao["session_token"])
    definir_cookie_sessao(token)
    _aplicar_estado_autenticado(usuario, token)
    _marcar_renovacao_sessao()
    return token


def manter_sessao_por_cookie_ou_state() -> bool:
    """Valida a sessao atual e renova o tempo de atividade quando aplicavel."""
    token_state = str(st.session_state.get("session_token") or "").strip()

    if st.session_state.get("logged_in") and token_state:
        sessao = buscar_sessao_por_token(token_state)
        if sessao is None or sessao.get("revoked"):
            limpar_cookie_sessao()
            _limpar_estado_sessao()
            return False

        if _sessao_expirada(sessao):
            revogar_sessao(token_state)
            limpar_cookie_sessao()
            _limpar_estado_sessao("Sessão expirada por inatividade. Faça login novamente.")
            return False

        if _deve_renovar_sessao():
            if renovar_sessao_por_atividade(token_state) is None:
                limpar_cookie_sessao()
                _limpar_estado_sessao("Sessão expirada por inatividade. Faça login novamente.")
                return False
            definir_cookie_sessao(token_state)
            _marcar_renovacao_sessao()
        st.session_state.auth_flash_message = ""
        return True

    cookie_token = ler_cookie_sessao()
    if not cookie_token:
        return False

    sessao = buscar_sessao_por_token(cookie_token)
    if sessao is None:
        limpar_cookie_sessao()
        return False

    if sessao.get("revoked"):
        limpar_cookie_sessao()
        return False

    if _sessao_expirada(sessao):
        revogar_sessao(cookie_token)
        limpar_cookie_sessao()
        _limpar_estado_sessao("Sessão expirada por inatividade. Faça login novamente.")
        return False

    usuario = buscar_usuario_por_id(int(sessao["user_id"]))
    if usuario is None:
        revogar_sessao(cookie_token)
        limpar_cookie_sessao()
        _limpar_estado_sessao("Sessão inválida. Faça login novamente.")
        return False

    if renovar_sessao_por_atividade(cookie_token) is None:
        limpar_cookie_sessao()
        _limpar_estado_sessao("Sessão expirada por inatividade. Faça login novamente.")
        return False

    definir_cookie_sessao(cookie_token)
    _aplicar_estado_autenticado(usuario, cookie_token)
    _marcar_renovacao_sessao()
    return True


def encerrar_sessao_atual() -> None:
    """Revoga a sessao ativa, limpa o cookie e remove o estado local."""
    token_state = str(st.session_state.get("session_token") or "").strip()
    if token_state:
        revogar_sessao(token_state)
    limpar_cookie_sessao()
    _limpar_estado_sessao()


__all__ = [
    "criar_sessao_autenticada",
    "encerrar_sessao_atual",
    "manter_sessao_por_cookie_ou_state",
]
