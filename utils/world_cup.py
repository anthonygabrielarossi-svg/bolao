"""Mapeamentos e inferencias da Copa do Mundo 2026."""

from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict
from typing import Dict, Optional, Tuple

from .flags import get_flag_emoji as _shared_get_flag_emoji


def normalizar_texto(texto: object) -> str:
    """Normaliza texto para comparacoes e lookup."""
    bruto = unicodedata.normalize("NFKD", str(texto or ""))
    sem_acentos = "".join(ch for ch in bruto if not unicodedata.combining(ch))
    sem_separadores = re.sub(r"[^a-zA-Z0-9]+", " ", sem_acentos)
    return " ".join(sem_separadores.split()).strip().lower()


WORLD_CUP_GROUPS_2026: "OrderedDict[str, Tuple[str, ...]]" = OrderedDict(
    [
        ("Grupo A", ("Mexico", "South Africa", "South Korea", "Czechia")),
        ("Grupo B", ("Canada", "Qatar", "Switzerland", "Bosnia & Herzegovina")),
        ("Grupo C", ("Brazil", "Morocco", "Haiti", "Scotland")),
        ("Grupo D", ("Australia", "Türkiye", "USA", "Paraguay")),
        ("Grupo E", ("Germany", "Curaçao", "Côte d'Ivoire", "Ecuador")),
        ("Grupo F", ("Netherlands", "Japan", "Sweden", "Tunisia")),
        ("Grupo G", ("Spain", "Cabo Verde", "Saudi Arabia", "Uruguay")),
        ("Grupo H", ("Belgium", "Egypt", "Iran", "New Zealand")),
        ("Grupo I", ("France", "Senegal", "Iraq", "Norway")),
        ("Grupo J", ("Argentina", "Algeria", "Austria", "Jordan")),
        ("Grupo K", ("Portugal", "DR Congo", "Colombia", "Uzbekistan")),
        ("Grupo L", ("England", "Croatia", "Ghana", "Panama")),
    ]
)

_TEAM_DETAILS: Dict[str, Tuple[str, str]] = {
    "Mexico": ("México", "🇲🇽"),
    "South Africa": ("África do Sul", "🇿🇦"),
    "South Korea": ("Coreia do Sul", "🇰🇷"),
    "Czechia": ("República Tcheca", "🇨🇿"),
    "Canada": ("Canadá", "🇨🇦"),
    "Bosnia & Herzegovina": ("Bósnia e Herzegovina", "🇧🇦"),
    "USA": ("EUA", "🇺🇸"),
    "Paraguay": ("Paraguai", "🇵🇾"),
    "Qatar": ("Catar", "🇶🇦"),
    "Switzerland": ("Suíça", "🇨🇭"),
    "Brazil": ("Brasil", "🇧🇷"),
    "Morocco": ("Marrocos", "🇲🇦"),
    "Haiti": ("Haiti", "🇭🇹"),
    "Scotland": ("Escócia", "🏴"),
    "Australia": ("Austrália", "🇦🇺"),
    "Türkiye": ("Turquia", "🇹🇷"),
    "Germany": ("Alemanha", "🇩🇪"),
    "Curaçao": ("Curaçao", "🇨🇼"),
    "Netherlands": ("Países Baixos", "🇳🇱"),
    "Japan": ("Japão", "🇯🇵"),
    "Côte d'Ivoire": ("Costa do Marfim", "🇨🇮"),
    "Ecuador": ("Equador", "🇪🇨"),
    "Sweden": ("Suécia", "🇸🇪"),
    "Tunisia": ("Tunísia", "🇹🇳"),
    "Spain": ("Espanha", "🇪🇸"),
    "Cabo Verde": ("Cabo Verde", "🇨🇻"),
    "Belgium": ("Bélgica", "🇧🇪"),
    "Egypt": ("Egito", "🇪🇬"),
    "Saudi Arabia": ("Arábia Saudita", "🇸🇦"),
    "Uruguay": ("Uruguai", "🇺🇾"),
    "Iran": ("Irã", "🇮🇷"),
    "New Zealand": ("Nova Zelândia", "🇳🇿"),
    "France": ("França", "🇫🇷"),
    "Senegal": ("Senegal", "🇸🇳"),
    "Iraq": ("Iraque", "🇮🇶"),
    "Norway": ("Noruega", "🇳🇴"),
    "Argentina": ("Argentina", "🇦🇷"),
    "Algeria": ("Argélia", "🇩🇿"),
    "Austria": ("Áustria", "🇦🇹"),
    "Jordan": ("Jordânia", "🇯🇴"),
    "Portugal": ("Portugal", "🇵🇹"),
    "DR Congo": ("RD Congo", "🇨🇩"),
    "England": ("Inglaterra", "🏴"),
    "Croatia": ("Croácia", "🇭🇷"),
    "Ghana": ("Gana", "🇬🇭"),
    "Panama": ("Panamá", "🇵🇦"),
    "Uzbekistan": ("Uzbequistão", "🇺🇿"),
    "Colombia": ("Colômbia", "🇨🇴"),
}

