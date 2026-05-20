"""Tela de recuperacao de senha."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from database import gerar_token_recuperacao, redefinir_senha_por_token
from services.email_service import enviar_email_recuperacao, smtp_configurado


def _obter_query_param(nome: str) -> Optional[str]:
    try:
        return st.query_params.get(nome)
    except AttributeError:
        params = st.experimental_get_query_params()  # type: ignore[attr-defined]
        valores = params.get(nome, [])
        return valores[0] if valores else None


def _limpar_query_params() -> None:
    try:
        st.query_params.clear()
    except AttributeError:
        try:
            st.experimental_set_query_params()  # type: ignore[attr-defined]
        except Exception:
            pass


def render_tela_recuperar_senha() -> None:
    """Renderiza a tela de recuperacao de senha."""
    st.title("Recuperar Senha")

    token_url = _obter_query_param("reset_token")

    if token_url:
        _render_form_nova_senha(token_fixo=token_url)
    elif st.session_state.get("recuperar_senha_etapa") == 2:
        _render_form_nova_senha(token_fixo=None)
    else:
        _render_form_solicitar_token()

    st.divider()
    if st.button("Voltar ao login", key="btn_voltar_login"):
        st.session_state.current_screen = "menu"
        st.session_state.pop("recuperar_senha_etapa", None)
        st.session_state.pop("recuperar_senha_token_pendente", None)
        _limpar_query_params()
        st.rerun()


def _render_form_solicitar_token() -> None:
    st.write("Informe seu nome de usuario ou email cadastrado para receber o token de recuperacao.")

    with st.form("form_solicitar_token"):
        identificador = st.text_input("Nome de usuario ou email")
        enviar = st.form_submit_button("Solicitar recuperacao")

    if not enviar:
        return

    identificador = (identificador or "").strip()
    if not identificador:
        st.error("Informe o nome de usuario ou email.")
        return

    ok, token_ou_msg, dados_usuario = gerar_token_recuperacao(identificador)

    if not ok:
        st.error(token_ou_msg)
        return

    if dados_usuario is None:
        st.info("Se o usuario existir e tiver email cadastrado, um email sera enviado. Verifique sua caixa de entrada.")
        return

    token = token_ou_msg
    email_usuario = dados_usuario.get("email") or ""

    if email_usuario and smtp_configurado():
        email_ok, email_msg = enviar_email_recuperacao(
            email_destino=str(email_usuario),
            nome_usuario=str(dados_usuario["nome"]),
            token=token,
        )
        if email_ok:
            st.success("Email enviado! Verifique sua caixa de entrada e use o token recebido abaixo.")
        else:
            st.warning(f"Nao foi possivel enviar o email automaticamente: {email_msg}")

    if not email_usuario:
        st.info("Voce nao tem email cadastrado. Use o token abaixo para redefinir sua senha.")
    elif not smtp_configurado():
        st.info("O servico de email nao esta configurado. Use o token abaixo.")

    st.code(token, language=None)
    st.caption("Guarde este token. Ele expira em 1 hora.")

    st.session_state.recuperar_senha_token_pendente = token
    st.session_state.recuperar_senha_etapa = 2
    st.rerun()


def _render_form_nova_senha(token_fixo: Optional[str]) -> None:
    st.write("Insira o token de recuperacao e escolha uma nova senha.")

    with st.form("form_nova_senha"):
        if token_fixo:
            st.text_input("Token de recuperacao", value=token_fixo, disabled=True)
            token_form = token_fixo
        else:
            token_form = st.text_input("Token de recuperacao")
        nova_senha = st.text_input("Nova senha", type="password")
        confirmar = st.text_input("Confirmar nova senha", type="password")
        enviar = st.form_submit_button("Redefinir senha")

    if not enviar:
        return

    token = token_fixo or token_form or st.session_state.get("recuperar_senha_token_pendente", "")

    if not token:
        st.error("Informe o token de recuperacao.")
        return

    if nova_senha != confirmar:
        st.error("As senhas nao conferem.")
        return

    ok, msg = redefinir_senha_por_token(token, nova_senha)
    if ok:
        st.success(f"{msg} Voce ja pode fazer login com a nova senha.")
        st.session_state.pop("recuperar_senha_etapa", None)
        st.session_state.pop("recuperar_senha_token_pendente", None)
        _limpar_query_params()
    else:
        st.error(msg)
