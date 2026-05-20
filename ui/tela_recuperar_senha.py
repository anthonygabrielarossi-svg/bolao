"""Tela de recuperacao de senha."""

from __future__ import annotations

import streamlit as st

from database import redefinir_senha_liberada, solicitar_recuperacao_senha


def render_tela_recuperar_senha() -> None:
    """Renderiza a tela de recuperacao de senha."""
    st.title("Recuperar Senha")
    st.write("Informe seu nome de usuario para solicitar a liberacao da troca de senha.")

    with st.form("form_solicitar_recuperacao"):
        nome_usuario = st.text_input(
            "Nome de usuario",
            value=st.session_state.get("recuperar_senha_usuario", ""),
        )
        enviar = st.form_submit_button("Verificar recuperacao")

    if enviar:
        ok, mensagem, dados_usuario = solicitar_recuperacao_senha(nome_usuario)
        if not ok:
            st.error(mensagem)
        else:
            st.session_state.recuperar_senha_usuario = (
                str(dados_usuario["nome"]) if dados_usuario else nome_usuario.strip()
            )
            st.session_state.recuperar_senha_liberada = bool(
                dados_usuario and dados_usuario.get("troca_senha_liberada")
            )
            if st.session_state.recuperar_senha_liberada:
                st.success("Troca de senha liberada. Defina sua nova senha abaixo.")
            elif dados_usuario is None:
                st.info(mensagem)
            else:
                st.info(
                    "Solicitacao enviada. Aguarde o administrador liberar a troca de senha e tente novamente."
                )

    if st.session_state.get("recuperar_senha_liberada"):
        _render_form_nova_senha()

    st.divider()
    if st.button("Voltar ao login", key="btn_voltar_login"):
        st.session_state.current_screen = "menu"
        st.session_state.pop("recuperar_senha_usuario", None)
        st.session_state.pop("recuperar_senha_liberada", None)
        st.rerun()


def _render_form_nova_senha() -> None:
    st.write("Escolha uma nova senha.")

    with st.form("form_nova_senha"):
        nova_senha = st.text_input("Nova senha", type="password")
        confirmar = st.text_input("Confirmar nova senha", type="password")
        enviar = st.form_submit_button("Redefinir senha")

    if not enviar:
        return

    nome_usuario = st.session_state.get("recuperar_senha_usuario", "")
    if not nome_usuario:
        st.error("Informe o nome de usuario novamente.")
        return

    if nova_senha != confirmar:
        st.error("As senhas nao conferem.")
        return

    ok, msg = redefinir_senha_liberada(nome_usuario, nova_senha)
    if ok:
        st.success(f"{msg} Voce ja pode fazer login com a nova senha.")
        st.session_state.pop("recuperar_senha_usuario", None)
        st.session_state.pop("recuperar_senha_liberada", None)
    else:
        st.error(msg)
