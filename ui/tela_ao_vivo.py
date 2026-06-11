"""Tela Ao Vivo experimental da Copa do Mundo."""

from __future__ import annotations

import html
from textwrap import dedent
from typing import Any, Dict, List, Optional

import streamlit as st

try:  # pragma: no cover - dependencia opcional
    from streamlit_autorefresh import st_autorefresh
except ImportError:  # pragma: no cover - fallback compativel
    st_autorefresh = None

from settings import TEST_MODE_AO_VIVO
from database import listar_palpites_por_api_ids
from services.api_service import BSDAPIError, buscar_jogos_ao_vivo, buscar_jogos_ao_vivo_teste, buscar_jogos_do_dia
from ui.tela_palpites import _aplicar_estilos_palpites, _formatar_data_hora
from utils.formatters import formatar_nome_time
from utils.team_assets import render_team_identity_html


_STATUS_AO_VIVO = frozenset({
    "inprogress", "1st_half", "halftime", "2nd_half",
    "live", "first_half", "second_half",
})
_STATUS_FINALIZADO = frozenset({
    "finished", "ft", "fulltime", "full time", "complete",
    "completed", "final", "aet", "after extra time", "pen",
    "after penalties",
})


def _normalizar_status_raw(status: Optional[str]) -> str:
    return str(status or "").replace("_", " ").strip().lower()


@st.cache_data(ttl=30, show_spinner=False)
def buscar_jogos_ao_vivo_cache(test_mode: bool) -> List[Dict[str, Any]]:
    if test_mode:
        return buscar_jogos_ao_vivo_teste()
    return buscar_jogos_ao_vivo()


@st.cache_data(ttl=300, show_spinner=False)
def buscar_jogos_do_dia_cache() -> List[Dict[str, Any]]:
    return buscar_jogos_do_dia()


def _aplicar_auto_refresh(interval_ms: int = 30_000) -> None:
    if st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key="ao_vivo_autorefresh")
        return

    st.caption("Atualizacao automatica indisponivel neste ambiente.")


def _html_escape(texto: Any) -> str:
    return html.escape(str(texto or ""))


def _status_exibicao(status: Optional[str]) -> str:
    texto = str(status or "").strip()
    if not texto:
        return "AO VIVO"
    s = texto.replace("_", " ").strip().lower()
    if s in {"halftime", "half time"}:
        return "🟠 INTERVALO"
    if s in {"inprogress", "live", "1st half", "first half", "2nd half", "second half"}:
        return "🔴 AO VIVO"
    if s in {"finished", "ft", "fulltime", "full time", "complete", "completed", "final", "aet", "after extra time", "pen", "after penalties"}:
        return "✅ ENCERRADO"
    if s in {"notstarted", "scheduled", "upcoming", "tbd"}:
        return "⏳ AGENDADO"
    if s == "postponed":
        return "⚠️ ADIADO"
    if s == "cancelled":
        return "❌ CANCELADO"
    if s == "mock":
        return "⚪ DEMO LOCAL"
    return texto.replace("_", " ").upper()


def _formatar_minuto(minuto: Optional[Any]) -> str:
    if minuto in (None, ""):
        return "-"
    texto = str(minuto).strip()
    if not texto:
        return "-"
    if texto.endswith("'") or texto.endswith("'"):
        return texto
    if texto.isdigit():
        return f"{texto}'"
    return texto


def _gerar_mock_local() -> List[Dict[str, Any]]:
    from datetime import datetime

    agora = datetime.now().astimezone().isoformat()

    return [
        {
            "mock": True,
            "time_casa": "Atalanta Bergamasca Calcio",
            "time_fora": "AS Roma",
            "home_team_id": None,
            "away_team_id": None,
            "home_team_logo_url": None,
            "away_team_logo_url": None,
            "league_id": None,
            "league_name": "Teste local",
            "status": "inprogress",
            "fase": "Demonstracao local",
            "data_hora": agora,
            "minuto": 32,
            "placar_casa": 1,
            "placar_fora": 0,
            "estadio": "Teste controlado",
        }
    ]


def _render_pill(labels: List[str]) -> str:
    return "".join(
        f'<span class="wc-live-pill{" wc-live-pill-alert" if label.startswith("🔴") else ""}">{_html_escape(label)}</span>'
        for label in labels
        if label
    )


