"""Cliente HTTP da API BSD para jogos da Copa do Mundo 2026.

Este modulo resolve a season da liga 27, percorre a paginacao do endpoint de
eventos e normaliza cada evento para o modelo local do bolao.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests

import settings  # noqa: F401 - garante carga do `.env` mesmo em imports diretos.
from database import COMPETICAO_PADRAO, FASE_NAO_MAPEADA, Jogo
from utils.team_assets import get_team_logo_url
from utils.world_cup import inferir_grupo_por_times


BASE_URL = "https://sports.bzzoiro.com/api/"
WORLD_CUP_LEAGUE_ID = 27
WORLD_CUP_NAME = COMPETICAO_PADRAO
WORLD_CUP_TZ = "America/Sao_Paulo"
WORLD_CUP_FALLBACK_DATE_FROM = "2026-06-01"
WORLD_CUP_FALLBACK_DATE_TO = "2026-07-31"
SEASONS_ENDPOINT = urljoin(BASE_URL, "seasons/")
EVENTS_ENDPOINT = urljoin(BASE_URL, "events/")
EVENT_DETAIL_ENDPOINT = urljoin(BASE_URL, "events/{event_id}/")
LIVE_ENDPOINT = urljoin(BASE_URL, "live/")
PLAYERS_ENDPOINT = urljoin(BASE_URL, "players/")
DEFAULT_TIMEOUT = 30


class BSDAPIError(RuntimeError):
    """Erro de integracao com a API BSD."""

    def __init__(self, message: str, status_code: Optional[int] = None, url: Optional[str] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


def _extrair_mensagem_erro(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        texto = (response.text or "").strip()
        return texto or response.reason or "Resposta invalida"

    if isinstance(payload, dict):
        for chave in ("detail", "message", "error", "errors"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        return str(payload)

    if isinstance(payload, list):
        return ", ".join(str(item) for item in payload) or "Resposta invalida"

    return str(payload)


def _request_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    try:
        headers = settings.get_headers()
    except RuntimeError as exc:
        raise BSDAPIError(str(exc), url=url) from exc

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise BSDAPIError(f"Timeout ao consultar {url}", url=url) from exc
    except requests.ConnectionError as exc:
        raise BSDAPIError(f"Falha de conexao ao consultar {url}: {exc}", url=url) from exc
    except requests.RequestException as exc:
        raise BSDAPIError(f"Falha de rede ao consultar {url}: {exc}", url=url) from exc

    settings.debug_log(f"[BSD] {response.request.method} {response.url} -> {response.status_code}")

    if response.status_code == 401:
        raise BSDAPIError("Token invalido ou nao configurado", 401, response.url)

    if response.status_code >= 400:
        mensagem = _extrair_mensagem_erro(response)
        raise BSDAPIError(f"HTTP {response.status_code} ao consultar {response.url}: {mensagem}", response.status_code, response.url)

    if not (response.text or "").strip():
        raise BSDAPIError(f"Resposta vazia ao consultar {response.url}", url=response.url)

    try:
        return response.json()
    except ValueError as exc:
        raise BSDAPIError(f"JSON invalido ao consultar {response.url}", url=response.url) from exc


def _to_int_or_none(valor: Any) -> Optional[int]:
    if valor is None or valor == "":
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _texto_dict(objeto: Any, *campos: str) -> str:
    if isinstance(objeto, dict):
        for campo in campos:
            valor = objeto.get(campo)
            if valor not in (None, ""):
                return str(valor).strip()
    if isinstance(objeto, str):
        return objeto.strip()
    return ""


def _normalize_text(texto: Any) -> str:
    return " ".join(str(texto or "").split()).strip().lower()


def _to_bool(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return bool(valor)
    if isinstance(valor, str):
        texto = valor.strip().lower()
        return texto in {"1", "true", "yes", "y", "sim", "current"}
    return False


def _extrair_status(evento: Dict[str, Any]) -> str:
    status = evento.get("status")
    texto = _texto_dict(status, "name", "slug", "label", "title", "value")
    if texto:
        return texto
    if isinstance(status, str):
        return status.strip()
    return "notstarted"


def _extrair_time(evento: Dict[str, Any], prefixo: str) -> str:
    candidatos = (
        evento.get(f"{prefixo}_team_obj"),
        evento.get(f"{prefixo}_team"),
        evento.get(f"{prefixo}_team_name"),
        evento.get(f"{prefixo}_team_short_name"),
        evento.get(f"{prefixo}_team_info"),
        evento.get(prefixo),
    )
    for candidato in candidatos:
        nome = _texto_dict(candidato, "name", "short_name", "shortName", "title", "label", "abbr", "code")
        if nome:
            return nome
        if isinstance(candidato, str) and candidato.strip():
            return candidato.strip()

    return ""


def _extrair_team_id(evento: Dict[str, Any], prefixo: str) -> Optional[int]:
    candidatos = (
        evento.get(f"{prefixo}_team_obj"),
        evento.get(f"{prefixo}_team"),
        evento.get(f"{prefixo}_team_info"),
    )
    for candidato in candidatos:
        if isinstance(candidato, dict):
            for chave in ("id", "team_id", "teamId", "pk", "value"):
                valor = _to_int_or_none(candidato.get(chave))
                if valor is not None:
                    return valor
        else:
            valor = _to_int_or_none(candidato)
            if valor is not None:
                return valor
    return None


def _extrair_data(evento: Dict[str, Any]) -> Optional[str]:
    valor = (
        evento.get("event_date")
        or evento.get("date")
        or evento.get("start_date")
        or evento.get("kickoff")
        or evento.get("scheduled")
        or evento.get("utc_date")
        or evento.get("datetime")
    )
    if not valor:
        return None
    return str(valor).strip()


def _extrair_estadio(evento: Dict[str, Any]) -> Optional[str]:
    candidatos = (
        evento.get("stadium"),
        evento.get("stadium_obj"),
        evento.get("venue"),
        evento.get("venue_obj"),
        evento.get("arena"),
        evento.get("ground"),
        evento.get("location"),
    )
    for candidato in candidatos:
        nome = _texto_dict(candidato, "name", "title", "label", "short_name", "shortName")
        if nome:
            return nome
        if isinstance(candidato, str) and candidato.strip():
            return candidato.strip()
    return None


def _extrair_round_number(evento: Dict[str, Any]) -> Optional[int]:
    candidatos = (
        evento.get("round_number"),
        evento.get("round"),
        evento.get("round_no"),
        evento.get("matchday"),
    )
    for candidato in candidatos:
        if isinstance(candidato, dict):
            for chave in ("number", "round_number", "id", "round", "value"):
                valor = _to_int_or_none(candidato.get(chave))
                if valor is not None:
                    return valor
        else:
            valor = _to_int_or_none(candidato)
            if valor is not None:
                return valor
    return None


def _texto_evento(evento: Dict[str, Any], *campos: str) -> str:
    for campo in campos:
        valor = evento.get(campo)
        texto = _texto_dict(valor, "name", "title", "label", "slug", "value", "short_name")
        if texto:
            return texto
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return ""


_PLACEHOLDER_BRACKET_TOKEN_RE = re.compile(r"^(?:[WL]\d+|\d+[A-Z]|3[A-L])(?:/(?:[WL]\d+|\d+[A-Z]|3[A-L]))*$", re.IGNORECASE)


def identificar_placeholder_bracket(time_casa: Any, time_fora: Any = None) -> bool:
    """Identifica confrontos de chaveamento com tokens como W73, 1A ou 3C/3E."""
    def _normalizar_token(valor: Any) -> str:
        return "".join(str(valor or "").split()).upper()

    for time in (time_casa, time_fora):
        token = _normalizar_token(time)
        if token and _PLACEHOLDER_BRACKET_TOKEN_RE.fullmatch(token):
            return True
    return False


WORLD_CUP_2026_PHASE_BY_ROUND: Dict[int, str] = {
    1: "Fase de Grupos",
    2: "Fase de Grupos",
    3: "Fase de Grupos",
    5: "Oitavas de Final",
    6: "16-avos de Final",
    27: "Quartas de Final",
    28: "Semifinal",
    29: "Final",
    50: "Disputa de 3º Lugar",
}


def inferir_fase(evento_api: Dict[str, Any]) -> str:
    round_number = _extrair_round_number(evento_api)
    return WORLD_CUP_2026_PHASE_BY_ROUND.get(round_number, FASE_NAO_MAPEADA)


def _status_finalizado(status: str) -> bool:
    status_normalizado = status.strip().lower()
    return status_normalizado in {
        "finished",
        "ft",
        "fulltime",
        "full time",
        "complete",
        "completed",
        "final",
        "aet",
        "after extra time",
        "pen",
        "after penalties",
    }


def _coletar_paginado(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    rotulo: str = "registros",
    resumo: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Busca todas as paginas de um endpoint listavel."""
    itens: List[Dict[str, Any]] = []
    proxima_url = url
    parametros = dict(params or {})
    pagina = 1
    total_informado: Optional[int] = None

    while proxima_url:
        payload = _request_json(proxima_url, params=parametros, timeout=timeout)
        if isinstance(payload, list):
            if any(not isinstance(item, dict) for item in payload):
                raise BSDAPIError(f"A resposta de {proxima_url} trouxe itens em formato invalido.", url=proxima_url)
            settings.debug_log(f"[BSD] Pagina {pagina} de {rotulo}: {len(payload)} resultados")
            itens.extend(payload)
            break

        if not isinstance(payload, dict):
            raise BSDAPIError(f"Formato de resposta inesperado ao consultar {proxima_url}.", url=proxima_url)

        if total_informado is None:
            total_informado = _to_int_or_none(payload.get("count"))

        resultados = payload.get("results", [])
        if resultados is None:
            resultados = []
        if not isinstance(resultados, list):
            raise BSDAPIError(f"Campo 'results' invalido na resposta de {proxima_url}.", url=proxima_url)

        if any(not isinstance(item, dict) for item in resultados):
            raise BSDAPIError(f"A resposta de {proxima_url} trouxe itens em formato invalido.", url=proxima_url)

        settings.debug_log(f"[BSD] Pagina {pagina} de {rotulo}: {len(resultados)} resultados")
        itens.extend(resultados)

        next_url = payload.get("next")
        if next_url:
            proxima_url = urljoin(BASE_URL, str(next_url))
            parametros = {}
            pagina += 1
        else:
            proxima_url = None

    if resumo is not None:
        resumo["count"] = total_informado
        resumo["baixados"] = len(itens)
        resumo["paginas"] = pagina

    return itens


