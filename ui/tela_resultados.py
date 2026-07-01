"""Tela de resultados oficiais da Copa."""

from __future__ import annotations

import html
from collections import defaultdict
from textwrap import dedent
from typing import Dict, List, Optional

import streamlit as st

from database import FASE_NAO_MAPEADA, listar_jogos_por_fase
from services.classificacao_service import listar_classificacao_real_agrupada
from utils.formatters import formatar_nome_time, normalizar_texto
from utils.world_cup import WORLD_CUP_GROUPS_2026, inferir_grupo_por_times
from utils.team_assets import render_team_identity_html
from ui.tela_palpites import (
    _aplicar_estilos_palpites,
    _formatar_data_hora,
    _ordenar_jogos_grupo,
    _render_tabela_classificacao_grupo,
    atribuir_rodada_interna_grupo,
)


def _obter_grupo_jogo(jogo) -> Optional[str]:
    grupo = getattr(jogo, "grupo", None)
    if grupo:
        return str(grupo).strip().upper().replace("GRUPO ", "Grupo ")
    return inferir_grupo_por_times(jogo.time_casa or jogo.time_a, jogo.time_fora or jogo.time_b)


def _vencedor_real(jogo) -> str:
    casa = jogo.gols_casa if jogo.gols_casa is not None else jogo.placar_a
    fora = jogo.gols_fora if jogo.gols_fora is not None else jogo.placar_b
    if casa is None or fora is None:
        return ""
    if int(casa) > int(fora):
        return formatar_nome_time(jogo.time_casa or jogo.time_a)
    if int(fora) > int(casa):
        return formatar_nome_time(jogo.time_fora or jogo.time_b)
    return "Empate"


