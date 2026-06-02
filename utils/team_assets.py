"""Utilitarios de imagens e identidades visuais dos times."""

from __future__ import annotations

import html
from typing import Any, Dict, Iterable, Optional

from .flags import get_flag_emoji
from .formatters import formatar_nome_time, normalizar_texto
from .world_cup import canonicalizar_time


def get_team_logo_url(team_id: Any) -> Optional[str]:
    """Monta a URL publica do escudo/imagem do time."""
    if team_id in (None, ""):
        return None
    try:
        team_id_int = int(team_id)
    except (TypeError, ValueError):
        return None
    if team_id_int <= 0:
        return None
    return f"https://sports.bzzoiro.com/img/team/{team_id_int}/"


def construir_mapa_logos_por_jogos(jogos: Iterable[Any]) -> Dict[str, Dict[str, Optional[str]]]:
    """Cria um lookup por time com id e logo extraidos dos jogos."""
    lookup: Dict[str, Dict[str, Optional[str]]] = {}

    for jogo in jogos or []:
        for nome_time, team_id, logo_url in (
            (getattr(jogo, "time_casa", None) or getattr(jogo, "time_a", None), getattr(jogo, "home_team_id", None), getattr(jogo, "home_team_logo_url", None)),
            (getattr(jogo, "time_fora", None) or getattr(jogo, "time_b", None), getattr(jogo, "away_team_id", None), getattr(jogo, "away_team_logo_url", None)),
        ):
            if not nome_time:
                continue
            chave = normalizar_texto(canonicalizar_time(nome_time) or nome_time)
            if not chave:
                continue

            entrada = lookup.setdefault(
                chave,
                {
                    "team_id": None,
                    "logo_url": None,
                    "nome": formatar_nome_time(nome_time) or str(nome_time).strip(),
                },
            )

            if team_id not in (None, ""):
                try:
                    entrada["team_id"] = int(team_id)
                except (TypeError, ValueError):
                    pass
                entrada["logo_url"] = get_team_logo_url(team_id)
            elif logo_url and not entrada.get("logo_url"):
                entrada["logo_url"] = str(logo_url).strip()

            if not entrada.get("nome"):
                entrada["nome"] = formatar_nome_time(nome_time) or str(nome_time).strip()

    return lookup


def render_team_identity_html(
    nome_time: Optional[str],
    *,
    team_id: Any = None,
    logo_url: Optional[str] = None,
) -> str:
    """Retorna um bloco HTML com logo oficial e nome do time."""
    nome_exibicao = formatar_nome_time(nome_time) or str(nome_time or "").strip()
    if not nome_exibicao:
        nome_exibicao = "-"

    logo = logo_url or get_team_logo_url(team_id)
    nome_escapado = html.escape(nome_exibicao)
    bandeira = get_flag_emoji(nome_time or nome_exibicao)
    flag_html = f'<span class="wc-team-flag">{bandeira}</span>' if bandeira else ""

    if logo:
        logo_escapada = html.escape(str(logo))
        return (
            '<span class="wc-team-identity">'
            f'{flag_html}'
            f'<span class="wc-team-name">{nome_escapado}</span>'
            "</span>"
        )

    return (
        '<span class="wc-team-identity">'
        f'{flag_html}'
        f'<span class="wc-team-name">{nome_escapado}</span>'
        "</span>"
    )


__all__ = [
    "construir_mapa_logos_por_jogos",
    "get_team_logo_url",
    "render_team_identity_html",
]
