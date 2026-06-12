"""Tela de ranking.

Esta tela exibe a pontuacao total ja calculada e salva no banco local.
"""

from __future__ import annotations

import html
from textwrap import dedent
from typing import List, Optional, Tuple

import streamlit as st

from services.ranking_service import listar_ranking_atual, obter_premiacao_bolao
from utils.formatters import formatar_moeda_brl, normalizar_texto


def _render_estilos_ranking() -> None:
    st.markdown(
        """
        <style>
        .ranking-hero {
            background:
                radial-gradient(circle at top right, rgba(99, 102, 241, 0.18), transparent 28%),
                linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(17, 24, 39, 0.92));
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 28px;
            padding: 1.35rem 1.45rem;
            box-shadow: 0 18px 45px rgba(0, 0, 0, 0.18);
            margin-bottom: 1rem;
        }

        .ranking-kicker {
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.18em;
            color: rgba(255, 255, 255, 0.62);
            margin-bottom: 0.35rem;
        }

        .ranking-title {
            font-size: 2.15rem;
            font-weight: 900;
            letter-spacing: -0.04em;
            color: #ffffff;
            line-height: 1.05;
            margin-bottom: 0.4rem;
        }

        .ranking-subtitle {
            color: rgba(255, 255, 255, 0.75);
            line-height: 1.55;
            max-width: 70ch;
        }

        .ranking-section-label {
            margin: 1.25rem 0 0.7rem 0;
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            color: rgba(255, 255, 255, 0.6);
        }

        .ranking-metric-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.09);
            border-radius: 22px;
            padding: 1rem 1.05rem;
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.12);
            min-height: 118px;
        }

        .ranking-metric-label {
            font-size: 0.7rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            color: rgba(255, 255, 255, 0.56);
            margin-bottom: 0.45rem;
        }

        .ranking-metric-value {
            font-size: 1.9rem;
            font-weight: 900;
            line-height: 1;
            margin-bottom: 0.35rem;
            color: #ffffff;
        }

        .ranking-metric-hint {
            color: rgba(255, 255, 255, 0.72);
            font-size: 0.9rem;
            line-height: 1.45;
        }

        .ranking-podium-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
        }

        .ranking-podium-card {
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.035));
            border: 1px solid rgba(255, 255, 255, 0.09);
            border-radius: 24px;
            padding: 1rem;
            box-shadow: 0 14px 30px rgba(0, 0, 0, 0.14);
            position: relative;
            overflow: hidden;
            min-height: 170px;
        }

        .ranking-podium-card::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 60%);
            pointer-events: none;
        }

        .ranking-podium-card.is-1 {
            background: linear-gradient(180deg, rgba(245, 158, 11, 0.2), rgba(255, 255, 255, 0.05));
            border-color: rgba(245, 158, 11, 0.55);
            transform: translateY(-4px);
        }

        .ranking-podium-card.is-1 .ranking-place-badge {
            background: linear-gradient(135deg, #f59e0b, #fbbf24);
            color: #111827;
        }

        .ranking-podium-card.is-2 {
            background: linear-gradient(180deg, rgba(148, 163, 184, 0.18), rgba(255, 255, 255, 0.05));
            border-color: rgba(148, 163, 184, 0.38);
        }

        .ranking-podium-card.is-3 {
            background: linear-gradient(180deg, rgba(180, 83, 9, 0.18), rgba(255, 255, 255, 0.05));
            border-color: rgba(180, 83, 9, 0.36);
        }

        .ranking-place-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.32rem 0.65rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.92);
            font-weight: 800;
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.85rem;
        }

        .ranking-podium-name {
            font-size: 1.08rem;
            font-weight: 800;
            color: #ffffff;
            line-height: 1.35;
            margin-bottom: 0.55rem;
        }

        .ranking-podium-points {
            font-size: 2.2rem;
            font-weight: 900;
            letter-spacing: -0.05em;
            color: #ffffff;
            line-height: 1;
            margin-bottom: 0.35rem;
        }

        .ranking-podium-note {
            color: rgba(255, 255, 255, 0.72);
            font-size: 0.9rem;
        }

        .ranking-table-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.09);
            border-radius: 26px;
            padding: 1rem;
            box-shadow: 0 14px 32px rgba(0, 0, 0, 0.14);
            overflow: hidden;
        }

        .ranking-table-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-bottom: 0.85rem;
        }

        .ranking-table-title {
            font-size: 1.05rem;
            font-weight: 800;
            color: #ffffff;
        }

        .ranking-table-caption {
            color: rgba(255, 255, 255, 0.72);
            font-size: 0.9rem;
        }

        .ranking-table-wrap {
            overflow-x: auto;
        }

        table.ranking-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 620px;
            font-size: 0.95rem;
        }

        .ranking-table thead th {
            text-align: left;
            padding: 0.82rem 0.8rem;
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: rgba(255, 255, 255, 0.58);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .ranking-table tbody td {
            padding: 0.88rem 0.8rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            color: rgba(255, 255, 255, 0.95);
            vertical-align: middle;
        }

        .ranking-table tbody tr:hover {
            background: rgba(255, 255, 255, 0.04);
        }

        .ranking-table tbody tr.top-1 {
            background: rgba(245, 158, 11, 0.12);
        }

        .ranking-table tbody tr.top-2 {
            background: rgba(148, 163, 184, 0.1);
        }

        .ranking-table tbody tr.top-3 {
            background: rgba(180, 83, 9, 0.1);
        }

        .ranking-pos {
            font-weight: 900;
            color: #ffffff;
            width: 78px;
        }

        .ranking-user {
            font-weight: 700;
        }

        .ranking-points {
            font-weight: 900;
            text-align: right;
        }

        .ranking-num {
            text-align: right;
            font-variant-numeric: tabular-nums;
        }

        .ranking-empty {
            background: rgba(255, 255, 255, 0.05);
            border: 1px dashed rgba(255, 255, 255, 0.16);
            border-radius: 22px;
            padding: 1.25rem 1rem;
            color: rgba(255, 255, 255, 0.78);
        }

        @media (max-width: 900px) {
            .ranking-podium-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 760px) {
            .ranking-title {
                font-size: 1.75rem;
            }

            .ranking-metric-value {
                font-size: 1.55rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _normalizar_busca(texto: Optional[str]) -> str:
    return normalizar_texto(texto or "")


def _filtrar_ranking(ranking: List[Tuple[int, object]], busca: str) -> List[Tuple[int, object]]:
    busca_normalizada = _normalizar_busca(busca)
    if not busca_normalizada:
        return list(ranking)
    return [item for item in ranking if busca_normalizada in _normalizar_busca(item[1].nome)]


def _calcular_media_pontos(ranking: List) -> float:
    if not ranking:
        return 0.0
    total = sum(int(item.pontuacao_total or 0) for item in ranking)
    return round(total / len(ranking), 1)


def _render_metricas_premiacao(premiacao: dict) -> None:
    st.markdown('<div class="ranking-section-label">Premiacao</div>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Usuarios pagos/aprovados", int(premiacao["total_usuarios_aprovados"]))
    with col2:
        st.metric("Valor acumulado", formatar_moeda_brl(premiacao["valor_acumulado"]))
    with col3:
        st.metric("1o lugar", formatar_moeda_brl(premiacao["primeiro"]))
    with col4:
        st.metric("2o lugar", formatar_moeda_brl(premiacao["segundo"]))
    with col5:
        st.metric("3o lugar", formatar_moeda_brl(premiacao["terceiro"]))


def _render_header(
    lider_nome: str,
    lider_pontos: int,
    total_participantes: int,
    maior_pontuacao: int,
    media_pontos: float,
) -> None:
    st.markdown(
        """
        <div class="ranking-hero">
            <div class="ranking-kicker">Classificacao geral</div>
            <div class="ranking-title">Ranking do Bolao</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        col1, col2, col3, col4 = st.columns(4)
        cards = [
            ("1o colocado", lider_nome or "N/D", f"Pontuacao: {lider_pontos}"),
            ("Participantes", str(total_participantes), "Total de usuarios no bolao"),
            ("Maior pontuacao", str(maior_pontuacao), "Melhor desempenho registrado"),
            ("Media de pontos", f"{media_pontos:.1f}", "Media da classificacao atual"),
        ]
        for coluna, (label, value, hint) in zip((col1, col2, col3, col4), cards):
            with coluna:
                st.markdown(
                    f"""
                    <div class="ranking-metric-card">
                        <div class="ranking-metric-label">{html.escape(label)}</div>
                        <div class="ranking-metric-value">{html.escape(value)}</div>
                        <div class="ranking-metric-hint">{html.escape(hint)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def _render_podium_card(posicao: int, item, destaque: bool = False) -> None:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    classe = f"ranking-podium-card is-{posicao}"
    if destaque:
        classe += " is-highlighted"

    st.markdown(
        dedent(
            f"""
            <div class="{classe}">
                <div class="ranking-place-badge">{medals.get(posicao, f'{posicao}o')} lugar</div>
                <div class="ranking-podium-name">{html.escape(str(item.nome))}</div>
                <div class="ranking-podium-points">{int(item.pontuacao_total or 0)}</div>
                <div class="ranking-podium-note">Pontuacao total acumulada</div>
            </div>
            """
        ).strip(),
        unsafe_allow_html=True,
    )


def _render_podium(ranking: List) -> None:
    st.markdown('<div class="ranking-section-label">Podio</div>', unsafe_allow_html=True)
    with st.container():
        col1, col2, col3 = st.columns(3, gap="medium")
        top3 = list(ranking[:3])
        podium_map = {1: None, 2: None, 3: None}
        for idx, item in enumerate(top3, start=1):
            podium_map[idx] = item

        with col1:
            if podium_map[1] is not None:
                _render_podium_card(1, podium_map[1], destaque=True)
            else:
                st.markdown(
                    "<div class='ranking-empty'>Ainda nao ha dados para o 1o lugar.</div>",
                    unsafe_allow_html=True,
                )
        with col2:
            if podium_map[2] is not None:
                _render_podium_card(2, podium_map[2])
            else:
                st.markdown(
                    "<div class='ranking-empty'>Ainda nao ha dados para o 2o lugar.</div>",
                    unsafe_allow_html=True,
                )
        with col3:
            if podium_map[3] is not None:
                _render_podium_card(3, podium_map[3])
            else:
                st.markdown(
                    "<div class='ranking-empty'>Ainda nao ha dados para o 3o lugar.</div>",
                    unsafe_allow_html=True,
                )


def _montar_linhas_tabela(ranking: List[Tuple[int, object]]) -> str:
    linhas = []
    for posicao, item in ranking:
        classe = []
        if posicao == 1:
            classe.append("top-1")
        elif posicao == 2:
            classe.append("top-2")
        elif posicao == 3:
            classe.append("top-3")

        exatos = getattr(item, "placares_exatos", 0) or 0
        resultados = getattr(item, "resultados_certos", 0) or 0
        especiais = getattr(item, "especiais_acertos", 0) or 0
        colunas_extra = (
            f"<td class='ranking-num'>{html.escape(str(int(exatos)))}</td>"
            f"<td class='ranking-num'>{html.escape(str(int(resultados)))}</td>"
            f"<td class='ranking-num'>{html.escape(str(int(especiais)))}</td>"
        )

        linhas.append(
            (
                f'<tr class="{" ".join(classe)}">'
                f'<td class="ranking-pos">{posicao}</td>'
                f'<td class="ranking-user">{html.escape(str(item.nome))}</td>'
                f'<td class="ranking-points ranking-num">{int(item.pontuacao_total or 0)}</td>'
                f"{colunas_extra}"
                "</tr>"
            )
        )
    return "".join(linhas)


def _render_tabela_ranking(ranking: List[Tuple[int, object]]) -> None:
    cabecalhos = (
        "<thead>"
        "<tr>"
        "<th>Posicao</th>"
        "<th>Participante</th>"
        "<th style=\"text-align:right;\">Pontos</th>"
        "<th style=\"text-align:right;\" title=\"Placares exatos acertados\">Exatos</th>"
        "<th style=\"text-align:right;\" title=\"Resultados corretos (sem placar exato)\">Result.</th>"
        "<th style=\"text-align:right;\" title=\"Palpites especiais acertados\">Esp.</th>"
        "</tr>"
        "</thead>"
    )

    html_tabela = dedent(
        f"""
        <div class="ranking-table-card">
            <div class="ranking-table-header">
                <div>
                    <div class="ranking-table-title">Classificacao geral</div>
                    <div class="ranking-table-caption">Desempate: exatos &gt; resultados &gt; especiais &gt; nome.</div>
                </div>
            </div>
            <div class="ranking-table-wrap">
                <table class="ranking-table">{cabecalhos}<tbody>{_montar_linhas_tabela(ranking)}</tbody></table>
            </div>
        </div>
        """
    ).strip()
    st.markdown(html_tabela, unsafe_allow_html=True)


def render_tela_ranking() -> None:
    """Renderiza o ranking ordenado pela pontuacao total."""
    _render_estilos_ranking()

    ranking = listar_ranking_atual()
    premiacao = obter_premiacao_bolao()

    if not ranking:
        st.markdown(
            dedent(
                """
                <div class="ranking-hero">
                    <div class="ranking-kicker">Classificacao geral</div>
                    <div class="ranking-title">Ranking do Bolao</div>
                    <div class="ranking-subtitle">
                        Ainda nao ha dados suficientes para montar o ranking.
                    </div>
                </div>
                <div class="ranking-empty">
                    Ainda nao ha dados suficientes para montar o ranking.
                </div>
                """
            ).strip(),
            unsafe_allow_html=True,
        )
        _render_metricas_premiacao(premiacao)
        return

    ranking_ordenado = list(ranking)
    ranking_posicionado = list(enumerate(ranking_ordenado, start=1))
    maior_pontuacao = int(max(item.pontuacao_total for item in ranking_ordenado))
    media_pontos = _calcular_media_pontos(ranking_ordenado)
    total_participantes = len(ranking_ordenado)
    lider = ranking_ordenado[0]

    _render_header(
        lider_nome=str(lider.nome),
        lider_pontos=int(lider.pontuacao_total or 0),
        total_participantes=total_participantes,
        maior_pontuacao=maior_pontuacao,
        media_pontos=media_pontos,
    )

    _render_metricas_premiacao(premiacao)

    busca_col, limite_col = st.columns([3, 1])
    with busca_col:
        busca = st.text_input(
            "Buscar participante",
            placeholder="Digite o nome para filtrar a tabela",
            value="",
        )
    with limite_col:
        opcoes_limite = ["Todos", "Top 10", "Top 20", "Top 50"]
        limite_rotulo = st.selectbox("Exibir", opcoes_limite, index=0)

    ranking_filtrado = _filtrar_ranking(ranking_posicionado, busca)
    if limite_rotulo != "Todos":
        limite_numero = int(limite_rotulo.split()[1])
        ranking_filtrado = ranking_filtrado[:limite_numero]

    st.caption("Os destaques acima consideram o ranking completo; a tabela abaixo pode ser filtrada.")

    _render_podium(ranking_ordenado)

    st.markdown('<div class="ranking-section-label">Tabela completa</div>', unsafe_allow_html=True)
    if ranking_filtrado:
        _render_tabela_ranking(ranking_filtrado)
    else:
        st.markdown(
            "<div class='ranking-empty'>Nenhum participante encontrado para o filtro informado.</div>",
            unsafe_allow_html=True,
        )
