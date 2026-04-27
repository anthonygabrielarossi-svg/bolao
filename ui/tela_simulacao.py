"""Tela de simulacao da Copa.

O usuario edita placares apenas na memoria da sessao. Nenhuma alteracao e
gravada no banco, nos palpites reais ou no ranking oficial.
"""

from __future__ import annotations

import html
from collections import defaultdict
from textwrap import dedent
from typing import Any, Dict, List, Optional

import streamlit as st

from database import FASE_NAO_MAPEADA, listar_jogos_por_fase
from services.simulacao_service import inicializar_simulacao_state, resetar_simulacao_state, resumir_simulacao
from utils.formatters import formatar_nome_time, normalizar_texto
from utils.team_assets import render_team_identity_html
from ui.tela_palpites import (
    _aplicar_estilos_palpites,
    _formatar_data_hora,
    _obter_grupo_jogo,
    _ordenar_jogos_grupo,
    _render_tabela_classificacao_grupo,
    atribuir_rodada_interna_grupo,
)


def _chave_jogo(jogo) -> int:
    if jogo.id is not None:
        return int(jogo.id)
    if jogo.api_id is not None:
        return int(jogo.api_id)
    return id(jogo)


def _limpar_estado_simulacao() -> None:
    chaves = [chave for chave in st.session_state.keys() if str(chave).startswith("simulacao_") or str(chave).startswith("sim_")]
    for chave in chaves:
        del st.session_state[chave]


def _normalizar_vencedor(valor: Any) -> Optional[str]:
    texto = str(valor or "").strip().lower()
    if texto == "mandante":
        return "home"
    if texto == "visitante":
        return "away"
    return None


