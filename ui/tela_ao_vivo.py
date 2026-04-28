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
from services.api_service import BSDAPIError, buscar_jogos_ao_vivo, buscar_jogos_ao_vivo_teste
from ui.tela_palpites import _aplicar_estilos_palpites, _formatar_data_hora
from utils.formatters import formatar_nome_time
from utils.team_assets import render_team_identity_html


@st.cache_data(ttl=30, show_spinner=False)
def buscar_jogos_ao_vivo_cache(test_mode: bool) -> List[Dict[str, Any]]:
    if test_mode:
        return buscar_jogos_ao_vivo_teste()
    return buscar_jogos_ao_vivo()


def _aplicar_auto_refresh(interval_ms: int = 30_000) -> None:
    if st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key="ao_vivo_autorefresh")
        return

    st.caption("Atualização automática indisponível. Use o botão Atualizar agora.")


def _html_escape(texto: Any) -> str:
    return html.escape(str(texto or ""))


def _status_exibicao(status: Optional[str]) -> str:
    texto = str(status or "").strip()
    if not texto:
        return "AO VIVO"
    texto_normalizado = texto.replace("_", " ").strip().lower()
    if texto_normalizado in {"halftime", "half time"}:
        return "🟠 INTERVALO"
    if texto_normalizado in {"inprogress", "live", "1st half", "first half", "2nd half", "second half"}:
        return "🔴 AO VIVO"
    if texto_normalizado == "mock":
        return "⚪ DEMO LOCAL"
    return texto.replace("_", " ").upper()


def _formatar_minuto(minuto: Optional[Any]) -> str:
    if minuto in (None, ""):
        return "-"
    texto = str(minuto).strip()
    if not texto:
        return "-"
    if texto.endswith("'") or texto.endswith("’"):
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


def _render_jogo_ao_vivo_card(jogo: Dict[str, Any]) -> None:
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
    status = _status_exibicao(jogo.get("status"))
    minuto = _formatar_minuto(jogo.get("minuto"))
    placar_casa = jogo.get("placar_casa")
    placar_fora = jogo.get("placar_fora")
    placar_texto = (
        f"{int(placar_casa)} x {int(placar_fora)}"
        if placar_casa is not None and placar_fora is not None
        else "Aguardando"
    )

    meta = [fase, f"{horario['data']} {horario['hora']}"]
    if estadio:
        meta.append(estadio)

    top_pills = _render_pill(
        [
            status,
            fase,
            f"Minuto {minuto}",
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


def render_tela_ao_vivo() -> None:
    """Renderiza a pagina de acompanhamento ao vivo."""
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
                <div class="wc-live-subtitle">Visualizacao experimental dos jogos em andamento da Copa do Mundo. Sem transmissao de video.</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    if TEST_MODE_AO_VIVO:
        st.warning("Modo de teste ativo — não usar em produção.")
        st.info("TEST_MODE_AO_VIVO ativo: buscando jogos ao vivo gerais para teste controlado.")
    else:
        st.caption("Modo oficial da Copa do Mundo: filtra apenas a league=27.")

    if st.button("Atualizar agora", use_container_width=True):
        buscar_jogos_ao_vivo_cache.clear()
        st.rerun()

    st.caption("Atualizacao automatica a cada 30 segundos.")

    try:
        jogos_ao_vivo = buscar_jogos_ao_vivo_cache(TEST_MODE_AO_VIVO)
    except BSDAPIError as exc:
        st.warning(f"Nao foi possivel consultar a API ao vivo: {exc}")
        jogos_ao_vivo = []
    except Exception as exc:  # pragma: no cover - erro inesperado
        st.error(f"Erro inesperado ao consultar jogos ao vivo: {exc}")
        return

    if not jogos_ao_vivo:
        if TEST_MODE_AO_VIVO:
            st.info("Nenhum jogo ao vivo encontrado na API de teste. Exibindo mock local apenas nesta tela.")
            jogos_ao_vivo = _gerar_mock_local()
            st.caption("Mock local isolado para validar layout, atualização e estados visuais.")
            st.metric("Jogos em demonstracao", len(jogos_ao_vivo))
        else:
            st.info("Nenhum jogo da Copa ao vivo neste momento.")
            return
    else:
        titulo_metric = "Jogos ao vivo de teste" if TEST_MODE_AO_VIVO else "Jogos ao vivo da Copa"
        st.metric(titulo_metric, len(jogos_ao_vivo))

    jogos_ordenados = sorted(
        jogos_ao_vivo,
        key=lambda jogo: (
            str(jogo.get("data_hora") or ""),
            int(jogo.get("match_number") or 0),
            str(jogo.get("status") or ""),
        ),
    )

    for jogo in jogos_ordenados:
        _render_jogo_ao_vivo_card(jogo)
