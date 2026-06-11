"""Tela de palpites.

Esta tela exibe jogos agrupados por fase e permite salvar palpites de partidas e
palpites especiais sem acessar o SQLite diretamente.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from collections import defaultdict
from textwrap import dedent
from typing import Any, Dict, List, Optional

import streamlit as st

from database import (
    FASE_NAO_MAPEADA,
    carregar_palpites_especiais,
    carregar_palpites_partidas,
    listar_jogadores_copa,
    obter_times_por_grupo,
    salvar_palpites_especiais,
    salvar_palpites_partida,
    FASES_VALIDAS_COPA,
)
from services.jogos_service import listar_jogos_por_fase
from utils.datetime_utils import bloquear_palpite_para_jogo, jogo_ja_comecou
from utils.formatters import formatar_nome_time, normalizar_texto
from utils.team_assets import construir_mapa_logos_por_jogos, render_team_identity_html
from utils.world_cup import (
    WORLD_CUP_GROUPS_2026,
    inferir_grupo_por_times,
    normalizar_grupo_copa,
    obter_times_do_grupo,
)


def _copa_ja_comecou(jogos: List) -> bool:
    """Retorna True quando o primeiro jogo da Copa já iniciou."""
    datas = [
        getattr(j, "data_jogo", None)
        for j in jogos
        if getattr(j, "data_jogo", None)
    ]
    if not datas:
        return False
    return jogo_ja_comecou(min(datas))


def _vencedor_previsto(time_a: str, time_b: str, palpite_a: int, palpite_b: int) -> str:
    if palpite_a > palpite_b:
        return time_a
    if palpite_b > palpite_a:
        return time_b
    return "Empate"


def _palpite_bloqueado(jogo) -> bool:
    return bloquear_palpite_para_jogo(jogo)


def _aplicar_estilos_palpites() -> None:
    st.markdown(
        dedent(
            """
        <style>
        .wc-page-title {
            font-size: 2.1rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            margin-bottom: 0.25rem;
        }

        .wc-page-subtitle {
            color: rgba(255, 255, 255, 0.72);
            margin-bottom: 1.25rem;
        }

        .wc-phase-title {
            margin-top: 2.1rem;
            margin-bottom: 0.4rem;
            font-size: 1.5rem;
            font-weight: 800;
            letter-spacing: 0.02em;
        }

        .wc-group-shell {
            padding: 1rem 0 0.35rem 0;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        }

        .wc-group-title {
            font-size: 1.35rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin: 0.15rem 0 0.65rem 0;
        }

        .wc-group-note {
            color: rgba(255, 255, 255, 0.65);
            margin-bottom: 0.9rem;
        }

        .wc-table-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.03));
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 18px;
            padding: 0.95rem;
            box-shadow: 0 14px 35px rgba(0, 0, 0, 0.16);
        }

        .wc-table-title {
            font-size: 0.95rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.75rem;
            color: rgba(255, 255, 255, 0.82);
        }

        table.wc-standings-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }

        .wc-standings-table thead th {
            text-align: left;
            padding: 0.55rem 0.45rem;
            color: rgba(255, 255, 255, 0.72);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            white-space: nowrap;
        }

        .wc-standings-table tbody td {
            padding: 0.5rem 0.45rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            vertical-align: middle;
        }

        .wc-standings-table tbody tr:nth-child(1),
        .wc-standings-table tbody tr:nth-child(2) {
            background: rgba(70, 145, 255, 0.08);
        }

        .wc-standings-team {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            font-weight: 700;
        }

        .wc-standings-pos {
            width: 1.5rem;
            color: rgba(255, 255, 255, 0.82);
            font-weight: 800;
        }

        .wc-standings-flag {
            font-size: 1.05rem;
        }

        .wc-flag {
            font-size: 1.2rem;
            margin-right: 6px;
        }

        .wc-team-identity {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            min-width: 0;
        }

        .wc-team-flag-img {
            width: 1.6rem;
            height: 1.07rem;
            object-fit: cover;
            border-radius: 2px;
            flex-shrink: 0;
            display: inline-block;
            vertical-align: middle;
        }

        .wc-team-logo {
            width: 1.18rem;
            height: 1.18rem;
            object-fit: contain;
            flex: 0 0 auto;
        }

        .wc-team-name {
            min-width: 0;
        }

        .wc-round-label {
            margin: 0.9rem 0 0.55rem 0;
            font-size: 0.84rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: rgba(255, 255, 255, 0.7);
        }

        .wc-match-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.09);
            border-radius: 16px;
            padding: 0.9rem 0.95rem;
            margin-bottom: 0.75rem;
        }

        .wc-salvo-badge {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            margin-top: 0.55rem;
            padding: 0.38rem 0.75rem;
            border-radius: 8px;
            font-size: 0.82rem;
            width: 100%;
            box-sizing: border-box;
        }
        .wc-salvo-ok {
            background: rgba(34,197,94,0.1);
            border: 1px solid rgba(34,197,94,0.3);
            color: #86efac;
        }
        .wc-salvo-warn {
            background: rgba(234,179,8,0.1);
            border: 1px solid rgba(234,179,8,0.3);
            color: #fde047;
        }
        .wc-salvo-erro {
            background: rgba(239,68,68,0.08);
            border: 1px solid rgba(239,68,68,0.2);
            color: rgba(255,255,255,0.45);
        }

        .wc-match-closed {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            margin-top: 0.55rem;
            padding: 0.25rem 0.65rem;
            border-radius: 999px;
            background: rgba(239, 68, 68, 0.14);
            color: #fecaca;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .wc-match-topline {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 0.35rem;
            color: rgba(255, 255, 255, 0.75);
            font-size: 0.82rem;
        }

        .wc-match-teams {
            font-size: 1.02rem;
            font-weight: 800;
            line-height: 1.35;
            margin-bottom: 0.25rem;
        }

        .wc-match-meta {
            color: rgba(255, 255, 255, 0.68);
            font-size: 0.82rem;
            margin-bottom: 0.55rem;
        }

        .wc-status {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.15rem 0.55rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.08);
            font-weight: 700;
        }

        .wc-score-col {
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 0.15rem 0.35rem 0.35rem 0.35rem;
        }

        div[data-baseweb="tab-list"] {
            gap: 0.45rem;
            margin-bottom: 0.8rem;
            flex-wrap: wrap;
        }

        button[data-baseweb="tab"] {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 999px;
            padding: 0.45rem 0.9rem;
            color: rgba(255, 255, 255, 0.78);
            font-weight: 700;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, rgba(70, 145, 255, 0.3), rgba(70, 145, 255, 0.14));
            color: #ffffff;
            border-color: rgba(70, 145, 255, 0.42);
        }
        </style>
        """
        ),
        unsafe_allow_html=True,
    )


def _formatar_data_hora(data_iso: Optional[str]) -> Dict[str, str]:
    if not data_iso:
        return {"data": "-", "hora": "-"}

    texto = str(data_iso).strip()
    try:
        data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return {"data": texto, "hora": "-"}

    return {
        "data": data.strftime("%d/%m/%Y"),
        "hora": data.strftime("%H:%M"),
    }


def _percentual_aproveitamento(pontos: int, jogos: int) -> str:
    if jogos <= 0:
        return "0%"
    percentual = (pontos / (jogos * 3)) * 100
    return f"{percentual:.0f}%"


def _rotulo_fase_exibicao(fase: str) -> str:
    if normalizar_texto(fase) == normalizar_texto(FASE_NAO_MAPEADA):
        return FASE_NAO_MAPEADA
    return fase


def _obter_grupo_jogo(jogo) -> Optional[str]:
    grupo = normalizar_grupo_copa(jogo.grupo)
    if grupo:
        return grupo
    return inferir_grupo_por_times(jogo.time_a, jogo.time_b)


def _ordenar_jogos_grupo(jogos: List) -> List:
    return sorted(
        jogos,
        key=lambda jogo: (
            jogo.round_number or 0,
            jogo.data_jogo or "",
            jogo.id or 0,
        ),
    )


def montar_html_tabela_classificacao(times: List[Dict[str, Any]]) -> str:
    linhas_html = ""
    for time in times:
        linhas_html += (
            f'<tr>'
            f'<td><div class="wc-standings-team">'
            f'<span class="wc-standings-pos">{html.escape(str(time.get("posicao", 0)))}</span>'
            f'{time.get("identity_html") or render_team_identity_html(str(time.get("nome", "")))}'
            f'</div></td>'
            f'<td>{html.escape(str(time.get("pontos", 0)))}</td>'
            f'<td>{html.escape(str(time.get("jogos", 0)))}</td>'
            f'<td>{html.escape(str(time.get("vitorias", 0)))}</td>'
            f'<td>{html.escape(str(time.get("empates", 0)))}</td>'
            f'<td>{html.escape(str(time.get("derrotas", 0)))}</td>'
            f'<td>{html.escape(str(time.get("gols_pro", 0)))}</td>'
            f'<td>{html.escape(str(time.get("gols_contra", 0)))}</td>'
            f'<td>{html.escape(str(time.get("saldo", 0)))}</td>'
            f'<td>{html.escape(str(time.get("percentual", "0%")))}</td>'
            f'</tr>'
        )

    return dedent(
        f"""
        <div class="wc-table-card">
            <div class="wc-table-title">Tabela de classificação</div>
            <table class="wc-standings-table">
                <thead>
                    <tr>
                        <th>Classificação</th>
                        <th>P</th>
                        <th>J</th>
                        <th>V</th>
                        <th>E</th>
                        <th>D</th>
                        <th>GP</th>
                        <th>GC</th>
                        <th>SG</th>
                        <th>%</th>
                    </tr>
                </thead>
                <tbody>
                    {linhas_html}
                </tbody>
            </table>
        </div>
        """
    ).strip()


def render_tabela_classificacao(times: List[Dict[str, Any]]) -> None:
    html_tabela = montar_html_tabela_classificacao(times)
    st.markdown(html_tabela, unsafe_allow_html=True)


def _render_tabela_classificacao_grupo(
    grupo_label: str,
    classificacao_agrupada: Dict[str, List],
    jogos_referencia: Optional[List] = None,
) -> None:
    rows = classificacao_agrupada.get(grupo_label, [])
    rows_por_time = {normalizar_texto(item.time_nome): item for item in rows}
    times_base = list(obter_times_do_grupo(grupo_label))
    if not times_base:
        times_base = [item.time_nome for item in rows]
    logo_lookup = construir_mapa_logos_por_jogos(jogos_referencia or [])

    times_para_tabela: List[Dict[str, Any]] = []
    for posicao, time_nome in enumerate(times_base, start=1):
        item = rows_por_time.get(normalizar_texto(time_nome))
        team_info = logo_lookup.get(normalizar_texto(time_nome), {})
        pontos = item.pontos if item else 0
        jogos = item.jogos if item else 0
        vitorias = item.vitorias if item else 0
        empates = item.empates if item else 0
        derrotas = item.derrotas if item else 0
        gols_pro = item.gols_pro if item else 0
        gols_contra = item.gols_contra if item else 0
        saldo = item.saldo_gols if item else 0
        percentual = _percentual_aproveitamento(pontos, jogos)
        times_para_tabela.append(
            {
                "posicao": posicao,
                "identity_html": render_team_identity_html(
                    time_nome,
                    team_id=team_info.get("team_id"),
                    logo_url=team_info.get("logo_url"),
                ),
                "nome": formatar_nome_time(time_nome),
                "pontos": pontos,
                "jogos": jogos,
                "vitorias": vitorias,
                "empates": empates,
                "derrotas": derrotas,
                "gols_pro": gols_pro,
                "gols_contra": gols_contra,
                "saldo": saldo,
                "percentual": percentual,
            }
        )

    render_tabela_classificacao(times_para_tabela)


def _render_jogo_card(
    user_id: int,
    jogo,
    jogo_id: int,
    palpite_atual: Dict[str, int],
) -> None:
    home_nome = formatar_nome_time(jogo.time_casa or jogo.time_a)
    away_nome = formatar_nome_time(jogo.time_fora or jogo.time_b)
    tem_palpite_salvo = "palpite_a" in palpite_atual
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
    bloqueado = _palpite_bloqueado(jogo)

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
        </div>
            """
        ),
        unsafe_allow_html=True,
    )
    if bloqueado:
        st.markdown("<div class='wc-match-closed'>Palpite encerrado</div>", unsafe_allow_html=True)

    col_home, col_away = st.columns(2)
    palpite_a = col_home.number_input(
        f"Gols de {home_nome}",
        min_value=0,
        max_value=20,
        step=1,
        value=int(palpite_atual.get("palpite_a", 0)),
        key=f"palpite_casa_{jogo_id}",
        label_visibility="collapsed",
        disabled=bloqueado,
    )
    palpite_b = col_away.number_input(
        f"Gols de {away_nome}",
        min_value=0,
        max_value=20,
        step=1,
        value=int(palpite_atual.get("palpite_b", 0)),
        key=f"palpite_fora_{jogo_id}",
        label_visibility="collapsed",
        disabled=bloqueado,
    )

    st.caption(
        f"Vencedor previsto: {_vencedor_previsto(home_nome, away_nome, int(palpite_a), int(palpite_b))}"
    )

    if st.button("Salvar palpite", key=f"salvar_palpite_{jogo_id}", disabled=bloqueado):
        try:
            salvar_palpites_partida(
                user_id=user_id,
                match_id=jogo_id,
                palpite_a=int(palpite_a),
                palpite_b=int(palpite_b),
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("Palpite salvo com sucesso.")

    if tem_palpite_salvo:
        p_a = int(palpite_atual["palpite_a"])
        p_b = int(palpite_atual["palpite_b"])
        st.markdown(
            f'<div class="wc-salvo-badge wc-salvo-ok">'
            f'💾 Salvo no banco: <strong>{html.escape(home_nome)} {p_a} × {p_b} {html.escape(away_nome)}</strong>'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif not bloqueado:
        st.markdown(
            '<div class="wc-salvo-badge wc-salvo-warn">'
            '⚠️ Nenhum palpite salvo para este jogo'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="wc-salvo-badge wc-salvo-erro">'
            '⚠️ Sem palpite salvo — jogo encerrado'
            '</div>',
            unsafe_allow_html=True,
        )


def _parse_data_jogo_para_ordem(jogo) -> tuple:
    data_iso = getattr(jogo, "data_jogo", None)
    if not data_iso:
        return (1, float("inf"), int(getattr(jogo, "id", 0) or 0))

    try:
        data_jogo = datetime.fromisoformat(str(data_iso).replace("Z", "+00:00"))
    except ValueError:
        return (1, float("inf"), int(getattr(jogo, "id", 0) or 0))

    if data_jogo.tzinfo is None:
        data_jogo = data_jogo.replace(tzinfo=timezone.utc)

    return (0, data_jogo.timestamp(), int(getattr(jogo, "id", 0) or 0))


def atribuir_rodada_interna_grupo(jogos_grupo: List) -> tuple[List, Dict[int, List]]:
    jogos_ordenados = sorted(jogos_grupo, key=_parse_data_jogo_para_ordem)
    jogos_por_rodada: Dict[int, List] = defaultdict(list)
    for idx, jogo in enumerate(jogos_ordenados):
        rodada_grupo = (idx // 2) + 1
        jogos_por_rodada[rodada_grupo].append(jogo)
    return jogos_ordenados, jogos_por_rodada


def _render_jogos_rodada_grupo(
    user_id: int,
    grupo_label: str,
    rodada: int,
    jogos_rodada: List,
    palpites_partidas: Dict[int, Dict[str, int]],
) -> None:
    if not jogos_rodada:
        st.info("Nenhum jogo encontrado para esta rodada.")
        return

    st.markdown(f"<div class='wc-round-label'>{rodada}ª rodada</div>", unsafe_allow_html=True)
    for indice, jogo in enumerate(jogos_rodada, start=1):
        jogo_id = jogo.id if jogo.id is not None else int(f"{rodada}{indice}")
        palpite_atual = palpites_partidas.get(jogo_id, {})
        _render_jogo_card(
            user_id=user_id,
            jogo=jogo,
            jogo_id=jogo_id,
            palpite_atual=palpite_atual,
        )


def render_abas_rodadas_grupo(
    user_id: int,
    grupo_label: str,
    jogos_grupo: List,
    palpites_partidas: Dict[int, Dict[str, int]],
) -> None:
    tabs = st.tabs(["1ª Rodada", "2ª Rodada", "3ª Rodada"])
    jogos_grupo, jogos_por_rodada = atribuir_rodada_interna_grupo(jogos_grupo)

    for idx, rodada in enumerate((1, 2, 3)):
        with tabs[idx]:
            jogos_rodada = _ordenar_jogos_grupo(jogos_por_rodada.get(rodada, []))
            _render_jogos_rodada_grupo(
                user_id=user_id,
                grupo_label=grupo_label,
                rodada=rodada,
                jogos_rodada=jogos_rodada,
                palpites_partidas=palpites_partidas,
            )


def _render_fase_grupos(
    user_id: int,
    jogos: List,
    palpites_partidas: Dict[int, Dict[str, int]],
) -> None:
    jogos_por_grupo: Dict[str, List] = defaultdict(list)
    jogos_sem_grupo: List = []

    for jogo in jogos:
        grupo = _obter_grupo_jogo(jogo)
        if grupo:
            jogos_por_grupo[grupo].append(jogo)
        else:
            jogos_sem_grupo.append(jogo)

    st.markdown("<div class='wc-phase-title'>Fase de Grupos</div>", unsafe_allow_html=True)
    st.caption("Apenas os jogos para palpitar, organizados por grupo e rodada.")

    for grupo_label in WORLD_CUP_GROUPS_2026.keys():
        jogos_grupo = _ordenar_jogos_grupo(jogos_por_grupo.get(grupo_label, []))
        st.markdown(f"<div class='wc-group-title'>{grupo_label.upper()}</div>", unsafe_allow_html=True)
        st.caption(f"{len(jogos_grupo)} jogos importados neste grupo.")

        with st.container():
            if not jogos_grupo:
                st.info("Nenhum jogo cadastrado neste grupo ainda.")
            else:
                render_abas_rodadas_grupo(
                    user_id=user_id,
                    grupo_label=grupo_label,
                    jogos_grupo=jogos_grupo,
                    palpites_partidas=palpites_partidas,
                )

        st.divider()

    if jogos_sem_grupo:
        st.markdown("<div class='wc-round-label'>Não mapeados</div>", unsafe_allow_html=True)
        for indice, jogo in enumerate(_ordenar_jogos_grupo(jogos_sem_grupo), start=1):
            jogo_id = jogo.id if jogo.id is not None else indice
            palpite_atual = palpites_partidas.get(jogo_id, {})
            _render_jogo_card(
                user_id=user_id,
                jogo=jogo,
                jogo_id=jogo_id,
                palpite_atual=palpite_atual,
            )


def _render_fase_simples(user_id: int, fase: str, jogos: List, palpites_partidas: Dict[int, Dict[str, int]]) -> None:
    if not jogos:
        return

    fase_exibicao = _rotulo_fase_exibicao(fase)
    with st.expander(fase_exibicao, expanded=False):
        for indice, jogo in enumerate(_ordenar_jogos_grupo(jogos), start=1):
            jogo_id = jogo.id if jogo.id is not None else indice
            palpite_atual = palpites_partidas.get(jogo_id, {})
            _render_jogo_card(
                user_id=user_id,
                jogo=jogo,
                jogo_id=jogo_id,
                palpite_atual=palpite_atual,
            )


def _carregar_classificados_salvos(palpites_especiais) -> Dict[str, Dict[str, Any]]:
    if not palpites_especiais:
        return {}

    classificados: Dict[str, Dict[str, Any]] = {}
    bruto = getattr(palpites_especiais, "classificados_grupos", "") or ""
    if bruto:
        try:
            dados = json.loads(bruto)
        except json.JSONDecodeError:
            dados = {}
        if isinstance(dados, dict):
            for grupo, valores in dados.items():
                if isinstance(valores, dict):
                    classificados[str(grupo)] = {
                        "primeiro": str(valores.get("primeiro") or ""),
                        "segundo": str(valores.get("segundo") or ""),
                        "terceiro": str(valores.get("terceiro") or ""),
                        "terceiro_classificado": bool(valores.get("terceiro_classificado", False)),
                    }

    if "Grupo A" not in classificados:
        classificados["Grupo A"] = {
            "primeiro": getattr(palpites_especiais, "primeiro_grupo_a", "") or "",
            "segundo": getattr(palpites_especiais, "segundo_grupo_a", "") or "",
            "terceiro": "",
            "terceiro_classificado": False,
        }

    return classificados


def _opcoes_com_vazio(opcoes: List[str]) -> List[str]:
    return [""] + [opcao for opcao in opcoes if opcao]


def _indice_opcao(opcoes: List[str], valor_salvo: str) -> int:
    return opcoes.index(valor_salvo) if valor_salvo in opcoes else 0


def _render_select_time(label: str, opcoes: List[str], valor_salvo: str, key: str, *, disabled: bool = False) -> str:
    opcoes_select = _opcoes_com_vazio(opcoes)
    if valor_salvo and valor_salvo not in opcoes_select:
        st.caption(f"Valor salvo anteriormente fora da lista atual: {valor_salvo}")
    return st.selectbox(
        label,
        opcoes_select,
        index=_indice_opcao(opcoes_select, valor_salvo),
        key=key,
        format_func=lambda valor: "Selecione..." if not valor else valor,
        disabled=disabled,
    )


def _render_palpites_especiais(user_id: int, palpites_especiais, *, bloqueado: bool = False) -> None:
    st.subheader("Palpites Especiais")

    if bloqueado:
        st.warning("A Copa já começou — palpites especiais encerrados.")


    times_por_grupo = obter_times_por_grupo()
    grupos_copa = list(WORLD_CUP_GROUPS_2026.keys())
    selecoes = sorted(
        {time for grupo in grupos_copa for time in times_por_grupo.get(grupo, [])},
        key=normalizar_texto,
    )
    classificados_salvos = _carregar_classificados_salvos(palpites_especiais)

    with st.container():
        st.markdown("#### Campeão e Vice")
        col_campeao, col_vice = st.columns(2)

        with col_campeao:
            campeao = _render_select_time(
                "Campeão",
                selecoes,
                palpites_especiais.campeao if palpites_especiais else "",
                "palpite_especial_campeao",
                disabled=bloqueado,
            )

        opcoes_vice = [time for time in selecoes if time != campeao]
        with col_vice:
            vice = _render_select_time(
                "Vice",
                opcoes_vice,
                palpites_especiais.vice if palpites_especiais else "",
                "palpite_especial_vice",
                disabled=bloqueado,
            )

        st.markdown("#### Prêmios Individuais")
        jogadores_lista = listar_jogadores_copa()
        opcoes_jogadores = [""] + jogadores_lista
        artilheiro_salvo = (palpites_especiais.artilheiro if palpites_especiais else "") or ""
        melhor_salvo = (palpites_especiais.melhor_jogador if palpites_especiais else "") or ""

        col_artilheiro, col_melhor = st.columns(2)
        with col_artilheiro:
            if jogadores_lista:
                if artilheiro_salvo and artilheiro_salvo not in opcoes_jogadores:
                    st.caption(f"Palpite anterior: {artilheiro_salvo}")
                artilheiro = _render_select_time(
                    "Artilheiro",
                    jogadores_lista,
                    artilheiro_salvo,
                    "palpite_especial_artilheiro",
                    disabled=bloqueado,
                )
            else:
                artilheiro = st.text_input(
                    "Artilheiro",
                    value=artilheiro_salvo,
                    disabled=bloqueado,
                    help="Importe os jogadores no painel admin para habilitar a lista.",
                )
        with col_melhor:
            if jogadores_lista:
                if melhor_salvo and melhor_salvo not in opcoes_jogadores:
                    st.caption(f"Palpite anterior: {melhor_salvo}")
                melhor_jogador = _render_select_time(
                    "Melhor jogador",
                    jogadores_lista,
                    melhor_salvo,
                    "palpite_especial_melhor_jogador",
                    disabled=bloqueado,
                )
            else:
                melhor_jogador = st.text_input(
                    "Melhor jogador",
                    value=melhor_salvo,
                    disabled=bloqueado,
                    help="Importe os jogadores no painel admin para habilitar a lista.",
                )

        st.markdown("#### Classificados por Grupo")
        tabs = st.tabs(grupos_copa)
        classificados_por_grupo: Dict[str, Dict[str, Any]] = {}

        for tab, grupo in zip(tabs, grupos_copa):
            with tab:
                times_grupo = times_por_grupo.get(grupo, [])
                if not times_grupo:
                    st.info("Nenhuma seleção encontrada para este grupo.")
                    classificados_por_grupo[grupo] = {
                        "primeiro": "",
                        "segundo": "",
                        "terceiro": "",
                        "terceiro_classificado": False,
                    }
                    continue

                salvos_grupo = classificados_salvos.get(grupo, {})
                col_primeiro, col_segundo, col_terceiro = st.columns(3)
                with col_primeiro:
                    primeiro = _render_select_time(
                        "1º colocado",
                        times_grupo,
                        salvos_grupo.get("primeiro", ""),
                        f"classificado_primeiro_{grupo.replace(' ', '_').lower()}",
                        disabled=bloqueado,
                    )

                opcoes_segundo = [time for time in times_grupo if time != primeiro]
                with col_segundo:
                    segundo = _render_select_time(
                        "2º colocado",
                        opcoes_segundo,
                        salvos_grupo.get("segundo", ""),
                        f"classificado_segundo_{grupo.replace(' ', '_').lower()}",
                        disabled=bloqueado,
                    )

                opcoes_terceiro = [time for time in times_grupo if time not in {primeiro, segundo}]
                with col_terceiro:
                    terceiro = _render_select_time(
                        "3º colocado",
                        opcoes_terceiro,
                        salvos_grupo.get("terceiro", ""),
                        f"classificado_terceiro_{grupo.replace(' ', '_').lower()}",
                        disabled=bloqueado,
                    )

                terceiro_classificado = st.checkbox(
                    "3º colocado classificado",
                    value=bool(salvos_grupo.get("terceiro_classificado", False)),
                    key=f"terceiro_classificado_{grupo.replace(' ', '_').lower()}",
                    disabled=not terceiro or bloqueado,
                )

                classificados_por_grupo[grupo] = {
                    "primeiro": primeiro,
                    "segundo": segundo,
                    "terceiro": terceiro,
                    "terceiro_classificado": bool(terceiro_classificado and terceiro),
                }

        terceiros_classificados = sum(
            1 for valores in classificados_por_grupo.values() if valores.get("terceiro_classificado")
        )
        st.caption(f"Terceiros classificados: {terceiros_classificados} / 8")
        if terceiros_classificados < 8:
            st.warning("Selecione exatamente 8 terceiros classificados.")
        elif terceiros_classificados == 8:
            st.success("8 terceiros classificados selecionados.")
        else:
            st.error("Somente 8 terceiros colocados podem se classificar.")

        if st.button(
            "Salvar palpites especiais",
            key="salvar_palpites_especiais",
            disabled=bloqueado or terceiros_classificados > 8,
        ):
            if campeao and vice and campeao == vice:
                st.error("Campeão e vice não podem ser a mesma seleção.")
                return

            for grupo, valores in classificados_por_grupo.items():
                posicoes = [
                    valores.get("primeiro", ""),
                    valores.get("segundo", ""),
                    valores.get("terceiro", ""),
                ]
                preenchidos = [time for time in posicoes if time]
                if len(preenchidos) != len(set(preenchidos)):
                    st.error(f"{grupo}: 1º, 2º e 3º colocados não podem repetir seleção.")
                    return

            if terceiros_classificados != 8:
                st.error("Você deve selecionar exatamente 8 terceiros colocados classificados.")
                return

            grupo_a = classificados_por_grupo.get("Grupo A", {})
            salvar_palpites_especiais(
                user_id=user_id,
                campeao=campeao,
                vice=vice,
                artilheiro=artilheiro,
                melhor_jogador=melhor_jogador,
                primeiro_grupo_a=grupo_a.get("primeiro", ""),
                segundo_grupo_a=grupo_a.get("segundo", ""),
                classificados_grupos=json.dumps(classificados_por_grupo, ensure_ascii=False),
            )
            st.success("Palpites especiais salvos com sucesso.")



def render_tela_palpites(user_id: int) -> None:
    """Renderiza a tela principal de palpites."""
    _aplicar_estilos_palpites()
    st.markdown("<div class='wc-page-title'>Palpites da Copa do Mundo</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='wc-page-subtitle'>Separe sua estratégia por fase, acompanhe a tabela dos grupos e continue salvando seus palpites normalmente.</div>",
        unsafe_allow_html=True,
    )

    jogos = listar_jogos_por_fase()
    palpites_partidas = carregar_palpites_partidas(user_id)
    palpites_especiais = carregar_palpites_especiais(user_id)
    especiais_bloqueados = _copa_ja_comecou(jogos)

    if not jogos:
        st.info("Nenhum jogo cadastrado ainda.")
    else:
        jogos_por_fase: Dict[str, List] = defaultdict(list)
        for jogo in jogos:
            jogos_por_fase[jogo.fase or FASE_NAO_MAPEADA].append(jogo)

        jogos_fase_grupos = jogos_por_fase.get("Fase de Grupos", [])
        if jogos_fase_grupos:
            _render_fase_grupos(user_id, jogos_fase_grupos, palpites_partidas)
        else:
            st.info("Nenhum jogo da Fase de Grupos cadastrado ainda.")

        fases_ordenadas = [
            fase
            for fase in FASES_VALIDAS_COPA
            if fase not in {"Fase de Grupos", FASE_NAO_MAPEADA}
        ]
        for fase in fases_ordenadas:
            _render_fase_simples(user_id, fase, jogos_por_fase.get(fase, []), palpites_partidas)

        if jogos_por_fase.get(FASE_NAO_MAPEADA):
            _render_fase_simples(user_id, FASE_NAO_MAPEADA, jogos_por_fase.get(FASE_NAO_MAPEADA, []), palpites_partidas)

    _render_palpites_especiais(user_id, palpites_especiais, bloqueado=especiais_bloqueados)