def _mesmo_resultado(gc: int, gf: int, pc: int, pf: int) -> bool:
    def _sign(n: int) -> int:
        return 1 if n > 0 else (-1 if n < 0 else 0)
    return _sign(gc - gf) == _sign(pc - pf)


def _render_palpites_jogo(
    jogo: Dict[str, Any],
    palpites: List[Dict[str, Any]],
    status_raw: str,
) -> None:
    # Só exibe palpites após o jogo ter iniciado
    if status_raw not in _STATUS_AO_VIVO and status_raw not in _STATUS_FINALIZADO:
        return

    home_nome = formatar_nome_time(jogo.get("time_casa") or jogo.get("home_team") or "-")
    away_nome = formatar_nome_time(jogo.get("time_fora") or jogo.get("away_team") or "-")
    placar_casa_real = jogo.get("placar_casa")
    placar_fora_real = jogo.get("placar_fora")
    tem_placar = placar_casa_real is not None and placar_fora_real is not None
    eh_encerrado = status_raw in _STATUS_FINALIZADO

    n = len(palpites)
    label_expander = f"Ver palpites ({n})" if n > 0 else "Ver palpites (nenhum)"

    with st.expander(label_expander, expanded=False):
        if not palpites:
            st.caption("Nenhum palpite registrado para este jogo.")
            return

        cards_html: List[str] = []
        for palpite in palpites:
            nome = _html_escape(palpite.get("nome") or "-")
            gols_casa = int(palpite.get("gols_casa") or 0)
            gols_fora = int(palpite.get("gols_fora") or 0)

            badge = ""
            if tem_placar:
                p_casa = int(placar_casa_real)
                p_fora = int(placar_fora_real)
                if gols_casa == p_casa and gols_fora == p_fora:
                    badge = '<span class="wc-palpite-badge wc-palpite-exato">Placar Exato ✓</span>'
                elif _mesmo_resultado(gols_casa, gols_fora, p_casa, p_fora):
                    badge = '<span class="wc-palpite-badge wc-palpite-resultado">Resultado ✓</span>'
                elif eh_encerrado:
                    badge = '<span class="wc-palpite-badge wc-palpite-errou">Errou</span>'

            cards_html.append(
                f'<div class="wc-palpite-card">'
                f'<div class="wc-palpite-nome">{nome}{badge}</div>'
                f'<div class="wc-palpite-placar">'
                f'<span class="wc-palpite-time">{_html_escape(home_nome)}</span>'
                f'<span class="wc-palpite-score">{gols_casa} x {gols_fora}</span>'
                f'<span class="wc-palpite-time wc-palpite-time-right">{_html_escape(away_nome)}</span>'
                f'</div></div>'
            )

        st.markdown("\n".join(cards_html), unsafe_allow_html=True)


