"""Tela de auditoria de pontuacao do usuario logado."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.ranking_service import detalhar_pontuacao_usuario


@st.cache_data(ttl=60, show_spinner=False)
def _detalhar_cache(user_id: int):
    return detalhar_pontuacao_usuario(user_id)


def _clear_cache(user_id: int) -> None:
    _detalhar_cache.clear()


_LABEL_CATEGORIA = {
    "campeao": "Campeão",
    "vice": "Vice-campeão",
    "artilheiro": "Artilheiro",
    "melhor_jogador": "Melhor jogador",
}


def _formatar_categoria(cat: str) -> str:
    if cat in _LABEL_CATEGORIA:
        return _LABEL_CATEGORIA[cat]
    if cat.startswith("primeiro_Grupo"):
        return f"1º {cat.replace('primeiro_', '')}"
    if cat.startswith("segundo_Grupo"):
        return f"2º {cat.replace('segundo_', '')}"
    if cat.startswith("terceiro_Grupo"):
        return f"3º classificado {cat.replace('terceiro_', '')}"
    return cat


def render_tela_minha_pontuacao(user_id: int) -> None:
    st.title("Minha Pontuação")

    col_refresh, _ = st.columns([1, 5])
    if col_refresh.button("🔄 Atualizar", key="btn_refresh_pontuacao"):
        _clear_cache(user_id)
        st.rerun()

    with st.spinner("Carregando..."):
        try:
            detalhes = _detalhar_cache(user_id)
        except Exception as exc:
            st.error(f"Erro ao carregar pontuação: {exc}")
            return

    total = detalhes["total_partidas"] + detalhes["total_especiais"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total geral", f"{total} pts")
    col2.metric("Partidas", f"{detalhes['total_partidas']} pts")
    col3.metric("Especiais", f"{detalhes['total_especiais']} pts")

    st.caption(f"Jogos finalizados considerados: {detalhes['jogos_finalizados']}")

    st.divider()

    # --- Partidas ---
    st.subheader("Pontos por partida")
    if detalhes["partidas"]:
        rows = []
        for d in sorted(detalhes["partidas"], key=lambda x: -x["pontos"]):
            pts = d["pontos"]
            if pts == 10:
                badge = "✅ Exato"
            elif pts == 5:
                badge = "🟡 Resultado"
            else:
                badge = "❌ Errou"
            rows.append({
                "Jogo": d["jogo"],
                "Seu palpite": d["palpite"],
                "Placar real": d["placar_real"],
                "Resultado": badge,
                "Pontos": pts,
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum jogo finalizado com palpite cadastrado ainda.")

    st.divider()

    # --- Especiais ---
    st.subheader("Palpites especiais")
    especiais = [e for e in detalhes["especiais"] if e["palpite"]]
    if especiais:
        rows_esp = []
        for e in especiais:
            pts = e["pontos"]
            if pts > 0:
                badge = f"✅ +{pts} pts"
            elif e["oficial"]:
                badge = "❌ Errou"
            else:
                badge = "⏳ Aguardando"
            rows_esp.append({
                "Categoria": _formatar_categoria(e["categoria"]),
                "Seu palpite": e["palpite"],
                "Oficial": e["oficial"] or "—",
                "Resultado": badge,
                "Pontos": pts,
            })
        df_esp = pd.DataFrame(rows_esp)
        st.dataframe(df_esp, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum palpite especial cadastrado.")