_TEAM_ALIASES: Dict[str, Tuple[str, ...]] = {
    "Mexico": ("México",),
    "South Africa": ("África do Sul",),
    "South Korea": ("Coreia do Sul", "Republic of Korea", "Korea Republic"),
    "Czechia": ("República Tcheca", "Czech Republic", "Czech Rep."),
    "Canada": ("Canadá",),
    "Bosnia & Herzegovina": ("Bosnia and Herzegovina", "Bósnia", "Bósnia e Herzegovina"),
    "USA": ("United States", "United States of America", "Estados Unidos", "U.S.A.", "US"),
    "Paraguay": ("Paraguai",),
    "Qatar": ("Catar",),
    "Switzerland": ("Suíça",),
    "Brazil": ("Brasil",),
    "Morocco": ("Marrocos",),
    "Haiti": ("Haiti",),
    "Scotland": ("Escócia",),
    "Australia": ("Austrália",),
    "Türkiye": ("Turkey", "Turquia"),
    "Germany": ("Alemanha",),
    "Curaçao": ("Curacao", "Curaçao"),
    "Netherlands": ("Países Baixos", "Holland"),
    "Japan": ("Japão",),
    "Côte d'Ivoire": ("Costa do Marfim", "Ivory Coast"),
    "Ecuador": ("Equador",),
    "Sweden": ("Suécia",),
    "Tunisia": ("Tunísia",),
    "Spain": ("Espanha",),
    "Cabo Verde": ("Cape Verde",),
    "Belgium": ("Bélgica",),
    "Egypt": ("Egito",),
    "Saudi Arabia": ("Arábia Saudita",),
    "Uruguay": ("Uruguai",),
    "Iran": ("Irã",),
    "New Zealand": ("Nova Zelândia",),
    "France": ("França",),
    "Senegal": ("Senegal",),
    "Iraq": ("Iraque",),
    "Norway": ("Noruega",),
    "Argentina": ("Argentina",),
    "Algeria": ("Argélia",),
    "Austria": ("Áustria",),
    "Jordan": ("Jordânia",),
    "Portugal": ("Portugal",),
    "DR Congo": ("RD Congo", "Democratic Republic of the Congo", "Congo DR"),
    "England": ("Inglaterra",),
    "Croatia": ("Croácia",),
    "Ghana": ("Gana",),
    "Panama": ("Panamá",),
    "Uzbekistan": ("Uzbequistão",),
    "Colombia": ("Colômbia",),
}

_TEAM_CODE_ALIASES: Dict[str, Tuple[str, ...]] = {
    "Mexico": ("MX", "MEX"),
    "South Africa": ("ZA", "RSA"),
    "South Korea": ("KR", "KOR"),
    "Czechia": ("CZ", "CZE"),
    "Canada": ("CA", "CAN"),
    "Bosnia & Herzegovina": ("BA", "BIH"),
    "Qatar": ("QA", "QAT"),
    "Switzerland": ("CH", "SUI"),
    "USA": ("US", "USA"),
    "Argentina": ("AR", "ARG"),
    "France": ("FR", "FRA"),
    "England": ("ENG", "GB", "GBR"),
    "Portugal": ("PT", "POR"),
    "Spain": ("ES", "ESP"),
    "Germany": ("DE", "GER"),
    "Netherlands": ("NL", "NED"),
    "Japan": ("JP", "JPN"),
    "Uruguay": ("UY", "URU"),
    "Morocco": ("MA", "MAR"),
    "Tunisia": ("TN", "TUN"),
    "Egypt": ("EG", "EGY"),
    "Iran": ("IR", "IRN"),
    "New Zealand": ("NZ", "NZL"),
    "Austria": ("AT", "AUT"),
    "Norway": ("NO", "NOR"),
    "Croatia": ("HR", "CRO"),
    "Colombia": ("CO", "COL"),
    "Ghana": ("GH", "GHA"),
    "Panama": ("PA", "PAN"),
    "Uzbekistan": ("UZ", "UZB"),
    "DR Congo": ("CD", "COD", "DRC"),
    "Cabo Verde": ("CV", "CPV"),
    "Saudi Arabia": ("SA", "KSA"),
    "Algeria": ("DZ", "ALG"),
    "Jordan": ("JO", "JOR"),
    "Brazil": ("BR", "BRA"),
    "Haiti": ("HT", "HAI"),
    "Scotland": ("SCO", "SC"),
    "Australia": ("AU", "AUS"),
    "Curaçao": ("CW", "CUR"),
    "Cote d'Ivoire": ("CI", "CIV"),
    "Côte d'Ivoire": ("CI", "CIV"),
}