def _render_jogo_resultado_card(jogo) -> None:
    home_nome = formatar_nome_time(jogo.time_casa or jogo.time_a)
    away_nome = formatar_nome_time(jogo.time_fora or jogo.time_b)
    home_identity = render_team_identity_html(
        jogo.time_casa or jogo.time_a,
        team_id=getattr(jogo, "home_team_id", None),
        logo_url=getattr(jogo, "home_team_logo_url", None),
    )
    away_identity = render_team_identity_html(
        jogo.time_fora or jogo.time_b,
        team_id=getattr(jogo, "away_team_id", None),
        logo_url=getattr(jogo, "away_team_logo_url", None),
    )
    horario = _formatar_data_hora(jogo.data_jogo)
    estadio = html.escape(str(getattr(jogo, "estadio", "") or "").strip())
    status = html.escape(str(jogo.status or "").strip() or "-")
    round_label = f"{jogo.round_number or '-'}"

    casa = jogo.gols_casa if jogo.gols_casa is not None else jogo.placar_a
    fora = jogo.gols_fora if jogo.gols_fora is not None else jogo.placar_b
    if casa is None or fora is None:
        placar = "Aguardando resultado"
    else:
        placar = f"{int(casa)} x {int(fora)}"

    vencedor = _vencedor_real(jogo)

    meta = [
        f"📅 {html.escape(horario['data'])}",
        f"⏰ {html.escape(horario['hora'])}",
        f"Round {html.escape(round_label)}",
    ]
    if estadio:
        meta.append(f"🏟 {estadio}")

    st.markdown(
        dedent(
            f"""
            <div class="wc-match-card">
                <div class="wc-match-topline">
                    <span class="wc-status">{status}</span>
                    <span>{' · '.join(meta)}</span>
                </div>
                <div class="wc-match-teams">
                    {home_identity}
                    <span style="opacity:.65;"> x </span>
                    {away_identity}
                </div>
                <div class="wc-result-score">{html.escape(placar)}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    if vencedor:
        st.caption(f"Vencedor: {vencedor}")
    elif casa is None or fora is None:
        st.caption("Aguardando resultado")

    if normalizar_texto(jogo.status) in {"finished", "ft", "fulltime", "full time", "complete", "completed", "final"}:
        st.markdown("<div class='wc-match-closed'>Finalizado</div>", unsafe_allow_html=True)


def _render_jogos_rodada_resultados(grupo_label: str, rodada: int, jogos_rodada: List) -> None:
    if not jogos_rodada:
        st.info("Nenhum jogo encontrado para esta rodada.")
        return

    st.markdown(f"<div class='wc-round-label'>{rodada}ª rodada</div>", unsafe_allow_html=True)
    for jogo in jogos_rodada:
        _render_jogo_resultado_card(jogo)


def _render_fase_grupos_resultados(jogos: List) -> None:
    jogos_por_grupo: Dict[str, List] = defaultdict(list)
    for jogo in jogos:
        grupo = _obter_grupo_jogo(jogo)
        if grupo:
            jogos_por_grupo[grupo].append(jogo)

    st.markdown("<div class='wc-phase-title'>Fase de Grupos</div>", unsafe_allow_html=True)
    st.caption("Resultados reais oficiais da fase de grupos.")

    for grupo_label in sorted(jogos_por_grupo.keys()):
        jogos_grupo = _ordenar_jogos_grupo(jogos_por_grupo.get(grupo_label, []))
        st.markdown(f"<div class='wc-group-title'>{grupo_label.upper()}</div>", unsafe_allow_html=True)
        st.caption(f"{len(jogos_grupo)} jogos neste grupo.")

        with st.container():
            _, jogos_por_rodada = atribuir_rodada_interna_grupo(jogos_grupo)
            tabs = st.tabs(["1ª Rodada", "2ª Rodada", "3ª Rodada"])
            for idx, rodada in enumerate((1, 2, 3)):
                with tabs[idx]:
                    _render_jogos_rodada_resultados(grupo_label, rodada, jogos_por_rodada.get(rodada, []))

        st.divider()


def _render_fase_grupos_resultados_com_classificacao_real(jogos: List, classificacao_agrupada: Dict[str, List]) -> None:
    jogos_por_grupo: Dict[str, List] = {grupo: [] for grupo in WORLD_CUP_GROUPS_2026.keys()}
    for jogo in jogos:
        grupo = _obter_grupo_jogo(jogo)
        if grupo:
            jogos_por_grupo[grupo].append(jogo)

    st.markdown("<div class='wc-phase-title'>Fase de Grupos</div>", unsafe_allow_html=True)
    st.caption("Resultados reais oficiais da fase de grupos e classificacao real calculada apenas com jogos finalizados.")

    for grupo_label in WORLD_CUP_GROUPS_2026.keys():
        jogos_grupo = _ordenar_jogos_grupo(jogos_por_grupo.get(grupo_label, []))
        st.markdown(f"<div class='wc-group-title'>{grupo_label.upper()}</div>", unsafe_allow_html=True)
        st.caption(f"{len(jogos_grupo)} jogos neste grupo.")

        with st.container():
            col_classificacao, col_jogos = st.columns([1.2, 1], gap="large")
            with col_classificacao:
                st.caption("Tabela de classificacao real baseada apenas em resultados oficiais.")
                _render_tabela_classificacao_grupo(grupo_label, classificacao_agrupada, jogos_referencia=jogos_grupo)
            with col_jogos:
                _, jogos_por_rodada = atribuir_rodada_interna_grupo(jogos_grupo)
                tabs = st.tabs(["1Âª Rodada", "2Âª Rodada", "3Âª Rodada"])
                for idx, rodada in enumerate((1, 2, 3)):
                    with tabs[idx]:
                        _render_jogos_rodada_resultados(grupo_label, rodada, jogos_por_rodada.get(rodada, []))

        st.divider()


def _render_fase_simples_resultados(fase: str, jogos: List) -> None:
    if not jogos:
        return

    fase_exibicao = fase
    with st.expander(fase_exibicao, expanded=False):
        for jogo in _ordenar_jogos_grupo(jogos):
            _render_jogo_resultado_card(jogo)


def render_tela_resultados() -> None:
    """Renderiza a pagina somente leitura de resultados."""
    _aplicar_estilos_palpites()
    st.markdown(
        """
        <style>
        .wc-result-score {
            margin-top: 0.65rem;
            font-size: 1.08rem;
            font-weight: 900;
            letter-spacing: 0.03em;
            color: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='wc-page-title'>Resultados da Copa do Mundo</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='wc-page-subtitle'>Veja apenas os resultados reais oficiais dos jogos da Copa.</div>",
        unsafe_allow_html=True,
    )

    _fases_grupo = {"Fase de Grupos", FASE_NAO_MAPEADA}
    jogos = [
        j for j in listar_jogos_por_fase()
        if not getattr(j, "is_placeholder_bracket", False)
        and (
            (j.fase or FASE_NAO_MAPEADA) in _fases_grupo
            or getattr(j, "api_id", None) is not None
        )
    ]
    if not jogos:
        st.info("Nenhum jogo cadastrado ainda.")
        return

    classificacao_agrupada = listar_classificacao_real_agrupada()
    jogos_por_fase: Dict[str, List] = defaultdict(list)
    for jogo in jogos:
        jogos_por_fase[jogo.fase or FASE_NAO_MAPEADA].append(jogo)

    jogos_fase_grupos = jogos_por_fase.get("Fase de Grupos", [])
    if jogos_fase_grupos:
        _render_fase_grupos_resultados_com_classificacao_real(jogos_fase_grupos, classificacao_agrupada)
    else:
        st.info("Nenhum jogo da Fase de Grupos cadastrado ainda.")

    fases_ordenadas = [
        fase
        for fase in [
            "16-avos de Final",
            "Oitavas de Final",
            "Quartas de Final",
            "Semifinal",
            "Disputa de 3º Lugar",
            "Final",
        ]
    ]
    for fase in fases_ordenadas:
        _render_fase_simples_resultados(fase, jogos_por_fase.get(fase, []))

    if jogos_por_fase.get(FASE_NAO_MAPEADA):
        _render_fase_simples_resultados(FASE_NAO_MAPEADA, jogos_por_fase.get(FASE_NAO_MAPEADA, []))