def _montar_resultados_atuais(jogos_base: List, fallback: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    resultados: Dict[int, Dict[str, Any]] = {}
    for jogo in jogos_base:
        chave = _chave_jogo(jogo)
        padrao = fallback.get(chave, {})
        gols_casa = st.session_state.get(f"sim_gols_casa_{chave}", padrao.get("gols_casa"))
        gols_fora = st.session_state.get(f"sim_gols_fora_{chave}", padrao.get("gols_fora"))
        vencedor = None
        if gols_casa is not None and gols_fora is not None and int(gols_casa) == int(gols_fora):
            vencedor = _normalizar_vencedor(st.session_state.get(f"sim_vencedor_{chave}", padrao.get("vencedor_posicao")))
        resultados[chave] = {
            "gols_casa": int(gols_casa or 0),
            "gols_fora": int(gols_fora or 0),
            "vencedor_posicao": vencedor,
        }
    return resultados


def _nota_chaveamento(info: Dict[str, Any]) -> Optional[str]:
    observacao = info.get("observacao")
    if observacao:
        return str(observacao)
    if not info.get("resolvido", False):
        return "Dependente de combinacao ou resultado da chave."
    return None


def _render_jogo_simulado_card(jogo, resultados: Dict[int, Dict[str, Any]], chaveamento: Dict[int, Dict[str, Any]]) -> None:
    chave = _chave_jogo(jogo)
    resultado = resultados.get(chave, {})
    home_nome = formatar_nome_time(jogo.time_casa or jogo.time_a)
    away_nome = formatar_nome_time(jogo.time_fora or jogo.time_b)
    match_number = getattr(jogo, "match_number", None)
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
    score_home = int(resultado.get("gols_casa", jogo.gols_casa or 0) or 0)
    score_away = int(resultado.get("gols_fora", jogo.gols_fora or 0) or 0)
    tie = score_home == score_away

    meta = [
        f"📅 {html.escape(horario['data'])}",
        f"⏰ {html.escape(horario['hora'])}",
        f"Round {html.escape(str(jogo.round_number or '-'))}",
    ]
    if estadio:
        meta.append(f"🏟 {estadio}")

    st.markdown(
        dedent(
            f"""
            <div class="wc-match-card">
                <div class="wc-match-topline">
                    {"<span class=\"wc-match-number\">Jogo " + html.escape(str(match_number)) + "</span>" if match_number is not None else ""}
                    <span class="wc-status">{status}</span>
                    <span>{' · '.join(meta)}</span>
                </div>
                <div class="wc-match-teams">
                    {home_identity}
                    <span style="opacity:.65;"> x </span>
                    {away_identity}
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    col_home, col_away = st.columns(2)
    col_home.number_input(
        f"Gols do mandante - {home_nome}",
        min_value=0,
        max_value=20,
        step=1,
        value=score_home,
        key=f"sim_gols_casa_{chave}",
        label_visibility="collapsed",
    )
    col_away.number_input(
        f"Gols do visitante - {away_nome}",
        min_value=0,
        max_value=20,
        step=1,
        value=score_away,
        key=f"sim_gols_fora_{chave}",
        label_visibility="collapsed",
    )

    st.caption(f"Placar simulado: {score_home} x {score_away}")

    if tie and _is_mata_mata(jogo.fase):
        selecionado = st.selectbox(
            "Classificado nos penaltis",
            ["- Selecionar -", "Mandante", "Visitante"],
            index=_indice_vencedor(resultado.get("vencedor_posicao")),
            key=f"sim_vencedor_{chave}",
        )
        if selecionado == "Mandante":
            st.caption(f"Classificado: {home_nome}")
        elif selecionado == "Visitante":
            st.caption(f"Classificado: {away_nome}")
        else:
            st.warning("Empate simulado: selecione o classificado para a chave continuar.")
    elif tie:
        st.caption("Empate na fase de grupos.")

    info = chaveamento.get(chave)
    nota = _nota_chaveamento(info or {})
    if nota:
        st.caption(nota)


def _indice_vencedor(valor: Optional[str]) -> int:
    if valor == "home":
        return 1
    if valor == "away":
        return 2
    return 0


def _is_mata_mata(fase: Optional[str]) -> bool:
    fase_normalizada = normalizar_texto(fase)
    return fase_normalizada not in {normalizar_texto("Fase de Grupos"), normalizar_texto(FASE_NAO_MAPEADA)}


def _render_fase_grupos_simulacao(
    jogos: List,
    classificacao: Dict[str, List],
    resultados: Dict[int, Dict[str, Any]],
    chaveamento: Dict[int, Dict[str, Any]],
) -> None:
    jogos_por_grupo: Dict[str, List] = defaultdict(list)
    for jogo in jogos:
        grupo = _obter_grupo_jogo(jogo)
        if grupo:
            jogos_por_grupo[grupo].append(jogo)

    st.markdown("<div class='wc-phase-title'>Fase de Grupos</div>", unsafe_allow_html=True)
    st.caption("A tabela atualiza em tempo real conforme os placares simulados mudam.")

    for grupo_label in sorted(jogos_por_grupo.keys()):
        jogos_grupo = _ordenar_jogos_grupo(jogos_por_grupo.get(grupo_label, []))
        st.markdown(f"<div class='wc-group-title'>{grupo_label.upper()}</div>", unsafe_allow_html=True)
        st.caption(f"{len(jogos_grupo)} jogos neste grupo.")

        with st.container():
            col_classificacao, col_jogos = st.columns([1.15, 1.85], gap="large")
            with col_classificacao:
                _render_tabela_classificacao_grupo(grupo_label, classificacao, jogos_referencia=jogos_grupo)
            with col_jogos:
                jogos_ordenados, jogos_por_rodada = atribuir_rodada_interna_grupo(jogos_grupo)
                tabs = st.tabs(["1ª Rodada", "2ª Rodada", "3ª Rodada"])
                for idx, rodada in enumerate((1, 2, 3)):
                    with tabs[idx]:
                        jogos_rodada = _ordenar_jogos_grupo(jogos_por_rodada.get(rodada, []))
                        if not jogos_rodada:
                            st.info("Nenhum jogo encontrado para esta rodada.")
                        else:
                            for jogo in jogos_rodada:
                                _render_jogo_simulado_card(jogo, resultados, chaveamento)

        st.divider()


def _render_fase_simples_simulacao(
    fase: str,
    jogos: List,
    resultados: Dict[int, Dict[str, Any]],
    chaveamento: Dict[int, Dict[str, Any]],
) -> None:
    if not jogos:
        return

    with st.expander(fase, expanded=False):
        for jogo in _ordenar_jogos_grupo(jogos):
            _render_jogo_simulado_card(jogo, resultados, chaveamento)


def render_tela_simulacao() -> None:
    """Renderiza a pagina de simulacao isolada."""
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
        .wc-sim-topbar {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-bottom: 1rem;
        }
        .wc-match-number {
            display: inline-flex;
            align-items: center;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            background: rgba(14, 165, 233, 0.14);
            border: 1px solid rgba(14, 165, 233, 0.28);
            color: #7dd3fc;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='wc-page-title'>Simulação da Copa do Mundo</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='wc-page-subtitle'>Simule placares, classificados e chaveamento sem afetar os dados oficiais.</div>",
        unsafe_allow_html=True,
    )
    st.caption("Os jogos sem ajuste partem de 0 x 0. Edite os placares para testar cenarios diferentes.")

    jogos_reais = listar_jogos_por_fase()
    if not jogos_reais:
        st.info("Nenhum jogo cadastrado ainda.")
        return

    if "simulacao_jogos" not in st.session_state:
        st.session_state.update(inicializar_simulacao_state(jogos_reais))

    col_reset, col_real = st.columns(2)
    if col_reset.button("Resetar simulação", use_container_width=True):
        _limpar_estado_simulacao()
        st.session_state.update(resetar_simulacao_state(jogos_reais))
        st.rerun()

    if col_real.button("Carregar resultados reais atuais", use_container_width=True):
        _limpar_estado_simulacao()
        st.session_state.update(inicializar_simulacao_state(jogos_reais))
        st.rerun()

    resultados_atuais = _montar_resultados_atuais(
        st.session_state.get("simulacao_jogos", jogos_reais),
        st.session_state.get("simulacao_resultados", {}),
    )
    estado_simulado = resumir_simulacao(jogos_reais, resultados_atuais)
    st.session_state.update(estado_simulado)

    chaveamento = estado_simulado.get("simulacao_chaveamento", {})
    classificacao = estado_simulado.get("simulacao_classificacao", {})
    classificados = estado_simulado.get("simulacao_classificados", {})
    melhores_terceiros = estado_simulado.get("simulacao_melhores_terceiros", [])

    pendencias = sum(1 for info in chaveamento.values() if not info.get("resolvido", False))
    classificados_diretos = sum(len(valores) for valores in classificados.values())
    classificados_totais = classificados_diretos + len(melhores_terceiros)
    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric("Grupos calculados", len(classificacao))
    with metric_cols[1]:
        st.metric("Classificados diretos", classificados_diretos)
    with metric_cols[2]:
        st.metric("Total para 16-avos", classificados_totais)
    with metric_cols[3]:
        st.metric("Chaveamentos pendentes", pendencias)

    if pendencias:
        pendentes = [
            f"{chave}: {info.get('observacao') or 'Dependente de combinacao/resultado'}"
            for chave, info in chaveamento.items()
            if not info.get("resolvido", False)
        ]
        st.info("Alguns confrontos ainda dependem da combinacao dos melhores terceiros ou de resultados futuros.")
        st.caption(" | ".join(pendentes[:6]))

    debug_logs = estado_simulado.get("simulacao_debug_chaveamento", [])
    if debug_logs:
        with st.expander("Diagnóstico do chaveamento", expanded=False):
            st.code("\n".join(debug_logs), language="text")

    jogos_resolvidos = estado_simulado.get("simulacao_jogos_resolvidos", [])
    jogos_por_fase: Dict[str, List] = defaultdict(list)
    for jogo in jogos_resolvidos:
        jogos_por_fase[jogo.fase or FASE_NAO_MAPEADA].append(jogo)

    jogos_fase_grupos = jogos_por_fase.get("Fase de Grupos", [])
    if jogos_fase_grupos:
        _render_fase_grupos_simulacao(jogos_fase_grupos, classificacao, resultados_atuais, chaveamento)
    else:
        st.info("Nenhum jogo da Fase de Grupos cadastrado ainda.")

    fases_ordenadas = [
        "16-avos de Final",
        "Oitavas de Final",
        "Quartas de Final",
        "Semifinal",
        "Disputa de 3º Lugar",
        "Final",
    ]
    for fase in fases_ordenadas:
        _render_fase_simples_simulacao(fase, jogos_por_fase.get(fase, []), resultados_atuais, chaveamento)

    if jogos_por_fase.get(FASE_NAO_MAPEADA):
        _render_fase_simples_simulacao(FASE_NAO_MAPEADA, jogos_por_fase.get(FASE_NAO_MAPEADA, []), resultados_atuais, chaveamento)
