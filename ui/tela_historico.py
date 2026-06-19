"""Tela de historico: jogos finalizados e palpites dos participantes."""

from __future__ import annotations

import html
from datetime import date as _date, datetime, timezone
from textwrap import dedent
from typing import Any, Dict, List, Optional

import streamlit as st

from database import (
    carregar_palpites_partidas,
    listar_palpites_por_jogos,
)
from services.jogos_service import listar_jogos_por_fase
from utils.formatters import formatar_nome_time
from utils.team_assets import render_team_identity_html

try:
    from zoneinfo import ZoneInfo as _ZoneInfo
    _TZ_BRT = _ZoneInfo("America/Sao_Paulo")
except Exception:
    _TZ_BRT = None


# ---------------------------------------------------------------------------
# Helpers de data/tempo
# ---------------------------------------------------------------------------

def _data_jogo_brt(jogo) -> Optional[_date]:
    data_iso = getattr(jogo, "data_jogo", None)
    if not data_iso:
        return None
    try:
        dt = datetime.fromisoformat(str(data_iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if _TZ_BRT:
            dt = dt.astimezone(_TZ_BRT)
        return dt.date()
    except ValueError:
        return None


def _formatar_data_hora_brt(data_iso: Optional[str]) -> Dict[str, str]:
    if not data_iso:
        return {"data": "-", "hora": "-"}
    try:
        dt = datetime.fromisoformat(str(data_iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if _TZ_BRT:
            dt = dt.astimezone(_TZ_BRT)
        return {"data": dt.strftime("%d/%m/%Y"), "hora": dt.strftime("%H:%M")}
    except ValueError:
        return {"data": str(data_iso), "hora": "-"}


# ---------------------------------------------------------------------------
# Calculo de resultado de palpite
# ---------------------------------------------------------------------------

def _vencedor(a: int, b: int) -> str:
    if a > b:
        return "A"
    if b > a:
        return "B"
    return "E"


def _resultado_palpite(pa: int, pb: int, ra: int, rb: int) -> str:
    """Retorna 'exact', 'partial' ou 'miss'."""
    if pa == ra and pb == rb:
        return "exact"
    if _vencedor(pa, pb) == _vencedor(ra, rb):
        return "partial"
    return "miss"


def _badge_resultado_html(resultado: str) -> str:
    if resultado == "exact":
        return (
            '<span style="color:#86efac;font-weight:700;white-space:nowrap;">'
            "✅ Placar exato</span>"
        )
    if resultado == "partial":
        return (
            '<span style="color:#fde047;font-weight:700;white-space:nowrap;">'
            "🟡 Acerto parcial</span>"
        )
    return (
        '<span style="color:#f87171;font-weight:700;white-space:nowrap;">'
        "❌ Erro</span>"
    )


# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------

def _aplicar_estilos() -> None:
    st.markdown(
        dedent(
            """
            <style>
            /* identidades de time reutilizadas por render_team_identity_html */
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
            .wc-team-name { min-width: 0; }

            /* titulos de pagina */
            .wc-page-title {
                font-size: 2.1rem;
                font-weight: 800;
                letter-spacing: -0.03em;
                margin-bottom: 0.25rem;
            }
            .wc-page-subtitle {
                color: rgba(255,255,255,0.72);
                margin-bottom: 1.25rem;
            }

            /* card principal do jogo */
            .wch-card {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 16px;
                padding: 1rem 1.1rem;
                margin-bottom: 0.85rem;
            }
            .wch-topline {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 0.4rem;
                margin-bottom: 0.6rem;
                font-size: 0.8rem;
                color: rgba(255,255,255,0.65);
            }
            .wch-phase-badge {
                display: inline-flex;
                align-items: center;
                padding: 0.2rem 0.6rem;
                border-radius: 999px;
                background: rgba(70,145,255,0.15);
                border: 1px solid rgba(70,145,255,0.3);
                color: #93c5fd;
                font-size: 0.75rem;
                font-weight: 700;
                letter-spacing: 0.04em;
                text-transform: uppercase;
                white-space: nowrap;
            }

            /* linha de placar central */
            .wch-scoreline {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.65rem;
                margin: 0.55rem 0 0.6rem 0;
                flex-wrap: wrap;
            }
            .wch-team-side {
                display: flex;
                align-items: center;
                gap: 0.4rem;
                font-size: 1rem;
                font-weight: 800;
                min-width: 0;
            }
            .wch-score-box {
                background: rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 0.3rem 0.9rem;
                font-size: 1.45rem;
                font-weight: 900;
                letter-spacing: 0.05em;
                min-width: 2.8rem;
                text-align: center;
            }
            .wch-score-sep {
                color: rgba(255,255,255,0.35);
                font-size: 1.1rem;
                font-weight: 700;
            }

            /* palpite do usuario logado */
            .wch-user-palpite {
                display: flex;
                align-items: center;
                gap: 0.65rem;
                flex-wrap: wrap;
                margin-top: 0.65rem;
                padding: 0.5rem 0.75rem;
                background: rgba(255,255,255,0.04);
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.07);
                font-size: 0.85rem;
            }
            .wch-no-palpite {
                color: rgba(255,255,255,0.38);
                font-style: italic;
            }

            /* linha de cada palpite no expander */
            .wch-palpite-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 0.5rem;
                padding: 0.38rem 0.1rem;
                border-bottom: 1px solid rgba(255,255,255,0.06);
                font-size: 0.85rem;
                flex-wrap: wrap;
            }
            .wch-palpite-row:last-child { border-bottom: none; }
            .wch-palpite-nome { font-weight: 700; min-width: 6rem; }
            .wch-palpite-score { font-weight: 600; color: rgba(255,255,255,0.85); }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Renderizacao de card individual
# ---------------------------------------------------------------------------

def _render_card(
    jogo,
    palpite_usuario: Optional[Dict[str, int]],
    todos_palpites: List[Dict[str, Any]],
) -> None:
    placar_a = jogo.placar_a if jogo.placar_a is not None else getattr(jogo, "gols_casa", None)
    placar_b = jogo.placar_b if jogo.placar_b is not None else getattr(jogo, "gols_fora", None)

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

    horario = _formatar_data_hora_brt(jogo.data_jogo)
    fase = str(getattr(jogo, "fase", "") or "-")
    grupo = str(getattr(jogo, "grupo", "") or "")
    round_label = str(jogo.round_number or "-")
    fase_label = f"{fase} · {grupo}" if grupo else fase

    # --- placar ---
    if placar_a is not None and placar_b is not None:
        score_html = (
            f'<div class="wch-score-box">{html.escape(str(int(placar_a)))}</div>'
            f'<span class="wch-score-sep">×</span>'
            f'<div class="wch-score-box">{html.escape(str(int(placar_b)))}</div>'
        )
    else:
        score_html = '<span class="wch-score-sep" style="font-size:1.8rem;">–</span>'

    # --- palpite do usuario ---
    if palpite_usuario:
        pa = int(palpite_usuario["palpite_a"])
        pb = int(palpite_usuario["palpite_b"])
        if placar_a is not None and placar_b is not None:
            resultado = _resultado_palpite(pa, pb, int(placar_a), int(placar_b))
            badge = _badge_resultado_html(resultado)
        else:
            badge = ""
        palpite_html = (
            f'<div class="wch-user-palpite">'
            f"<span>Seu palpite: <strong>{html.escape(home_nome)} "
            f"{pa} × {pb} {html.escape(away_nome)}</strong></span>"
            f"{badge}"
            f"</div>"
        )
    else:
        palpite_html = (
            '<div class="wch-user-palpite">'
            '<span class="wch-no-palpite">Sem palpite registrado</span>'
            "</div>"
        )

    st.markdown(
        f'<div class="wch-card">'
        f'<div class="wch-topline">'
        f'<span class="wch-phase-badge">{html.escape(fase_label)}</span>'
        f"<span>📅 {html.escape(horario['data'])} · "
        f"⏰ {html.escape(horario['hora'])} · "
        f"Round {html.escape(round_label)}</span>"
        f"</div>"
        f'<div class="wch-scoreline">'
        f'<span class="wch-team-side">{home_identity}</span>'
        f"{score_html}"
        f'<span class="wch-team-side">{away_identity}</span>'
        f"</div>"
        f"{palpite_html}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # --- dropdown de todos os palpites ---
    n = len(todos_palpites)
    label_exp = f"Ver todos os palpites ({n})" if n > 0 else "Palpites (nenhum registrado)"
    with st.expander(label_exp):
        if not todos_palpites:
            st.caption("Nenhum palpite registrado para este jogo.")
            return

        def _sort_key(p: Dict[str, Any]) -> int:
            if placar_a is not None and placar_b is not None:
                r = _resultado_palpite(
                    int(p["gols_casa"]), int(p["gols_fora"]),
                    int(placar_a), int(placar_b),
                )
                return {"exact": 0, "partial": 1, "miss": 2}[r]
            return 3

        linhas_html = ""
        for p in sorted(todos_palpites, key=_sort_key):
            nome = html.escape(str(p["nome"]))
            ga = int(p["gols_casa"])
            gb = int(p["gols_fora"])
            if placar_a is not None and placar_b is not None:
                r = _resultado_palpite(ga, gb, int(placar_a), int(placar_b))
                badge = _badge_resultado_html(r)
            else:
                badge = ""
            linhas_html += (
                f'<div class="wch-palpite-row">'
                f'<span class="wch-palpite-nome">{nome}</span>'
                f'<span class="wch-palpite-score">{html.escape(home_nome)} '
                f"<strong>{ga} × {gb}</strong> {html.escape(away_nome)}</span>"
                f"{badge}"
                f"</div>"
            )

        st.markdown(linhas_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def render_tela_historico(user_id: int) -> None:
    """Renderiza a tela de historico de jogos finalizados."""
    _aplicar_estilos()

    st.markdown('<div class="wc-page-title">Histórico</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="wc-page-subtitle">Jogos finalizados com placares e palpites.</div>',
        unsafe_allow_html=True,
    )

    todos_jogos = listar_jogos_por_fase()
    jogos_finalizados = [j for j in todos_jogos if getattr(j, "finalizado", False)]

    if not jogos_finalizados:
        st.info("Nenhum jogo finalizado ainda.")
        return

    # Ordena do mais recente para o mais antigo
    jogos_finalizados.sort(
        key=lambda j: (j.data_jogo or "", j.id or 0),
        reverse=True,
    )

    # --- Filtro por data ---
    datas_disponiveis: List[_date] = sorted(
        {d for j in jogos_finalizados if (d := _data_jogo_brt(j)) is not None},
        reverse=True,
    )

    filtro_data: Optional[_date] = None
    if datas_disponiveis:
        opcoes = ["Todas as datas"] + [d.strftime("%d/%m/%Y") for d in datas_disponiveis]
        selecao = st.selectbox(
            "Filtrar por data:",
            opcoes,
            index=0,
            key="historico_filtro_data",
        )
        if selecao != "Todas as datas":
            filtro_data = next(
                (d for d in datas_disponiveis if d.strftime("%d/%m/%Y") == selecao),
                None,
            )

    jogos_exibir = (
        [j for j in jogos_finalizados if _data_jogo_brt(j) == filtro_data]
        if filtro_data is not None
        else jogos_finalizados
    )

    if not jogos_exibir:
        st.info("Nenhum jogo encontrado para a data selecionada.")
        return

    st.caption(f"{len(jogos_exibir)} jogo(s) encontrado(s).")

    # Carrega palpites em lote
    palpites_usuario = carregar_palpites_partidas(user_id)
    ids_jogos = tuple(j.id for j in jogos_exibir if j.id is not None)
    todos_palpites_por_jogo = listar_palpites_por_jogos(ids_jogos) if ids_jogos else {}

    for jogo in jogos_exibir:
        jogo_id = jogo.id
        palpite_usuario = palpites_usuario.get(jogo_id) if jogo_id is not None else None
        palpites_jogo = todos_palpites_por_jogo.get(jogo_id, []) if jogo_id is not None else []
        _render_card(jogo, palpite_usuario, palpites_jogo)


__all__ = ["render_tela_historico"]