_CANONICAL_BY_NORMALIZED: Dict[str, str] = {}
_DISPLAY_BY_NORMALIZED: Dict[str, str] = {}
_FLAG_BY_NORMALIZED: Dict[str, str] = {}
_GROUP_BY_NORMALIZED: Dict[str, str] = {}

for grupo, times in WORLD_CUP_GROUPS_2026.items():
    for time in times:
        chave = normalizar_texto(time)
        _CANONICAL_BY_NORMALIZED[chave] = time
        _GROUP_BY_NORMALIZED[chave] = grupo

        display, flag = _TEAM_DETAILS[time]
        _DISPLAY_BY_NORMALIZED[chave] = display
        _FLAG_BY_NORMALIZED[chave] = flag

        aliases = (display,) + _TEAM_ALIASES.get(time, tuple()) + _TEAM_CODE_ALIASES.get(time, tuple())
        for alias in aliases:
            alias_key = normalizar_texto(alias)
            _CANONICAL_BY_NORMALIZED.setdefault(alias_key, time)
            _GROUP_BY_NORMALIZED.setdefault(alias_key, grupo)
            _DISPLAY_BY_NORMALIZED.setdefault(alias_key, display)


def normalizar_grupo_copa(grupo: Optional[str]) -> Optional[str]:
    """Normaliza grupos como `Grupo A`."""
    if not grupo:
        return None

    texto = normalizar_texto(grupo).upper()
    if not texto:
        return None

    if texto.startswith("GRUPO "):
        letra = texto.split()[-1][:1]
    else:
        letra = texto[:1]

    if letra and letra in "ABCDEFGHIJKL":
        return f"Grupo {letra}"

    correspondencia = re.search(r"\b([A-L])\b", texto)
    if correspondencia:
        return f"Grupo {correspondencia.group(1)}"

    return None


def canonicalizar_time(nome: Optional[str]) -> str:
    """Retorna o nome canonico usado internamente pelo bolao."""
    if not nome:
        return ""
    chave = normalizar_texto(nome)
    return _CANONICAL_BY_NORMALIZED.get(chave, str(nome).strip())


def formatar_nome_time(nome: Optional[str]) -> str:
    """Formata nomes de selecoes para exibicao amigavel."""
    if not nome:
        return ""
    canonico = canonicalizar_time(nome)
    return _DISPLAY_BY_NORMALIZED.get(normalizar_texto(canonico), str(nome).strip())


def get_flag_emoji(nome: Optional[str]) -> str:
    """Retorna a bandeira da selecao."""
    return _shared_get_flag_emoji(nome or "")


def obter_times_do_grupo(grupo: Optional[str]) -> Tuple[str, ...]:
    """Retorna as selecoes oficiais de um grupo da Copa 2026."""
    grupo_normalizado = normalizar_grupo_copa(grupo)
    if not grupo_normalizado:
        return tuple()
    return WORLD_CUP_GROUPS_2026.get(grupo_normalizado, tuple())


def inferir_grupo_por_times(time_casa: Optional[str], time_fora: Optional[str] = None) -> Optional[str]:
    """Infere o grupo apenas quando os dois times pertencem ao mesmo grupo."""
    if not time_casa or not time_fora:
        return None

    chave_casa = normalizar_texto(canonicalizar_time(time_casa) or time_casa)
    chave_fora = normalizar_texto(canonicalizar_time(time_fora) or time_fora)
    grupo_casa = _GROUP_BY_NORMALIZED.get(chave_casa)
    grupo_fora = _GROUP_BY_NORMALIZED.get(chave_fora)

    if grupo_casa and grupo_fora and grupo_casa == grupo_fora:
        return grupo_casa
    return None


def inferir_grupo_copa(time_a: Optional[str], time_b: Optional[str] = None) -> Optional[str]:
    """Alias de compatibilidade para a inferencia de grupo por times."""
    return inferir_grupo_por_times(time_a, time_b)
