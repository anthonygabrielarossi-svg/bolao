"""Painel admin.

Este painel concentra operacoes de manutencao: importacao de jogos, atualizacao
manual de resultados, recalculo da classificacao e salvamento do gabarito oficial.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from database import (
    COMPETICAO_PADRAO,
    DatabaseError,
    FASE_NAO_MAPEADA,
    aprovar_usuario,
    carregar_classificacao_grupos,
    carregar_resultados_oficiais,
    contar_jogadores_copa,
    get_database_kind,
    get_especiais_abertos,
    set_especiais_abertos,
    listar_jogadores_copa,
    listar_usuarios,
    listar_jogos,
    liberar_troca_senha_usuario,
    obter_diagnostico_banco,
    salvar_resultados_oficiais,
    usuario_eh_admin,
)
from settings import DEBUG, TEST_MODE_AO_VIVO
from services.api_service import BSDAPIError
from services.classificacao_service import atualizar_tabela_classificacao
from services.jogos_service import (
    atualizar_resultados,
    atualizar_jogos_copa,
    corrigir_fases_copa,
    corrigir_grupos_fase_de_grupos,
    gerar_mata_mata_automatico,
    importar_jogadores_copa,
    importar_jogos_copa,
    listar_jogos_importados_debug,
)
from services.ranking_service import _obter_campeao_vice_da_final, _obter_classificacao_grupos_oficial, detalhar_pontuacao_usuario, recalcular_ranking_automaticamente
from utils.formatters import normalizar_texto
from utils.team_assets import construir_mapa_logos_por_jogos, render_team_identity_html


def _render_html_table(df: pd.DataFrame, *, class_name: str) -> None:
    """Renderiza um DataFrame como tabela HTML para preservar logos e spans."""
    if df.empty:
        return
    html_table = df.to_html(index=False, escape=False, classes=class_name)
    st.markdown(html_table, unsafe_allow_html=True)


def render_tela_admin(user_id: int) -> None:
    """Renderiza o painel administrativo."""
    if not usuario_eh_admin(user_id):
        st.error("Acesso negado. Apenas administradores podem visualizar este painel.")
        return

    st.title("Painel Admin")
    st.write("Ferramentas administrativas da Copa do Mundo.")
    st.markdown(
        """
        <style>
        .wc-admin-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 0.5rem;
        }
        .wc-admin-table th,
        .wc-admin-table td {
            padding: 0.7rem 0.75rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.12);
            vertical-align: middle;
            text-align: left;
        }
        .wc-admin-table th {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: rgba(255, 255, 255, 0.65);
        }
        .wc-team-identity {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            flex-wrap: wrap;
        }
        .wc-team-flag-img {
            width: 26px;
            height: 17px;
            object-fit: cover;
            border-radius: 2px;
            flex-shrink: 0;
        }
        .wc-team-logo {
            width: 22px;
            height: 22px;
            object-fit: contain;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.06);
        }
        .wc-team-name {
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    aba_importar, aba_resultados, aba_gabarito, aba_usuarios, aba_preview, aba_debug = st.tabs(
        ["Importar jogos", "Atualizar resultados", "Gabarito oficial", "Usuários", "Preview", "Debug importação"]
    )

    with aba_importar:
        st.subheader("Importacao de jogos")
        st.caption(f"Fluxo fixo para {COMPETICAO_PADRAO} (liga 27).")
        if st.button("Diagnóstico do sistema"):
            try:
                diagnostico = obter_diagnostico_banco()
            except DatabaseError as exc:
                st.error(f"Erro ao consultar diagnostico: {exc}")
            else:
                col_db, col_users, col_games, col_palpites = st.columns(4)
                col_db.metric("Banco", get_database_kind())
                col_users.metric("Usuarios", diagnostico["usuarios"])
                col_games.metric("Jogos", diagnostico["jogos"])
                col_palpites.metric("Palpites", diagnostico["palpites"])
                col_sem, col_sess, col_live, col_debug = st.columns(4)
                col_sem.metric("Jogos sem grupo", diagnostico["jogos_sem_grupo"])
                col_sess.metric("Sessoes ativas", diagnostico["sessoes_ativas"])
                col_live.metric("TEST_MODE_AO_VIVO", "ON" if TEST_MODE_AO_VIVO else "OFF")
                col_debug.metric("DEBUG", "ON" if DEBUG else "OFF")
                st.dataframe(
                    pd.DataFrame(
                        sorted(diagnostico["por_fase"].items()),
                        columns=["Fase", "Total"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
        if st.button("Importar jogos agora"):
            try:
                total = importar_jogos_copa(executed_by_user_id=user_id)
            except BSDAPIError as exc:
                st.warning(f"Nao foi possivel consultar a API: {exc}")
            except PermissionError as exc:
                st.error(str(exc))
            except DatabaseError as exc:
                st.error(f"Erro ao salvar os jogos no banco: {exc}")
            else:
                if total > 0:
                    st.success(f"{total} jogos importados ou atualizados.")
                else:
                    st.warning("Nenhum jogo foi importado.")

        if st.button("Corrigir fases importadas"):
            try:
                resumo_fases = corrigir_fases_copa(executed_by_user_id=user_id)
            except PermissionError as exc:
                st.error(str(exc))
            except DatabaseError as exc:
                st.error(f"Erro ao corrigir as fases no banco: {exc}")
            else:
                st.success("Fases corrigidas com sucesso.")
                st.write(
                    f"{resumo_fases['total']} jogos verificados, "
                    f"{resumo_fases['atualizados']} atualizados, "
                    f"{resumo_fases['nao_mapeados']} nao mapeados."
                )
                df_resumo_fases = pd.DataFrame(
                    sorted(resumo_fases["por_fase"].items()),
                    columns=["Fase", "Quantidade"],
                )
                st.dataframe(df_resumo_fases, use_container_width=True, hide_index=True)
                st.json(resumo_fases["confirmacoes"])

        st.divider()
        st.subheader("Jogadores da Copa")
        total_jogadores = contar_jogadores_copa()
        st.caption(f"Jogadores importados: **{total_jogadores}**")
        if st.button("Importar jogadores da Copa"):
            progresso = st.progress(0)
            status_text = st.empty()

            def _progresso_jogadores(atual: int, total: int) -> None:
                pct = int((atual / total) * 100) if total else 100
                progresso.progress(min(max(pct, 0), 100))
                status_text.caption(f"Importando seleção {atual}/{total}...")

            try:
                with st.spinner("Buscando jogadores de todas as seleções..."):
                    total_imp = importar_jogadores_copa(
                        executed_by_user_id=user_id,
                        progress_callback=_progresso_jogadores,
                    )
            except BSDAPIError as exc:
                st.warning(f"Erro na API ao importar jogadores: {exc}")
            except PermissionError as exc:
                st.error(str(exc))
            except DatabaseError as exc:
                st.error(f"Erro ao salvar jogadores: {exc}")
            else:
                progresso.progress(100)
                status_text.empty()
                st.success(f"{total_imp} jogadores importados com sucesso.")

        if st.button("Corrigir grupos da fase de grupos"):
            try:
                resumo_grupos = corrigir_grupos_fase_de_grupos(executed_by_user_id=user_id)
            except PermissionError as exc:
                st.error(str(exc))
            except DatabaseError as exc:
                st.error(f"Erro ao corrigir os grupos no banco: {exc}")
            else:
                st.success("Grupos corrigidos com sucesso.")
                st.write(
                    f"{resumo_grupos['total']} jogos verificados, "
                    f"{resumo_grupos['atualizados']} atualizados, "
                    f"{resumo_grupos['nao_mapeados']} nao mapeados."
                )
                df_resumo_grupos = pd.DataFrame(
                    sorted(resumo_grupos["por_grupo"].items()),
                    columns=["Grupo", "Quantidade"],
                )
                st.dataframe(df_resumo_grupos, use_container_width=True, hide_index=True)
                if resumo_grupos["jogos_nao_mapeados"]:
                    st.warning("Existem jogos da fase de grupos sem grupo identificado.")
                    df_nao_mapeados = pd.DataFrame(resumo_grupos["jogos_nao_mapeados"])
                    if not df_nao_mapeados.empty:
                        df_nao_mapeados["time_casa"] = df_nao_mapeados.apply(
                            lambda linha: render_team_identity_html(
                                linha.get("time_casa_nome") or linha.get("time_casa"),
                                team_id=linha.get("home_team_id"),
                                logo_url=linha.get("home_team_logo_url"),
                            ),
                            axis=1,
                        )
                        df_nao_mapeados["time_fora"] = df_nao_mapeados.apply(
                            lambda linha: render_team_identity_html(
                                linha.get("time_fora_nome") or linha.get("time_fora"),
                                team_id=linha.get("away_team_id"),
                                logo_url=linha.get("away_team_logo_url"),
                            ),
                            axis=1,
                        )
                        df_nao_mapeados = df_nao_mapeados.drop(
                            columns=["time_casa_nome", "time_fora_nome"],
                            errors="ignore",
                        )
                    _render_html_table(df_nao_mapeados, class_name="wc-admin-table")

    with aba_resultados:
        st.subheader("Atualizacao de resultados")
        st.caption(f"Fluxo fixo para {COMPETICAO_PADRAO} (liga 27).")
        if st.button("Atualizar resultados agora"):
            barra = st.progress(0)
            status = st.empty()

            def _cb_resultados(atual: int, total: int) -> None:
                # etapa 1 ocupa 0-60% da barra
                pct = int((atual / total) * 60) if total else 60
                barra.progress(min(pct, 60))
                status.caption(f"Buscando resultados na API: {atual}/{total} jogos...")

            try:
                status.caption("Buscando resultados na API...")
                atualizados = atualizar_resultados(
                    executed_by_user_id=user_id,
                    progress_callback=_cb_resultados,
                )

                barra.progress(65)
                status.caption("Atualizando tabela de classificação dos grupos...")
                classificacao = atualizar_tabela_classificacao(executed_by_user_id=user_id)

                barra.progress(78)
                status.caption("Verificando confrontos de mata-mata...")
                mata_mata = gerar_mata_mata_automatico(executed_by_user_id=user_id)

                barra.progress(90)
                status.caption("Recalculando ranking dos participantes...")
                ranking = recalcular_ranking_automaticamente(executed_by_user_id=user_id)

                barra.progress(100)
                status.empty()
            except BSDAPIError as exc:
                barra.empty()
                status.empty()
                st.warning(f"Nao foi possivel consultar a API de resultados: {exc}")
            except PermissionError as exc:
                barra.empty()
                status.empty()
                st.error(str(exc))
            except DatabaseError as exc:
                barra.empty()
                status.empty()
                st.error(f"Erro ao atualizar o banco: {exc}")
            else:
                mata_mata_msg = (
                    "mata-mata via API ✓"
                    if mata_mata == 0
                    else f"{mata_mata} jogos de mata-mata gerados (fallback)"
                )
                st.success(
                    f"{atualizados} resultados atualizados · {len(classificacao)} linhas de classificação · "
                    f"{mata_mata_msg} · {len(ranking)} usuários recalculados."
                )

        st.divider()
        st.subheader("Sincronizacao automatica dos jogos")
        if st.button("Atualizar jogos pela API"):
            progresso = st.progress(0)

            def _progresso(atual: int, total: int) -> None:
                porcentagem = int((atual / total) * 100) if total else 100
                progresso.progress(min(max(porcentagem, 0), 100))

            try:
                with st.spinner("Sincronizando jogos da Copa com a API..."):
                    resumo_update = atualizar_jogos_copa(
                        executed_by_user_id=user_id,
                        progress_callback=_progresso,
                    )
            except BSDAPIError as exc:
                st.warning(f"Nao foi possivel atualizar os jogos pela API: {exc}")
            except PermissionError as exc:
                st.error(str(exc))
            except DatabaseError as exc:
                st.error(f"Erro ao sincronizar os jogos no banco: {exc}")
            else:
                progresso.progress(100)
                st.success(
                    f"{resumo_update['total_eventos']} eventos processados, "
                    f"{resumo_update['inseridos']} inseridos, "
                    f"{resumo_update['atualizados']} atualizados e "
                    f"{resumo_update['sem_alteracao']} sem alteração."
                )
                st.write(
                    f"{resumo_update['finalizados']} jogos finalizados, "
                    f"{resumo_update['nao_mapeados']} com fase não mapeada, "
                    f"{resumo_update['placeholders']} placeholders e "
                    f"{resumo_update['reais']} jogos reais."
                )
                if resumo_update["ranking_recalculado_executado"]:
                    st.info(
                        f"Ranking recalculado para {resumo_update['ranking_recalculado']} usuarios."
                    )
                else:
                    st.info("Nenhum jogo finalizado encontrado; ranking nao foi recalculado.")

        st.divider()
        st.subheader("Recalcular ranking")
        st.caption("Recalcula a pontuação de todos os usuários com base nos resultados finalizados.")
        if st.button("Recalcular ranking agora"):
            try:
                ranking = recalcular_ranking_automaticamente(executed_by_user_id=user_id)
            except PermissionError as exc:
                st.error(str(exc))
            except DatabaseError as exc:
                st.error(f"Erro ao recalcular ranking: {exc}")
            else:
                st.success(f"Ranking recalculado para {len(ranking)} usuários.")
                df_ranking = pd.DataFrame(
                    [
                        {
                            "Posição": i + 1,
                            "Nome": item.nome,
                            "Partidas": item.pontos_partidas,
                            "Especiais": item.pontos_especiais,
                            "Total": item.pontuacao_total,
                        }
                        for i, item in enumerate(ranking)
                    ]
                )
                st.dataframe(df_ranking, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Diagnóstico de pontuação por usuário")
        st.caption("Mostra de onde vêm os pontos de cada usuário (útil para depuração).")
        usuarios_diag = listar_usuarios()
        nomes_usuarios = {u.nome: u.id for u in usuarios_diag if u.id is not None}
        usuario_selecionado = st.selectbox("Selecionar usuário", options=list(nomes_usuarios.keys()), key="diag_usuario_sel")
        if st.button("Ver detalhes de pontuação", key="btn_diag_pontuacao"):
            uid = nomes_usuarios.get(usuario_selecionado)
            if uid is not None:
                try:
                    detalhes = detalhar_pontuacao_usuario(int(uid))
                except Exception as exc:
                    st.error(f"Erro ao detalhar pontuação: {exc}")
                else:
                    st.write(f"**Jogos finalizados no banco:** {detalhes['jogos_finalizados']}")
                    st.write(f"**Total partidas:** {detalhes['total_partidas']} pts · **Total especiais:** {detalhes['total_especiais']} pts")
                    if detalhes["partidas"]:
                        st.write("**Pontos por partida:**")
                        st.dataframe(pd.DataFrame(detalhes["partidas"]), use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhum ponto de partida.")
                    especiais_com_palpite = [e for e in detalhes["especiais"] if e["palpite"]]
                    if especiais_com_palpite:
                        st.write("**Palpites especiais:**")
                        st.dataframe(pd.DataFrame(especiais_com_palpite), use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhum palpite especial cadastrado.")

        if st.button("Sincronizar placares ao vivo com banco"):
            progresso = st.progress(0)

            def _progresso_live(atual: int, total: int) -> None:
                porcentagem = int((atual / total) * 100) if total else 100
                progresso.progress(min(max(porcentagem, 0), 100))

            try:
                with st.spinner("Sincronizando placares ao vivo com a API..."):
                    resumo_update = atualizar_jogos_copa(
                        executed_by_user_id=user_id,
                        progress_callback=_progresso_live,
                    )
            except BSDAPIError as exc:
                st.warning(f"Nao foi possivel sincronizar os placares ao vivo: {exc}")
            except PermissionError as exc:
                st.error(str(exc))
            except DatabaseError as exc:
                st.error(f"Erro ao sincronizar os jogos no banco: {exc}")
            else:
                progresso.progress(100)
                st.success(
                    f"{resumo_update['total_eventos']} eventos processados, "
                    f"{resumo_update['inseridos']} inseridos, "
                    f"{resumo_update['atualizados']} atualizados e "
                    f"{resumo_update['sem_alteracao']} sem alteracao."
                )
                st.write(
                    f"{resumo_update['finalizados']} jogos finalizados, "
                    f"{resumo_update['nao_mapeados']} com fase nao mapeada, "
                    f"{resumo_update['placeholders']} placeholders e "
                    f"{resumo_update['reais']} jogos reais."
                )
                if resumo_update["ranking_recalculado_executado"]:
                    st.info(
                        f"Ranking recalculado para {resumo_update['ranking_recalculado']} usuarios."
                    )
                else:
                    st.info("Nenhum jogo finalizado encontrado; ranking nao foi recalculado.")

    with aba_gabarito:
        st.subheader("Palpites especiais")
        abertos = get_especiais_abertos()
        estado_label = "🔓 Abertos" if abertos else "🔒 Fechados"
        st.info(f"Estado atual: **{estado_label}**")
        label_btn = "🔒 Fechar palpites especiais" if abertos else "🔓 Liberar palpites especiais"
        if st.button(label_btn, key="toggle_especiais"):
            set_especiais_abertos(not abertos)
            st.rerun()

        st.divider()
        st.subheader("Resultados oficiais")

        campeao_auto, vice_auto = _obter_campeao_vice_da_final()
        if campeao_auto:
            st.info(
                f"**Campeão detectado automaticamente da Final:** {campeao_auto}  \n"
                f"**Vice:** {vice_auto or '—'}"
            )
        else:
            st.info("Campeão e vice serão detectados automaticamente quando a Final for finalizada.")

        classificacao_atual = _obter_classificacao_grupos_oficial()
        grupos_completos = sum(
            1 for g, v in classificacao_atual.items()
            if not g.startswith("_") and v.get("primeiro") and v.get("segundo")
        )
        terceiros_detectados = len(classificacao_atual.get("_terceiros_classificados", []))
        st.info(
            f"**Classificação dos grupos detectada automaticamente** — "
            f"{grupos_completos}/12 grupos encerrados · "
            f"{terceiros_detectados}/8 terceiros classificados identificados."
        )

        oficiais = carregar_resultados_oficiais()
        jogadores_lista = listar_jogadores_copa()
        opcoes_jogadores = [""] + jogadores_lista

        def _indice_jogador(opcoes: list, valor: str) -> int:
            return opcoes.index(valor) if valor and valor in opcoes else 0

        with st.form("form_gabarito_oficial"):
            if jogadores_lista:
                artilheiro = st.selectbox(
                    "Artilheiro",
                    opcoes_jogadores,
                    index=_indice_jogador(opcoes_jogadores, oficiais.artilheiro or ""),
                    format_func=lambda v: "Selecione..." if not v else v,
                )
                melhor_jogador = st.selectbox(
                    "Melhor Jogador",
                    opcoes_jogadores,
                    index=_indice_jogador(opcoes_jogadores, oficiais.melhor_jogador or ""),
                    format_func=lambda v: "Selecione..." if not v else v,
                )
            else:
                st.info("Importe os jogadores primeiro para habilitar a seleção.")
                artilheiro = st.text_input("Artilheiro", value=oficiais.artilheiro or "")
                melhor_jogador = st.text_input("Melhor Jogador", value=oficiais.melhor_jogador or "")
            salvar = st.form_submit_button("Salvar gabarito oficial")

        if salvar:
            try:
                salvar_resultados_oficiais(
                    artilheiro=artilheiro,
                    melhor_jogador=melhor_jogador,
                    executed_by_user_id=user_id,
                )
            except PermissionError as exc:
                st.error(str(exc))
            else:
                st.success("Gabarito oficial salvo com sucesso.")

    with aba_usuarios:
        st.subheader("Aprovação de usuários")
        usuarios = listar_usuarios()
        pendentes = [usuario for usuario in usuarios if not getattr(usuario, "aprovado", True)]

        if not pendentes:
            st.success("Nenhum usuário pendente de aprovação.")
        else:
            for usuario in pendentes:
                col_nome, col_acao = st.columns([3, 1])
                col_nome.write(usuario.nome)
                if col_acao.button("Aprovar", key=f"aprovar_usuario_{usuario.id}"):
                    if aprovar_usuario(int(usuario.id)):
                        st.success(f"Usuário {usuario.nome} aprovado.")
                        st.rerun()
                    else:
                        st.error("Não foi possível aprovar o usuário.")

        if usuarios:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "ID": usuario.id,
                            "Nome": usuario.nome,
                            "Aprovado": "Sim" if getattr(usuario, "aprovado", True) else "Não",
                            "Admin": "Sim" if usuario.is_admin else "Não",
                            "Recuperacao": (
                                "Liberada"
                                if getattr(usuario, "troca_senha_liberada", False)
                                else "Solicitada"
                                if getattr(usuario, "recuperacao_senha_solicitada", False)
                                else "-"
                            ),
                            "Pontuação": usuario.pontuacao_total,
                        }
                        for usuario in usuarios
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()
        st.subheader("Solicitacoes de recuperacao de senha")
        solicitacoes = [
            usuario
            for usuario in usuarios
            if getattr(usuario, "recuperacao_senha_solicitada", False)
            and not getattr(usuario, "troca_senha_liberada", False)
        ]

        if not solicitacoes:
            st.success("Nenhuma solicitacao de recuperacao pendente.")
        else:
            for usuario in solicitacoes:
                col_nome, col_acao = st.columns([3, 1])
                col_nome.write(usuario.nome)
                if col_acao.button("Liberar troca", key=f"liberar_troca_senha_{usuario.id}"):
                    if liberar_troca_senha_usuario(int(usuario.id)):
                        st.success(f"Troca de senha liberada para {usuario.nome}.")
                        st.rerun()
                    else:
                        st.error("Nao foi possivel liberar a troca de senha.")

    with aba_preview:
        st.subheader("Jogos cadastrados")
        jogos = listar_jogos()
        if jogos:
            df_jogos = pd.DataFrame(
                [
                    {
                        "ID": jogo.id,
                        "API ID": jogo.api_id,
                        "Competicao": jogo.competicao,
                        "Fase": jogo.fase,
                        "Grupo": jogo.grupo,
                        "Round": jogo.round_number,
                        "Jogo": (
                            f"{render_team_identity_html(jogo.time_a, team_id=jogo.home_team_id, logo_url=jogo.home_team_logo_url)}"
                            f" <span style='opacity:.65;'>x</span> "
                            f"{render_team_identity_html(jogo.time_b, team_id=jogo.away_team_id, logo_url=jogo.away_team_logo_url)}"
                        ),
                        "Placar A": jogo.placar_a,
                        "Placar B": jogo.placar_b,
                        "Finalizado": jogo.finalizado,
                        "Status": jogo.status,
                        "Data": jogo.data_jogo,
                    }
                    for jogo in jogos
                ]
            )
            _render_html_table(df_jogos, class_name="wc-admin-table")
        else:
            st.info("Nenhum jogo cadastrado.")

        st.subheader("Classificacao atual")
        classificacao = carregar_classificacao_grupos()
        if classificacao:
            logo_lookup = construir_mapa_logos_por_jogos(jogos)
            df_classificacao = pd.DataFrame(
                [
                    {
                        "Grupo": item.grupo,
                        "Posicao": item.posicao,
                        "Time": render_team_identity_html(
                            item.time_nome,
                            team_id=(logo_lookup.get(normalizar_texto(item.time_nome), {}) or {}).get("team_id"),
                            logo_url=(logo_lookup.get(normalizar_texto(item.time_nome), {}) or {}).get("logo_url"),
                        ),
                        "Pontos": item.pontos,
                        "Jogos": item.jogos,
                        "Vitorias": item.vitorias,
                        "Empates": item.empates,
                        "Derrotas": item.derrotas,
                        "GP": item.gols_pro,
                        "GC": item.gols_contra,
                        "SG": item.saldo_gols,
                    }
                    for item in classificacao
                ]
            )
            _render_html_table(df_classificacao, class_name="wc-admin-table")
        else:
            st.info("A classificacao ainda nao foi calculada.")

    with aba_debug:
        st.subheader("Diagnostico de importacao")
        jogos = listar_jogos()
        if jogos:
            total_placeholders = sum(1 for jogo in jogos if getattr(jogo, "is_placeholder_bracket", False))
            contagem_fases = Counter(jogo.fase or FASE_NAO_MAPEADA for jogo in jogos)
            total = len(jogos)
            grupo = contagem_fases.get("Fase de Grupos", 0)
            mata_mata = total - grupo - contagem_fases.get(FASE_NAO_MAPEADA, 0)
            sem_fase = contagem_fases.get(FASE_NAO_MAPEADA, 0)
            reais = total - total_placeholders

            col_total, col_grupos, col_mata, col_sem, col_place, col_real = st.columns(6)
            col_total.metric("Total na UI", total)
            col_grupos.metric("Fase de Grupos", grupo)
            col_mata.metric("Mata-mata", max(mata_mata, 0))
            col_sem.metric("Sem fase mapeada", sem_fase)
            col_place.metric("Placeholders", total_placeholders)
            col_real.metric("Reais", reais)

            st.caption("Amostra dos 20 primeiros jogos importados por ID.")
            df_debug = pd.DataFrame(listar_jogos_importados_debug(20))
            if not df_debug.empty:
                df_debug["time_casa"] = df_debug.apply(
                    lambda linha: render_team_identity_html(
                        linha.get("time_casa_nome") or linha.get("time_casa"),
                        team_id=linha.get("home_team_id"),
                        logo_url=linha.get("home_team_logo_url"),
                    ),
                    axis=1,
                )
                df_debug["time_fora"] = df_debug.apply(
                    lambda linha: render_team_identity_html(
                        linha.get("time_fora_nome") or linha.get("time_fora"),
                        team_id=linha.get("away_team_id"),
                        logo_url=linha.get("away_team_logo_url"),
                    ),
                    axis=1,
                )
                df_debug = df_debug.drop(columns=["time_casa_nome", "time_fora_nome"], errors="ignore")
            _render_html_table(df_debug, class_name="wc-admin-table")
        else:
            st.info("Nenhum jogo importado ainda para depuracao.")
