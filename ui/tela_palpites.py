"""Tela de palpites.

Esta tela exibe jogos agrupados por fase e permite salvar palpites de partidas e
palpites especiais sem acessar o SQLite diretamente.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from collections import defaultdict
from textwrap import dedent
from typing import Any, Dict, List, Optional

import streamlit as st

from database import (
    FASE_NAO_MAPEADA,
    carregar_palpites_especiais,
    carregar_palpites_partidas,
    salvar_palpites_especiais,
    salvar_palpites_partida,
    FASES_VALIDAS_COPA,
)
from services.jogos_service import listar_jogos_por_fase
from utils.datetime_utils import bloquear_palpite_para_jogo
from utils.formatters import formatar_nome_time, normalizar_texto
from utils.team_assets import construir_mapa_logos_por_jogos, render_team_identity_html
from utils.world_cup import (
    WORLD_CUP_GROUPS_2026,
    inferir_grupo_por_times,
    normalizar_grupo_copa,
    obter_times_do_grupo,
)


def _chave_segura(texto: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in texto.lower())


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


def _render_jogo_card(jogo, palpite_atual: Dict[str, int], fase: str, jogo_chave: str) -> Dict[str, Any]:
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
        key=f"palpite_a_{fase}_{jogo_chave}",
        label_visibility="collapsed",
        disabled=bloqueado,
    )
    palpite_b = col_away.number_input(
        f"Gols de {away_nome}",
        min_value=0,
        max_value=20,
        step=1,
        value=int(palpite_atual.get("palpite_b", 0)),
        key=f"palpite_b_{fase}_{jogo_chave}",
        label_visibility="collapsed",
        disabled=bloqueado,
    )

    st.caption(
        f"Vencedor previsto: {_vencedor_previsto(home_nome, away_nome, int(palpite_a), int(palpite_b))}"
    )

    return {"palpite_a": int(palpite_a), "palpite_b": int(palpite_b), "bloqueado": bloqueado}


def _salvar_palpites_digitados(user_id: int, valores_digitados: Dict[int, Dict[str, Any]]) -> tuple[int, int]:
    bloqueados = 0
    salvos = 0
    for jogo_id, valores in valores_digitados.items():
        if valores.get("bloqueado"):
            bloqueados += 1
            continue

        try:
            salvar_palpites_partida(
                user_id=user_id,
                match_id=jogo_id,
                palpite_a=valores["palpite_a"],
                palpite_b=valores["palpite_b"],
            )
            salvos += 1
        except ValueError as exc:
            mensagem = str(exc)
            if mensagem == "Palpite bloqueado: o jogo já começou.":
                bloqueados += 1
                continue
            raise

    return salvos, bloqueados


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
    with st.form(f"form_{_chave_segura(f'{grupo_label}_{rodada}')}"):
        valores_digitados: Dict[int, Dict[str, Any]] = {}
        bloqueados: List[bool] = []
        for indice, jogo in enumerate(jogos_rodada, start=1):
            jogo_id = jogo.id if jogo.id is not None else int(f"{rodada}{indice}")
            palpite_atual = palpites_partidas.get(jogo_id, {"palpite_a": 0, "palpite_b": 0})
            valor_jogo = _render_jogo_card(
                jogo,
                palpite_atual,
                fase=grupo_label,
                jogo_chave=_chave_segura(f"{grupo_label}_{rodada}_{jogo_id}"),
            )
            valores_digitados[jogo_id] = valor_jogo
            bloqueados.append(bool(valor_jogo.get("bloqueado")))

        if st.form_submit_button(f"Salvar palpites da {rodada}ª rodada", disabled=all(bloqueados)):
            salvos, bloqueados_count = _salvar_palpites_digitados(user_id=user_id, valores_digitados=valores_digitados)
            if salvos:
                st.success(f"Palpites da {rodada}ª rodada salvos com sucesso.")
            if bloqueados_count:
                st.warning("Alguns palpites ja estavam encerrados e nao puderam ser alterados.")


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
        with st.form("form_nao_mapeados"):
            valores_digitados: Dict[int, Dict[str, Any]] = {}
            bloqueados: List[bool] = []
            for indice, jogo in enumerate(_ordenar_jogos_grupo(jogos_sem_grupo), start=1):
                jogo_id = jogo.id if jogo.id is not None else indice
                palpite_atual = palpites_partidas.get(jogo_id, {"palpite_a": 0, "palpite_b": 0})
                valor_jogo = _render_jogo_card(
                    jogo,
                    palpite_atual,
                    fase="nao_mapeados",
                    jogo_chave=_chave_segura(f"nao_mapeado_{jogo_id}"),
                )
                valores_digitados[jogo_id] = valor_jogo
                bloqueados.append(bool(valor_jogo.get("bloqueado")))
            if st.form_submit_button("Salvar palpites não mapeados", disabled=all(bloqueados)):
                salvos, bloqueados_count = _salvar_palpites_digitados(user_id=user_id, valores_digitados=valores_digitados)
                if salvos:
                    st.success("Palpites não mapeados salvos com sucesso.")
                if bloqueados_count:
                    st.warning("Alguns palpites ja estavam encerrados e nao puderam ser alterados.")


def _render_fase_simples(user_id: int, fase: str, jogos: List, palpites_partidas: Dict[int, Dict[str, int]]) -> None:
    if not jogos:
        return

    fase_exibicao = _rotulo_fase_exibicao(fase)
    with st.expander(fase_exibicao, expanded=False):
        with st.form(f"form_{_chave_segura(fase)}"):
            valores_digitados: Dict[int, Dict[str, Any]] = {}
            bloqueados: List[bool] = []
            for indice, jogo in enumerate(_ordenar_jogos_grupo(jogos), start=1):
                jogo_id = jogo.id if jogo.id is not None else indice
                palpite_atual = palpites_partidas.get(jogo_id, {"palpite_a": 0, "palpite_b": 0})
                valor_jogo = _render_jogo_card(
                    jogo,
                    palpite_atual,
                    fase=fase,
                    jogo_chave=_chave_segura(f"{fase}_{jogo_id}"),
                )
                valores_digitados[jogo_id] = valor_jogo
                bloqueados.append(bool(valor_jogo.get("bloqueado")))
            if st.form_submit_button(f"Salvar palpites de {fase_exibicao}", disabled=all(bloqueados)):
                salvos, bloqueados_count = _salvar_palpites_digitados(user_id=user_id, valores_digitados=valores_digitados)
                if salvos:
                    st.success(f"Palpites da fase {fase_exibicao} salvos com sucesso.")
                if bloqueados_count:
                    st.warning("Alguns palpites ja estavam encerrados e nao puderam ser alterados.")



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

    st.subheader("Palpites Especiais")
    with st.form("form_palpites_especiais"):
        campeao = st.text_input("Campeao", value=(palpites_especiais.campeao if palpites_especiais else ""))
        vice = st.text_input("Vice", value=(palpites_especiais.vice if palpites_especiais else ""))
        artilheiro = st.text_input("Artilheiro", value=(palpites_especiais.artilheiro if palpites_especiais else ""))
        melhor_jogador = st.text_input(
            "Melhor Jogador", value=(palpites_especiais.melhor_jogador if palpites_especiais else "")
        )
        primeiro_grupo_a = st.text_input(
            "1o colocado do Grupo A", value=(palpites_especiais.primeiro_grupo_a if palpites_especiais else "")
        )
        segundo_grupo_a = st.text_input(
            "2o colocado do Grupo A", value=(palpites_especiais.segundo_grupo_a if palpites_especiais else "")
        )

        salvar_especiais = st.form_submit_button("Salvar palpites especiais")

    if salvar_especiais:
        salvar_palpites_especiais(
            user_id=user_id,
            campeao=campeao,
            vice=vice,
            artilheiro=artilheiro,
            melhor_jogador=melhor_jogador,
            primeiro_grupo_a=primeiro_grupo_a,
            segundo_grupo_a=segundo_grupo_a,
        )
        st.success("Palpites especiais salvos com sucesso.")