def _mesclar_eventos(base: Dict[str, Any], novo: Dict[str, Any]) -> Dict[str, Any]:
    """Mescla dois payloads do mesmo evento preservando os campos mais ricos."""
    if not base:
        return dict(novo)
    if not novo:
        return dict(base)

    mesclado = dict(base)
    for chave, valor in novo.items():
        if valor in (None, "", [], {}, ()):
            continue
        if chave not in mesclado or mesclado[chave] in (None, "", [], {}, ()):
            mesclado[chave] = valor
    return mesclado


def _unir_eventos(*listas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    por_id: Dict[int, Dict[str, Any]] = {}
    ordem: List[int] = []

    for lista in listas:
        for evento in lista:
            if not isinstance(evento, dict):
                continue
            evento_id = _to_int_or_none(evento.get("id"))
            if evento_id is None:
                continue
            if evento_id not in por_id:
                ordem.append(evento_id)
                por_id[evento_id] = dict(evento)
            else:
                por_id[evento_id] = _mesclar_eventos(por_id[evento_id], evento)

    def _chave_ordenacao(evento_id: int) -> tuple[str, int]:
        evento = por_id[evento_id]
        data = _extrair_data(evento) or ""
        return data, evento_id

    return [por_id[evento_id] for evento_id in sorted(ordem, key=_chave_ordenacao)]


def _valor_season_copa(season: Dict[str, Any]) -> tuple[int, int, int]:
    is_current = _to_bool(season.get("is_current"))
    year = _to_int_or_none(season.get("year")) or 0
    season_id = _to_int_or_none(season.get("id")) or 0

    score = 0
    if is_current:
        score += 1000
    if year == 2026:
        score += 500
    if "2026" in _normalize_text(season.get("name") or season.get("title")):
        score += 250

    return score, year, season_id


def obter_season_copa(timeout: int = DEFAULT_TIMEOUT) -> Optional[Dict[str, Any]]:
    """Busca a season atual da Copa do Mundo, priorizando `is_current` e 2026."""
    seasons = _coletar_paginado(
        SEASONS_ENDPOINT,
        params={"league": WORLD_CUP_LEAGUE_ID},
        timeout=timeout,
        rotulo="seasons",
    )

    if not seasons:
        settings.debug_log("[BSD] Nenhuma season encontrada para league=27.")
        return None

    candidatos = [season for season in seasons if isinstance(season, dict)]
    if not candidatos:
        settings.debug_log("[BSD] A resposta de seasons veio vazia ou invalida.")
        return None

    current = [season for season in candidatos if _to_bool(season.get("is_current"))]
    if current:
        selecionada = max(current, key=_valor_season_copa)
    else:
        candidatos_2026 = [
            season
            for season in candidatos
            if _to_int_or_none(season.get("year")) == 2026
            or "2026" in _normalize_text(season.get("name") or season.get("title"))
        ]
        if not candidatos_2026:
            settings.debug_log("[BSD] Nenhuma season atual ou de 2026 encontrada para league=27.")
            return None
        selecionada = max(candidatos_2026, key=_valor_season_copa)

    season_id = _to_int_or_none(selecionada.get("id"))
    settings.debug_log(
        "[BSD] Season selecionada: "
        f"id={season_id}, nome={selecionada.get('name') or selecionada.get('title') or '-'}, "
        f"current={_to_bool(selecionada.get('is_current'))}, "
        f"year={selecionada.get('year')}"
    )
    return selecionada


def buscar_todos_eventos_copa_com_resumo(
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Busca todos os eventos da Copa e devolve os dados com resumo diagnostico."""
    season = obter_season_copa(timeout=timeout)
    eventos_season: List[Dict[str, Any]] = []
    resumo: Dict[str, Any] = {
        "season_count": None,
        "season_baixados": 0,
        "fallback_count": None,
        "fallback_baixados": 0,
        "total_baixados": 0,
    }

    if season is not None:
        season_id = _to_int_or_none(season.get("id"))
        if season_id is not None:
            settings.debug_log(f"[BSD] Importando via season_id={season_id} e tz={WORLD_CUP_TZ}")
            resumo_season: Dict[str, Any] = {}
            eventos_season = _coletar_paginado(
                EVENTS_ENDPOINT,
                params={"season": season_id, "tz": WORLD_CUP_TZ},
                timeout=timeout,
                rotulo=f"events season={season_id}",
                resumo=resumo_season,
            )
            resumo["season_count"] = resumo_season.get("count")
            resumo["season_baixados"] = resumo_season.get("baixados", len(eventos_season))
            settings.debug_log(f"[BSD] {len(eventos_season)} eventos retornados pela season.")
        else:
            settings.debug_log("[BSD] Season selecionada sem id valido; ativando fallback por intervalo de datas.")
    else:
        settings.debug_log("[BSD] Nenhuma season valida encontrada; ativando fallback por intervalo de datas.")

    settings.debug_log(
        f"Fallback para intervalo {WORLD_CUP_FALLBACK_DATE_FROM} até {WORLD_CUP_FALLBACK_DATE_TO}"
    )
    resumo_fallback: Dict[str, Any] = {}
    eventos_fallback = _coletar_paginado(
        EVENTS_ENDPOINT,
        params={
            "league": WORLD_CUP_LEAGUE_ID,
            "date_from": WORLD_CUP_FALLBACK_DATE_FROM,
            "date_to": WORLD_CUP_FALLBACK_DATE_TO,
            "tz": WORLD_CUP_TZ,
        },
        timeout=timeout,
        rotulo="events fallback",
        resumo=resumo_fallback,
    )
    resumo["fallback_count"] = resumo_fallback.get("count")
    resumo["fallback_baixados"] = resumo_fallback.get("baixados", len(eventos_fallback))
    settings.debug_log(f"[BSD] {len(eventos_fallback)} eventos retornados no fallback.")

    if not eventos_season and not eventos_fallback:
        settings.debug_log("Nenhum jogo retornado pela API.")
        resumo["total_baixados"] = 0
        return [], resumo

    eventos = _unir_eventos(eventos_season, eventos_fallback)
    resumo["total_baixados"] = len(eventos)
    settings.debug_log(f"[BSD] {len(eventos)} eventos consolidados apos merge de season e fallback.")
    return eventos, resumo


def buscar_todos_eventos_copa(timeout: int = DEFAULT_TIMEOUT) -> List[Dict[str, Any]]:
    """Busca todos os eventos da Copa do Mundo usando season e fallback por data."""
    eventos, _ = buscar_todos_eventos_copa_com_resumo(timeout=timeout)
    return eventos


def mapear_evento_para_jogo(evento_api: Dict[str, Any], *, classificar_fase: bool = True) -> Jogo:
    """Converte um evento da API para o modelo Jogo do sistema.

    Quando `classificar_fase` e falso, o jogo e salvo como nao mapeado para
    permitir uma primeira etapa de importacao sem descartes.
    """
    if not isinstance(evento_api, dict):
        raise BSDAPIError("Formato de evento inesperado na API BSD.")

    api_id = _to_int_or_none(evento_api.get("id"))
    if api_id is None:
        raise BSDAPIError("Evento da API sem id valido.")

    home_team = _extrair_time(evento_api, "home")
    away_team = _extrair_time(evento_api, "away")
    home_team_id = _extrair_team_id(evento_api, "home")
    away_team_id = _extrair_team_id(evento_api, "away")
    if not home_team or not away_team:
        raise BSDAPIError(f"Evento {api_id} sem times definidos.")

    status = _extrair_status(evento_api) or "notstarted"
    placar_casa = _to_int_or_none(evento_api.get("home_score"))
    placar_fora = _to_int_or_none(evento_api.get("away_score"))
    fase = inferir_fase(evento_api) if classificar_fase else FASE_NAO_MAPEADA
    grupo = inferir_grupo_por_times(home_team, away_team) if fase == "Fase de Grupos" else None
    home_team_logo_url = get_team_logo_url(home_team_id)
    away_team_logo_url = get_team_logo_url(away_team_id)

    return Jogo(
        id=None,
        api_id=api_id,
        time_a=home_team,
        time_b=away_team,
        placar_a=placar_casa,
        placar_b=placar_fora,
        finalizado=_status_finalizado(status),
        fase=fase,
        grupo=grupo,
        data_jogo=_extrair_data(evento_api),
        status=status,
        proximo_jogo_id=None,
        round_number=_extrair_round_number(evento_api),
        is_placeholder_bracket=identificar_placeholder_bracket(home_team, away_team),
        time_casa=home_team,
        time_fora=away_team,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_team_logo_url=home_team_logo_url,
        away_team_logo_url=away_team_logo_url,
        gols_casa=placar_casa,
        gols_fora=placar_fora,
        estadio=_extrair_estadio(evento_api),
        competicao=WORLD_CUP_NAME,
    )


def buscar_detalhes_jogo(
    event_id: int,
    timeout: int = DEFAULT_TIMEOUT,
) -> Jogo:
    """Busca os detalhes atualizados de um jogo especifico."""
    url = EVENT_DETAIL_ENDPOINT.format(event_id=int(event_id))
    evento = _request_json(url, params={"tz": WORLD_CUP_TZ}, timeout=timeout)
    if not isinstance(evento, dict):
        raise BSDAPIError(f"Resposta invalida ao consultar o evento {event_id}.", url=url)
    return mapear_evento_para_jogo(evento)


def buscar_jogos_copa(timeout: int = DEFAULT_TIMEOUT) -> List[Jogo]:
    """Compatibilidade com o nome antigo, retornando jogos mapeados."""
    return [mapear_evento_para_jogo(evento) for evento in buscar_todos_eventos_copa(timeout=timeout)]


def _extrair_league_id_live(evento: Dict[str, Any]) -> Optional[int]:
    candidatos = (
        evento.get("league"),
        evento.get("league_obj"),
        evento.get("league_info"),
        evento.get("competition"),
        evento.get("competition_obj"),
    )
    for candidato in candidatos:
        if isinstance(candidato, dict):
            for chave in ("id", "league_id", "leagueId", "pk", "value"):
                valor = _to_int_or_none(candidato.get(chave))
                if valor is not None:
                    return valor
        else:
            valor = _to_int_or_none(candidato)
            if valor is not None:
                return valor
    return None


def _evento_eh_copa_ao_vivo(evento: Dict[str, Any]) -> bool:
    league_id = _extrair_league_id_live(evento)
    if league_id == WORLD_CUP_LEAGUE_ID:
        return True

    league_texto = _normalize_text(
        _texto_evento(
            evento,
            "league_name",
            "league_title",
            "competition_name",
            "competition_title",
            "tournament_name",
        )
    )
    return "world cup" in league_texto or "copa do mundo" in league_texto


def _extrair_minuto_ao_vivo(evento: Dict[str, Any]) -> Optional[str]:
    candidatos = (
        evento.get("minute"),
        evento.get("live_minute"),
        evento.get("elapsed"),
        evento.get("match_time"),
        evento.get("current_minute"),
        evento.get("time"),
        evento.get("clock"),
        evento.get("minute_text"),
        evento.get("status_time"),
    )
    for candidato in candidatos:
        if isinstance(candidato, dict):
            texto = _texto_dict(candidato, "name", "title", "label", "value", "text", "minute")
            if texto:
                return texto
        else:
            texto = str(candidato).strip() if candidato not in (None, "") else ""
            if texto:
                return texto
    return None


def _extrair_placar_ao_vivo(evento: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    candidatos_home = (
        evento.get("home_score"),
        evento.get("homeScore"),
        evento.get("score_home"),
        evento.get("home_goals"),
        evento.get("home_points"),
    )
    candidatos_away = (
        evento.get("away_score"),
        evento.get("awayScore"),
        evento.get("score_away"),
        evento.get("away_goals"),
        evento.get("away_points"),
    )

    placar_home = None
    placar_away = None

    for candidato in candidatos_home:
        if isinstance(candidato, dict):
            valor = _to_int_or_none(candidato.get("value") or candidato.get("score") or candidato.get("home"))
        else:
            valor = _to_int_or_none(candidato)
        if valor is not None:
            placar_home = valor
            break

    for candidato in candidatos_away:
        if isinstance(candidato, dict):
            valor = _to_int_or_none(candidato.get("value") or candidato.get("score") or candidato.get("away"))
        else:
            valor = _to_int_or_none(candidato)
        if valor is not None:
            placar_away = valor
            break

    score = evento.get("score")
    if isinstance(score, dict):
        if placar_home is None:
            placar_home = _to_int_or_none(score.get("home") or score.get("home_score") or score.get("a"))
        if placar_away is None:
            placar_away = _to_int_or_none(score.get("away") or score.get("away_score") or score.get("b"))

    return placar_home, placar_away


def _normalizar_evento_ao_vivo(evento: Dict[str, Any]) -> Dict[str, Any]:
    home_team = _extrair_time(evento, "home")
    away_team = _extrair_time(evento, "away")
    home_team_id = _extrair_team_id(evento, "home")
    away_team_id = _extrair_team_id(evento, "away")
    placar_casa, placar_fora = _extrair_placar_ao_vivo(evento)
    league_id = _extrair_league_id_live(evento)

    return {
        "api_id": _to_int_or_none(evento.get("id")),
        "match_number": _to_int_or_none(
            evento.get("match_number")
            or evento.get("match_no")
            or evento.get("number")
            or evento.get("order")
        ),
        "league_id": league_id,
        "league_name": _texto_evento(
            evento,
            "league_name",
            "league_title",
            "competition_name",
            "competition_title",
            "tournament_name",
        ),
        "time_casa": home_team,
        "time_fora": away_team,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_team_logo_url": get_team_logo_url(home_team_id),
        "away_team_logo_url": get_team_logo_url(away_team_id),
        "status": _extrair_status(evento),
        "fase": inferir_fase(evento),
        "round_number": _extrair_round_number(evento),
        "data_hora": _extrair_data(evento),
        "minuto": _extrair_minuto_ao_vivo(evento),
        "placar_casa": placar_casa,
        "placar_fora": placar_fora,
        "estadio": _extrair_estadio(evento),
        "is_copa": _evento_eh_copa_ao_vivo(evento),
        "raw": evento,
    }


def buscar_jogos_ao_vivo(timeout: int = DEFAULT_TIMEOUT) -> List[Dict[str, Any]]:
    """Busca jogos ao vivo da Copa do Mundo no endpoint oficial de live."""
    eventos = _coletar_paginado(
        LIVE_ENDPOINT,
        params={"league": WORLD_CUP_LEAGUE_ID, "tz": WORLD_CUP_TZ},
        timeout=timeout,
        rotulo="live league=27",
    )

    if not eventos:
        settings.debug_log("[BSD] Nenhum evento ao vivo retornado por live league=27.")
        return []

    status_validos = {
        "inprogress", "in progress",
        "1st half", "1st_half",
        "halftime", "half time",
        "2nd half", "2nd_half",
        "live",
        "first half", "first_half",
        "second half", "second_half",
    }

    jogos: List[Dict[str, Any]] = []
    for evento in eventos:
        if not _evento_eh_copa_ao_vivo(evento):
            continue
        status = _normalize_text(_extrair_status(evento)).replace("_", " ")
        if status and status not in status_validos:
            continue
        jogos.append(_normalizar_evento_ao_vivo(evento))

    settings.debug_log(f"[BSD] {len(jogos)} jogos ao vivo da Copa encontrados em live league=27.")
    if not jogos:
        settings.debug_log("[BSD] Nenhum jogo ao vivo da Copa neste momento.")
    return jogos


def buscar_jogadores_copa(
    progress_callback=None,
    timeout: int = DEFAULT_TIMEOUT,
) -> List[Dict[str, Any]]:
    """Busca jogadores de todas as selecoes da Copa via API.

    Para cada time encontrado nos eventos, consulta /players/?national_team={id}.
    Chama progress_callback(atual, total) a cada time processado, se fornecido.
    """
    eventos = buscar_todos_eventos_copa(timeout=timeout)

    teams: Dict[int, str] = {}
    for evento in eventos:
        for prefix in ("home", "away"):
            obj = evento.get(f"{prefix}_team_obj") or {}
            if isinstance(obj, dict):
                team_id = _to_int_or_none(obj.get("id"))
                team_name = _texto_dict(obj, "name", "short_name")
                if team_id and team_name and team_id not in teams:
                    teams[team_id] = team_name

    settings.debug_log(f"[BSD] {len(teams)} selecoes encontradas nos eventos da Copa.")

    jogadores: List[Dict[str, Any]] = []
    total = len(teams)

    for i, (team_id, team_name) in enumerate(teams.items()):
        if progress_callback:
            progress_callback(i, total)
        try:
            players = _coletar_paginado(
                PLAYERS_ENDPOINT,
                params={"national_team": team_id},
                timeout=timeout,
                rotulo=f"players national_team={team_id}",
            )
        except BSDAPIError as exc:
            settings.debug_log(f"[BSD] Falha ao buscar jogadores de {team_name}: {exc}")
            continue

        for p in players:
            nome = (p.get("name") or p.get("short_name") or "").strip()
            if nome:
                jogadores.append({
                    "nome": nome,
                    "posicao": p.get("position") or "",
                    "time": team_name,
                    "api_id": _to_int_or_none(p.get("id")),
                })

    if progress_callback:
        progress_callback(total, total)

    settings.debug_log(f"[BSD] {len(jogadores)} jogadores importados de {total} selecoes.")
    return jogadores


def buscar_jogos_do_dia(timeout: int = DEFAULT_TIMEOUT) -> List[Dict[str, Any]]:
    """Busca todos os jogos da Copa do Mundo agendados para hoje em horario BRT.

    A API BSD filtra datas em UTC, entao jogos noturnos (ex: 22h BRT = 01h UTC do dia
    seguinte) seriam excluidos com date_to=hoje. A solucao: consultar ate amanha e
    filtrar localmente pelo horario BRT do evento.
    """
    from datetime import datetime, date as _date, timedelta

    try:
        from zoneinfo import ZoneInfo
        _tz = ZoneInfo(WORLD_CUP_TZ)
        agora_local = datetime.now(_tz)
        hoje_str = agora_local.strftime("%Y-%m-%d")
        amanha_str = (agora_local + timedelta(days=1)).strftime("%Y-%m-%d")
        hoje_date = agora_local.date()
    except Exception:
        _tz = None
        hoje_str = _date.today().isoformat()
        amanha_str = (_date.today() + timedelta(days=1)).isoformat()
        hoje_date = None

    season = obter_season_copa(timeout=timeout)
    eventos: List[Dict[str, Any]] = []

    if season is not None:
        season_id = _to_int_or_none(season.get("id"))
        if season_id is not None:
            try:
                eventos = _coletar_paginado(
                    EVENTS_ENDPOINT,
                    params={"season": season_id, "date_from": hoje_str, "date_to": amanha_str, "tz": WORLD_CUP_TZ},
                    timeout=timeout,
                    rotulo=f"events hoje season={season_id}",
                )
            except BSDAPIError as exc:
                settings.debug_log(f"[BSD] Erro ao buscar jogos do dia por season: {exc}")

    if not eventos:
        try:
            eventos = _coletar_paginado(
                EVENTS_ENDPOINT,
                params={"league": WORLD_CUP_LEAGUE_ID, "date_from": hoje_str, "date_to": amanha_str, "tz": WORLD_CUP_TZ},
                timeout=timeout,
                rotulo="events hoje fallback",
            )
        except BSDAPIError as exc:
            settings.debug_log(f"[BSD] Erro no fallback de buscar jogos do dia: {exc}")

    jogos = [_normalizar_evento_ao_vivo(ev) for ev in eventos if isinstance(ev, dict)]

    # Filtra localmente: mantém apenas jogos cujo horário BRT seja hoje.
    if hoje_date is not None and _tz is not None:
        def _data_brt(jogo: Dict[str, Any]) -> Optional[_date]:
            data_hora = jogo.get("data_hora")
            if not data_hora:
                return None
            try:
                dt = datetime.fromisoformat(str(data_hora).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(_tz).date()
            except Exception:
                return None

        antes = len(jogos)
        jogos = [j for j in jogos if _data_brt(j) in (hoje_date, None)]
        settings.debug_log(f"[BSD] Filtro local BRT: {antes} → {len(jogos)} jogos para hoje ({hoje_str}).")
    else:
        settings.debug_log(f"[BSD] {len(jogos)} jogos da Copa para hoje ({hoje_str}).")

    return jogos


def buscar_jogos_ao_vivo_teste(timeout: int = DEFAULT_TIMEOUT) -> List[Dict[str, Any]]:
    """Busca jogos ao vivo em modo de teste sem filtrar por league=27."""
    eventos = _coletar_paginado(
        LIVE_ENDPOINT,
        params={"tz": WORLD_CUP_TZ},
        timeout=timeout,
        rotulo="live teste",
    )

    if not eventos:
        settings.debug_log("[BSD] Nenhum evento ao vivo retornado no modo teste.")
        return []

    status_relevantes = {
        "inprogress",
        "1st_half",
        "halftime",
        "2nd_half",
        "live",
        "first_half",
        "second_half",
    }

    jogos: List[Dict[str, Any]] = []
    for evento in eventos:
        status = _normalize_text(_extrair_status(evento))
        time_casa = _normalize_text(_extrair_time(evento, "home"))
        time_fora = _normalize_text(_extrair_time(evento, "away"))
        if status not in status_relevantes and "atalanta" not in time_casa and "atalanta" not in time_fora:
            continue
        jogos.append(_normalizar_evento_ao_vivo(evento))

    settings.debug_log(f"[BSD] {len(jogos)} jogos ao vivo encontrados em modo teste.")
    if not jogos:
        settings.debug_log("[BSD] Nenhum jogo relevante em modo teste neste momento.")
    return jogos


__all__ = [
    "BSDAPIError",
    "DEFAULT_TIMEOUT",
    "EVENTS_ENDPOINT",
    "EVENT_DETAIL_ENDPOINT",
    "SEASONS_ENDPOINT",
    "WORLD_CUP_LEAGUE_ID",
    "WORLD_CUP_NAME",
    "WORLD_CUP_TZ",
    "buscar_detalhes_jogo",
    "buscar_jogadores_copa",
    "buscar_jogos_copa",
    "buscar_jogos_ao_vivo",
    "buscar_jogos_ao_vivo_teste",
    "buscar_jogos_do_dia",
    "buscar_todos_eventos_copa_com_resumo",
    "buscar_todos_eventos_copa",
    "identificar_placeholder_bracket",
    "inferir_fase",
    "obter_season_copa",
    "mapear_evento_para_jogo",
]
