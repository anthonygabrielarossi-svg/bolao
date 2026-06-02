"""Aplicacao principal do bolao.

Este arquivo fica responsavel apenas por iniciar a sessao, tratar login/cadastro
simples e navegar entre as telas carregadas da pasta ui/.
"""

from __future__ import annotations

import streamlit as st
import time
from io import BytesIO
from pathlib import Path

from settings import DEBUG
from database import (
    DatabaseConfigurationError,
    DatabaseError,
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
from ui.tela_recuperar_senha import render_tela_recuperar_senha
from ui.tela_resultados import render_tela_resultados
from ui.tela_ranking import render_tela_ranking
from ui.tela_simulacao import render_tela_simulacao


st.set_page_config(
    page_title="Bolao da Copa do Mundo",
    page_icon="B",
    layout="wide",
)


@st.cache_resource(show_spinner=False)
def _inicializar_banco_cache() -> bool:
    init_db()
    return True


def inicializar_banco() -> None:
    try:
        _inicializar_banco_cache()
    except DatabaseConfigurationError as exc:
        st.error(str(exc))
        st.info('Configure DATABASE_URL em Secrets no Streamlit Cloud, por exemplo: DATABASE_URL = "postgresql+psycopg2://usuario:senha@host:porta/postgres?sslmode=require"')
        st.stop()
    except DatabaseError as exc:
        st.error("Nao foi possivel conectar ao banco PostgreSQL.")
        st.info(
            "Confira no Streamlit Cloud se o secret DATABASE_URL esta correto, "
            "se o banco aceita conexoes externas e se a URL usa SSL "
            "(exemplo: postgresql+psycopg2://usuario:senha@host:porta/postgres?sslmode=require)."
        )
        if DEBUG:
            st.exception(exc)
        st.stop()
    except Exception as exc:
        st.error("Nao foi possivel inicializar o banco de dados.")
        st.info(
            "Se estiver no Streamlit Cloud, confirme que o app foi redeployado "
            "com a ultima versao do codigo e revise o secret DATABASE_URL."
        )
        if DEBUG:
            st.exception(exc)
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
    if "pending_user_name" not in st.session_state:
        st.session_state.pending_user_name = ""


def fazer_logout() -> None:
    """Limpa a sessao e volta para a tela inicial."""
    encerrar_sessao_atual()
    st.rerun()


def render_regras() -> None:
    """Exibe as regras atualizadas do bolao."""
    st.title("Regras do Bolão — Copa do Mundo 2026")

    st.markdown("## Participação")
    st.markdown(
        """
- Valor de inscrição: **R$ 30,00** por participante (pague via PIX antes do início da Copa).
- O acesso é liberado manualmente pelo administrador após confirmação do pagamento.
- Palpites podem ser alterados a qualquer momento **até 1 hora antes do início de cada jogo**.
        """
    )

    st.markdown("## Pontuação por Partida")
    st.markdown(
        """
| Acerto | Pontos |
|--------|-------:|
| Placar exato (ex: 2 × 1) | **10** |
| Apenas o vencedor / empate correto | **5** |
| Erro | 0 |

Vale para todos os jogos: fase de grupos, mata-mata e disputa de 3º lugar.
        """
    )

    st.markdown("## Palpites Especiais")
    st.markdown(
        """
Além dos placares, cada participante faz palpites sobre o torneio inteiro.
O sistema verifica os acertos **automaticamente** com base nos resultados oficiais.

| Palpite | Pontos |
|---------|-------:|
| Campeão | **20** |
| Vice-campeão | **15** |
| Artilheiro da Copa | **10** |
| Melhor jogador (Bola de Ouro) | **10** |
| 1º colocado de cada grupo (× 12) | **5** cada |
| 2º colocado de cada grupo (× 12) | **5** cada |
| 3º colocado que avança (× 8 vagas) | **3** cada |

**Campeão e vice** são detectados automaticamente pelo resultado da Final.

**Classificação dos grupos** é calculada automaticamente ao fim da fase de grupos,
usando os critérios oficiais da FIFA: pontos → saldo de gols → gols marcados → vitórias.

**8 terceiros classificados**: os 12 terceiros colocados são ranqueados pelos mesmos
critérios e os 8 melhores avançam. O sistema identifica quem passou automaticamente.
        """
    )

    st.markdown("## Premiação")
    st.markdown(
        """
O prêmio é formado pela soma das inscrições dos participantes aprovados (R$ 30,00 cada).

| Colocação | % do prêmio |
|-----------|------------:|
| 1º lugar | **60%** |
| 2º lugar | **30%** |
| 3º lugar | **10%** |

Em caso de empate no ranking, a posição é desempatada pela ordem alfabética do nome.
        """
    )

    st.markdown("## Regras Gerais")
    st.markdown(
        """
- Os palpites de partida ficam **bloqueados 1 hora antes do início do jogo**.
- Palpites especiais (grupos, campeão, artilheiro etc.) podem ser alterados **até o início do primeiro jogo da Copa**.
- O ranking é atualizado pelo administrador após cada rodada de jogos finalizados.
- Em caso de dúvidas ou disputas, a decisão do administrador é final.
        """
    )


def render_tela_usuario_pendente() -> None:
    st.title("Acesso não liberado")

    imagem_pagamento = Path("assets/pague_bolao.png")
    if imagem_pagamento.exists():
        st.image(str(imagem_pagamento))

    st.markdown("## Pague o bolão")
    st.write("Seu cadastro foi realizado, mas ainda não foi aprovado pelo administrador.")
    st.info("Pague via PIX e entre em contato com o administrador para liberar seu acesso.")

    chave_pix = "27992048707"
    codigo_pix = _gerar_pix_copia_cola(
        chave_pix="+5527992048707",
        valor=30.00,
        nome_recebedor="BOLAO DA COPA",
        cidade="BRASIL",
        txid="BOLAO2026",
    )

    col_qr, col_dados = st.columns([1, 2])
    with col_qr:
        qr_png = _gerar_qr_code_png(codigo_pix)
        if qr_png:
            st.image(qr_png, caption="PIX - R$ 30,00", width=220)
        else:
            st.warning("QR code indisponivel neste ambiente.")

    with col_dados:
        st.write("Valor: **R$ 30,00**")
        st.write(f"Chave PIX: **{chave_pix}**")
        st.caption("Se preferir, copie o codigo PIX abaixo no app do banco.")
        st.code(codigo_pix, language=None)

    if st.button("Voltar"):
        st.session_state.clear()
        st.rerun()


def _campo_emv(id_campo: str, valor: str) -> str:
    return f"{id_campo}{len(valor):02d}{valor}"


def _crc16_ccitt(payload: str) -> str:
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _gerar_pix_copia_cola(
    *,
    chave_pix: str,
    valor: float,
    nome_recebedor: str,
    cidade: str,
    txid: str,
) -> str:
    merchant_account = _campo_emv("00", "BR.GOV.BCB.PIX") + _campo_emv("01", chave_pix)
    additional_data = _campo_emv("05", txid[:25])
    payload_sem_crc = (
        _campo_emv("00", "01")
        + _campo_emv("26", merchant_account)
        + _campo_emv("52", "0000")
        + _campo_emv("53", "986")
        + _campo_emv("54", f"{valor:.2f}")
        + _campo_emv("58", "BR")
        + _campo_emv("59", nome_recebedor[:25])
        + _campo_emv("60", cidade[:15])
        + _campo_emv("62", additional_data)
        + "6304"
    )
    return payload_sem_crc + _crc16_ccitt(payload_sem_crc)


def _gerar_qr_code_png(conteudo: str) -> BytesIO | None:
    try:
        import qrcode
    except ImportError:
        return None

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(conteudo)
    qr.make(fit=True)
    imagem = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def render_auth_screen() -> None:
    """Tela inicial com login e cadastro."""
    if st.session_state.get("current_screen") == "recuperar_senha":
        render_tela_recuperar_senha()
        st.stop()

    if st.session_state.get("pending_user_name"):
        render_tela_usuario_pendente()
        st.stop()

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
                if not getattr(usuario, "aprovado", True):
                    st.session_state.pending_user_name = usuario.nome
                    st.rerun()
                criar_sessao_autenticada(usuario)
                st.success("Login realizado com sucesso.")
                st.rerun()
            else:
                st.error("Nome de usuario ou senha invalidos.")

        if st.button("Esqueci minha senha", key="btn_esqueci_senha"):
            st.session_state.current_screen = "recuperar_senha"
            st.session_state.pop("recuperar_senha_usuario", None)
            st.session_state.pop("recuperar_senha_liberada", None)
            st.rerun()

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
    if st.session_state.is_admin:
        st.sidebar.caption(f"Banco conectado: {get_database_kind()}")
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
    inicio = time.perf_counter()
    inicializar_banco()
    iniciar_session_state()

    logado = manter_sessao_por_cookie_ou_state()
    if logado:
        render_menu_principal()
    else:
        render_auth_screen()
    if DEBUG or bool(st.session_state.get("is_admin")):
        st.caption(f"Tempo de carregamento: {time.perf_counter() - inicio:.2f}s")


if __name__ == "__main__":
    main()
