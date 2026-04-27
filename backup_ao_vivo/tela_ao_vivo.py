"""Tela Ao Vivo da Copa do Mundo.

Esta pagina e somente visual: exibe jogos em andamento via API sem alterar
palpites, resultados reais ou ranking.
"""

from __future__ import annotations

import html
from textwrap import dedent
from typing import Any, Dict, Optional

import streamlit as st
import streamlit.components.v1 as components

try:  # pragma: no cover - dependencia opcional
    from streamlit_autorefresh import st_autorefresh
except ImportError:  # pragma: no cover - fallback compatível
    st_autorefresh = None

from services.api_service import BSDAPIError, buscar_jogos_ao_vivo
from ui.tela_palpites import _aplicar_estilos_palpites, _formatar_data_hora
from utils.formatters import formatar_nome_time
from utils.team_assets import render_team_identity_html


def _aplicar_auto_refresh(interval_ms: int = 30_000) -> None:
    if st_autorefresh is not None:
        st_autorefresh(interval=interval_ms, key="ao_vivo_autorefresh")
        return

    components.html(
        f"""
        <script>
        setTimeout(function() {{
            window.parent.location.reload();
        }}, {int(interval_ms)});
        </script>
        """,
        height=0,
    )


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


def _status_exibicao(status: Optional[str]) -> str:
    texto = str(status or "").strip()
    if not texto:
        return "AO VIVO"
    return texto.replace("_", " ").upper()


def _html_escape(texto: Any) -> str:
    return html.escape(str(texto or ""))


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

    st.markdown(
        dedent(
            f"""
            <div class="wc-live-card">
                <div class="wc-live-topline">
                    <span class="wc-live-pill">{_html_escape(status)}</span>
                    <span class="wc-live-pill">{_html_escape(fase)}</span>
                    <span class="wc-live-pill">Minuto {_html_escape(minuto)}</span>
                </div>
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
                <div class="wc-live-subtitle">Acompanhamento visual dos jogos em andamento da Copa do Mundo. Sem transmissao de video.</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    st.caption("Atualizacao automatica a cada 30 segundos.")

    try:
        jogos_ao_vivo = buscar_jogos_ao_vivo()
    except BSDAPIError as exc:
        st.warning(f"Nao foi possivel consultar a API ao vivo: {exc}")
        return
    except Exception as exc:  # pragma: no cover - erro inesperado
        st.error(f"Erro inesperado ao consultar jogos ao vivo: {exc}")
        return

    if not jogos_ao_vivo:
        st.info("Nenhum jogo da Copa ao vivo neste momento.")
        return

    jogos_ordenados = sorted(
        jogos_ao_vivo,
        key=lambda jogo: (
            str(jogo.get("data_hora") or ""),
            int(jogo.get("match_number") or 0),
            str(jogo.get("status") or ""),
        ),
    )

    st.metric("Jogos ao vivo da Copa", len(jogos_ordenados))

    for jogo in jogos_ordenados:
        _render_jogo_ao_vivo_card(jogo)