def _render_jogo_ao_vivo_card(jogo: Dict[str, Any], palpites: Optional[List[Dict[str, Any]]] = None) -> None:
    home_nome = formatar_nome_time(jogo.get("time_casa") or jogo.get("home_team") or "-")
    away_nome = formatar_nome_time(jogo.get("time_fora") or jogo.get("away_team") or "-")
    home_identity = render_team_identity_html(
        jogo.get("time_casa") or jogo.get("home_team"),
        team_id=jogo.get("home_team_id"),
        logo_url=jogo.get("home_team_logo_url"),
    )
    away_identity = render_team_identity_html(
        jogo.get("time_fora") or jogo.get("away_team"),
        team_id=jogo.get("away_team_id"),
        logo_url=jogo.get("away_team_logo_url"),
    )

    data_hora = jogo.get("data_hora")
    horario = _formatar_data_hora(data_hora) if data_hora else {"data": "-", "hora": "-"}
    estadio = str(jogo.get("estadio") or "").strip()
    fase = str(jogo.get("fase") or "").strip() or "Fase nao informada"
    status_raw = _normalizar_status_raw(jogo.get("status"))
    status = _status_exibicao(jogo.get("status"))
    minuto = _formatar_minuto(jogo.get("minuto"))
    placar_casa = jogo.get("placar_casa")
    placar_fora = jogo.get("placar_fora")

    eh_ao_vivo = status_raw in _STATUS_AO_VIVO
    eh_encerrado = status_raw in _STATUS_FINALIZADO

    if placar_casa is not None and placar_fora is not None:
        placar_texto = f"{int(placar_casa)} x {int(placar_fora)}"
    elif eh_encerrado:
        placar_texto = "- x -"
    else:
        placar_texto = horario["hora"]

    meta = [fase, f"{horario['data']} {horario['hora']}"]
    if estadio:
        meta.append(estadio)

    top_pills = _render_pill(
        [
            status,
            fase,
            f"Minuto {minuto}" if eh_ao_vivo else "",
            "DEMO LOCAL" if jogo.get("mock") else "",
        ]
    )

    st.markdown(
        dedent(
            f"""
            <div class="wc-live-card">
                <div class="wc-live-topline">{top_pills}</div>
                <div class="wc-live-meta">{_html_escape(" | ".join(meta))}</div>
                <div class="wc-live-match">
                    <div class="wc-live-team">{home_identity}</div>
                    <div class="wc-live-score">{_html_escape(placar_texto)}</div>
                    <div class="wc-live-team wc-live-team-right">{away_identity}</div>
                </div>
                <div class="wc-live-foot">
                    <span>{_html_escape(home_nome)}</span>
                    <span class="wc-live-vs">x</span>
                    <span>{_html_escape(away_nome)}</span>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
    _render_palpites_jogo(jogo, palpites or [], status_raw)


def _render_secao(titulo: str, jogos: List[Dict[str, Any]], palpites_por_api_id: Dict[int, List]) -> None:
    st.markdown(f"### {titulo}")
    for jogo in jogos:
        api_id = jogo.get("api_id")
        palpites = palpites_por_api_id.get(int(api_id), []) if api_id is not None else []
        _render_jogo_ao_vivo_card(jogo, palpites)


def render_tela_ao_vivo() -> None:
    """Renderiza a pagina de acompanhamento ao vivo com jogos do dia."""
    _aplicar_estilos_palpites()
    st.markdown(
        """
        <style>
        .wc-live-hero {
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
            margin-bottom: 1rem;
        }
        .wc-live-subtitle {
            color: rgba(255, 255, 255, 0.72);
        }
        .wc-live-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04));
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 20px;
            padding: 1rem;
            box-shadow: 0 16px 38px rgba(0,0,0,0.18);
            margin-bottom: 0.95rem;
        }
        .wc-live-topline {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 0.65rem;
        }
        .wc-live-pill {
            display: inline-flex;
            align-items: center;
            padding: 0.22rem 0.6rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            color: rgba(255,255,255,0.88);
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }
        .wc-live-pill-alert {
            background: rgba(220, 38, 38, 0.18);
            border-color: rgba(239, 68, 68, 0.35);
            color: #fecaca;
        }
        .wc-live-meta {
            color: rgba(255,255,255,0.68);
            font-size: 0.9rem;
            margin-bottom: 0.9rem;
        }
        .wc-live-match {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
            gap: 1rem;
            align-items: center;
        }
        .wc-live-team {
            min-width: 0;
        }
        .wc-live-team-right {
            justify-self: end;
        }
        .wc-live-score {
            font-size: 2rem;
            font-weight: 900;
            letter-spacing: 0.04em;
            text-align: center;
            padding: 0.15rem 0.65rem;
            border-radius: 14px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            min-width: 120px;
        }
        .wc-live-foot {
            display: flex;
            gap: 0.5rem;
            align-items: center;
            justify-content: center;
            margin-top: 0.9rem;
            color: rgba(255,255,255,0.72);
            font-size: 0.9rem;
        }
        .wc-live-vs {
            opacity: 0.55;
            font-weight: 700;
        }
        .wc-palpite-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 0.65rem 0.9rem;
            margin-bottom: 0.5rem;
        }
        .wc-palpite-nome {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 700;
            font-size: 0.88rem;
            color: rgba(255,255,255,0.9);
            margin-bottom: 0.45rem;
        }
        .wc-palpite-placar {
            display: grid;
            grid-template-columns: minmax(0,1fr) auto minmax(0,1fr);
            gap: 0.5rem;
            align-items: center;
            font-size: 0.85rem;
            color: rgba(255,255,255,0.7);
        }
        .wc-palpite-score {
            font-size: 1.1rem;
            font-weight: 800;
            text-align: center;
            padding: 0.1rem 0.5rem;
            border-radius: 8px;
            background: rgba(255,255,255,0.06);
            color: rgba(255,255,255,0.95);
            white-space: nowrap;
        }
        .wc-palpite-time {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .wc-palpite-time-right {
            text-align: right;
        }
        .wc-palpite-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.12rem 0.5rem;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .wc-palpite-exato {
            background: rgba(34,197,94,0.18);
            border: 1px solid rgba(34,197,94,0.4);
            color: #86efac;
        }
        .wc-palpite-resultado {
            background: rgba(234,179,8,0.18);
            border: 1px solid rgba(234,179,8,0.4);
            color: #fde047;
        }
        .wc-palpite-errou {
            background: rgba(239,68,68,0.1);
            border: 1px solid rgba(239,68,68,0.2);
            color: rgba(255,255,255,0.4);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _aplicar_auto_refresh(30_000)

    st.markdown(
        dedent(
            """
            <div class="wc-live-hero">
                <div class="wc-page-title">Ao Vivo</div>
                <div class="wc-live-subtitle">Jogos de hoje da Copa do Mundo.</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    if TEST_MODE_AO_VIVO:
        st.warning("Modo de teste ativo — não usar em produção.")

    st.caption("Atualizacao automatica a cada 30 segundos.")

    # Busca jogos do dia (schedule) e jogos ao vivo (placares em tempo real)
    try:
        jogos_hoje = buscar_jogos_do_dia_cache()
    except BSDAPIError as exc:
        st.warning(f"Nao foi possivel buscar jogos do dia: {exc}")
        jogos_hoje = []
    except Exception as exc:  # pragma: no cover
        st.error(f"Erro inesperado ao buscar jogos do dia: {exc}")
        jogos_hoje = []

    try:
        jogos_ao_vivo = buscar_jogos_ao_vivo_cache(TEST_MODE_AO_VIVO)
    except BSDAPIError:
        jogos_ao_vivo = []
    except Exception:  # pragma: no cover
        jogos_ao_vivo = []

    # Sobrepõe dados ao vivo nos jogos do dia (placar e minuto em tempo real)
    live_por_api_id: Dict[int, Dict[str, Any]] = {
        j["api_id"]: j for j in jogos_ao_vivo if j.get("api_id") is not None
    }
    hoje_api_ids = {j.get("api_id") for j in jogos_hoje}

    jogos_merged: List[Dict[str, Any]] = []
    for jogo in jogos_hoje:
        api_id = jogo.get("api_id")
        if api_id is not None and api_id in live_por_api_id:
            jogos_merged.append(live_por_api_id[api_id])
        else:
            jogos_merged.append(jogo)

    # Jogos ao vivo que não estão na lista do dia (raridade)
    for jogo in jogos_ao_vivo:
        if jogo.get("api_id") not in hoje_api_ids:
            jogos_merged.append(jogo)

    if not jogos_merged:
        if TEST_MODE_AO_VIVO:
            st.info("Nenhum jogo encontrado na API de teste. Exibindo mock local.")
            jogos_merged = _gerar_mock_local()
        else:
            st.info("Nenhum jogo da Copa hoje.")
            return

    jogos_ordenados = sorted(
        jogos_merged,
        key=lambda j: (str(j.get("data_hora") or ""), int(j.get("match_number") or 0)),
    )

    ao_vivo = [j for j in jogos_ordenados if _normalizar_status_raw(j.get("status")) in _STATUS_AO_VIVO]
    encerrados = [j for j in jogos_ordenados if _normalizar_status_raw(j.get("status")) in _STATUS_FINALIZADO]
    proximos = [
        j for j in jogos_ordenados
        if _normalizar_status_raw(j.get("status")) not in _STATUS_AO_VIVO
        and _normalizar_status_raw(j.get("status")) not in _STATUS_FINALIZADO
    ]

    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 Ao Vivo", len(ao_vivo))
    col2.metric("⏳ Próximos", len(proximos))
    col3.metric("✅ Encerrados", len(encerrados))

    api_ids_tuple = tuple(
        int(j["api_id"])
        for j in jogos_ordenados
        if j.get("api_id") is not None and not j.get("mock")
    )
    palpites_por_api_id = listar_palpites_por_api_ids(api_ids_tuple)

    if ao_vivo:
        _render_secao("🔴 Em Andamento", ao_vivo, palpites_por_api_id)

    if proximos:
        _render_secao("⏳ Próximos Jogos", proximos, palpites_por_api_id)

    if encerrados:
        _render_secao("✅ Encerrados", encerrados, palpites_por_api_id)
