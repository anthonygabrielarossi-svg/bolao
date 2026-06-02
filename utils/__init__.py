"""Utilitarios do projeto da Copa do Mundo."""

from .flags import get_flag_emoji
from .datetime_utils import bloquear_palpite_para_jogo, jogo_ja_comecou, palpite_bloqueado_para_jogo, parse_iso_datetime
from .formatters import canonicalizar_time, formatar_nome_time, normalizar_texto
from .team_assets import construir_mapa_logos_por_jogos, get_team_logo_url, render_team_identity_html
from .world_cup import (
    WORLD_CUP_GROUPS_2026,
    get_flag_cdn_url,
    obter_times_do_grupo,
    inferir_grupo_copa,
    inferir_grupo_por_times,
    normalizar_grupo_copa,
)

__all__ = [
    "WORLD_CUP_GROUPS_2026",
    "get_flag_cdn_url",
    "canonicalizar_time",
    "bloquear_palpite_para_jogo",
    "construir_mapa_logos_por_jogos",
    "formatar_nome_time",
    "get_flag_emoji",
    "get_team_logo_url",
    "inferir_grupo_copa",
    "inferir_grupo_por_times",
    "jogo_ja_comecou",
    "normalizar_grupo_copa",
    "normalizar_texto",
    "palpite_bloqueado_para_jogo",
    "obter_times_do_grupo",
    "parse_iso_datetime",
    "render_team_identity_html",
]
