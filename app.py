"""Aplicacao principal do bolao.

Este arquivo fica responsavel apenas por iniciar a sessao, tratar login/cadastro
simples e navegar entre as telas carregadas da pasta ui/.
"""

from __future__ import annotations

import streamlit as st

from database import (
    DatabaseConfigurationError,
    autenticar_usuario,
    cadastrar_usuario,
    get_database_kind,
    init_db,
    obter_resumo_banco,
)
from services.session_service import (
    criar_sessao_autenticada,
    encerrar_sessao_atual,
    manter_sessao_por_cookie_ou_state,
)
from ui.tela_admin import render_tela_admin
from ui.tela_ao_vivo import render_tela_ao_vivo
from ui.tela_palpites import render_tela_palpites
from ui.tela_resultados import render_tela_resultados
from ui.tela_ranking import render_tela_ranking
from ui.tela_simulacao import render_tela_simulacao


st.set_page_config(
    page_title="Bolao da Copa do Mundo",
    page_icon="B",
    layout="wide",
)


def inicializar_banco() -> None:
    try:
        init_db()
    except DatabaseConfigurationError as exc:
        st.error(str(exc))
        st.info('Configure DATABASE_URL em Secrets no Streamlit Cloud, por exemplo: DATABASE_URL = "postgresql+psycopg2://usuario:senha@host:porta/postgres"')
        st.stop()


def iniciar_session_state() -> None:
    """Garante as chaves basicas da sessao."""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = ""
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    if "current_screen" not in st.session_state:
        st.session_state.current_screen = "menu"
    if "menu_atual" not in st.session_state:
        st.session_state.menu_atual = "Palpites"
    if "session_token" not in st.session_state:
        st.session_state.session_token = None
    if "auth_flash_message" not in st.session_state:
        st.session_state.auth_flash_message = ""


def fazer_logout() -> None:
    """Limpa a sessao e volta para a tela inicial."""
    encerrar_sessao_atual()
    st.rerun()


def render_regras() -> None:
    """Exibe o texto base das regras do bolao."""
    st.title("Regras da Copa do Mundo")
    st.markdown(
        """
        O sistema funciona por pontos com base nos acertos da Copa do Mundo.

        - 10 pontos: placar exato
        - 5 pontos: acertar o vencedor da partida
        - 20 pontos: acertar o campeao
        - 15 pontos: acertar o vice-campeao
        - 10 pontos: acertar o artilheiro
        - 10 pontos: acertar o melhor jogador
        - A fase de grupos usa os grupos A ate L
        - O mata-mata segue o chaveamento oficial da Copa do Mundo 2026

        O ranking exibe a soma da pontuacao total de cada usuario.
        """
    )


def render_auth_screen() -> None:
    """Tela inicial com login e cadastro."""
    st.title("Bolao da Copa do Mundo")
    st.write("Entre para registrar seus palpites ou crie seu usuario para comecar.")

    mensagem = str(st.session_state.get("auth_flash_message") or "").strip()
    if mensagem:
        st.warning(mensagem)
        st.session_state.auth_flash_message = ""

    tab_login, tab_cadastro = st.tabs(["Login", "Cadastro"])

    with tab_login:
        with st.form("form_login", clear_on_submit=False):
            nome = st.text_input("Nome de usuario")
            senha = st.text_input("Senha", type="password")
            enviar = st.form_submit_button("Entrar")

        if enviar:
            usuario = autenticar_usuario(nome, senha)
            if usuario:
                criar_sessao_autenticada(usuario)
                st.success("Login realizado com sucesso.")
                st.rerun()
            else:
                st.error("Nome de usuario ou senha invalidos.")

    with tab_cadastro:
        with st.form("form_cadastro", clear_on_submit=False):
            nome_novo = st.text_input("Nome de usuario", key="cad_nome")
            senha_nova = st.text_input("Senha", type="password", key="cad_senha")
            confirmar_senha = st.text_input("Confirmar senha", type="password")
            enviar_cadastro = st.form_submit_button("Criar conta")

        if enviar_cadastro:
            if senha_nova != confirmar_senha:
                st.error("As senhas nao conferem.")
            else:
                ok, mensagem = cadastrar_usuario(nome_novo, senha_nova)
                if ok:
                    st.success(mensagem)
                else:
                    st.error(mensagem)


def render_menu_principal() -> None:
    """Renderiza a navegacao depois do login."""
    st.sidebar.title(f"Bem-vindo, {st.session_state.user_name}")
    st.sidebar.caption(f"Banco conectado: {get_database_kind()}")
    if st.session_state.is_admin:
        st.sidebar.caption("Perfil: administrador")
        if st.sidebar.button("Testar conexao banco"):
            try:
                resumo = obter_resumo_banco()
            except Exception as exc:
                st.sidebar.error(f"Falha ao consultar banco: {exc}")
            else:
                st.sidebar.write(f"Usuarios: {resumo['usuarios']}")
                st.sidebar.write(f"Jogos: {resumo['jogos']}")
                st.sidebar.write(f"Palpites: {resumo['palpites']}")
    else:
        st.sidebar.caption("Perfil: usuario")

    if st.session_state.is_admin and st.sidebar.button("Abrir painel admin"):
        st.session_state.current_screen = "admin"
        st.rerun()

    if st.session_state.current_screen == "admin":
        if not st.session_state.is_admin:
            st.error("Acesso negado. Este painel e restrito a administradores.")
            st.session_state.current_screen = "menu"
            st.rerun()
        if st.sidebar.button("Voltar ao menu"):
            st.session_state.current_screen = "menu"
            st.rerun()
        render_tela_admin(int(st.session_state.user_id))
        return

    opcoes_menu = ["Palpites", "Resultados", "Ao Vivo", "Simulacao", "Ranking", "Regras"]
    if st.session_state.is_admin:
        opcoes_menu.append("Admin")

    st.sidebar.radio(
        "Menu",
        opcoes_menu,
        index=opcoes_menu.index(st.session_state.menu_atual)
        if st.session_state.menu_atual in opcoes_menu
        else 0,
        key="menu_atual",
    )
    if st.sidebar.button("Sair"):
        fazer_logout()

    menu = st.session_state.menu_atual
    if menu == "Palpites":
        render_tela_palpites(int(st.session_state.user_id))
    elif menu == "Resultados":
        render_tela_resultados()
    elif menu == "Ao Vivo":
        render_tela_ao_vivo()
    elif menu == "Simulacao":
        render_tela_simulacao()
    elif menu == "Ranking":
        render_tela_ranking()
    elif menu == "Admin" and st.session_state.is_admin:
        st.session_state.current_screen = "admin"
        st.rerun()
    else:
        render_regras()


def main() -> None:
    """Ponto de entrada da aplicacao."""
    inicializar_banco()
    iniciar_session_state()

    if manter_sessao_por_cookie_ou_state():
        render_menu_principal()
    else:
        render_auth_screen()


if __name__ == "__main__":
    main()
