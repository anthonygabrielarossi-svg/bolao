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
    get_database_kind,
    listar_usuarios,
    listar_jogos,
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
    importar_jogos_copa,
    listar_jogos_importados_debug,
)
from services.ranking_service import recalcular_ranking_automaticamente
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
            try:
                atualizados = atualizar_resultados(executed_by_user_id=user_id)
                classificacao = atualizar_tabela_classificacao(executed_by_user_id=user_id)
                mata_mata = gerar_mata_mata_automatico(executed_by_user_id=user_id)
                ranking = recalcular_ranking_automaticamente(executed_by_user_id=user_id)
            except BSDAPIError as exc:
                st.warning(f"Nao foi possivel consultar a API de resultados: {exc}")
            except PermissionError as exc:
                st.error(str(exc))
            except DatabaseError as exc:
                st.error(f"Erro ao atualizar o banco: {exc}")
            else:
                st.success(
                    f"{atualizados} resultados atualizados, {len(classificacao)} linhas de classificacao, "
                    f"{mata_mata} jogos de mata-mata gerados e {len(ranking)} usuarios recalculados."
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
        st.subheader("Resultados oficiais")
        oficiais = carregar_resultados_oficiais()
        with st.form("form_gabarito_oficial"):
            campeao = st.text_input("Campeao", value=oficiais.campeao)
            vice = st.text_input("Vice", value=oficiais.vice)
            artilheiro = st.text_input("Artilheiro", value=oficiais.artilheiro)
            melhor_jogador = st.text_input("Melhor Jogador", value=oficiais.melhor_jogador)
            primeiro_grupo_a = st.text_input("1o colocado do Grupo A", value=oficiais.primeiro_grupo_a)
            segundo_grupo_a = st.text_input("2o colocado do Grupo A", value=oficiais.segundo_grupo_a)
            salvar = st.form_submit_button("Salvar gabarito oficial")

        if salvar:
            try:
                salvar_resultados_oficiais(
                    campeao=campeao,
                    vice=vice,
                    artilheiro=artilheiro,
                    melhor_jogador=melhor_jogador,
                    primeiro_grupo_a=primeiro_grupo_a,
                    segundo_grupo_a=segundo_grupo_a,
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
                            "Pontuação": usuario.pontuacao_total,
                        }
                        for usuario in usuarios
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

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
