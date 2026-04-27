"""Regras de simulacao da Copa do Mundo.

Tudo aqui roda apenas em memoria. Nenhuma funcao deste modulo salva no banco,
altera palpites reais ou recalcula ranking oficial.
"""

from __future__ import annotations

import copy
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import COMPETICAO_PADRAO, ClassificacaoGrupo, Jogo, validar_grupo_copa
from utils.formatters import normalizar_texto
from utils.world_cup import WORLD_CUP_GROUPS_2026, canonicalizar_time, inferir_grupo_por_times


_PLACEHOLDER_RE = re.compile(r"^(?:[WL]\d+|\d+[A-Z]|3[A-L](?:/3[A-L])*)$", re.IGNORECASE)

def _normalizar(texto: Optional[str]) -> str:
    return normalizar_texto(texto)




_FASE_ORDEM_MATCH_NUMBER = {
    _normalizar("Fase de Grupos"): 0,
    _normalizar("16-avos de Final"): 1,
    _normalizar("Oitavas de Final"): 2,
    _normalizar("Quartas de Final"): 3,
    _normalizar("Semifinal"): 4,
    _normalizar("Disputa de 3º Lugar"): 5,
    _normalizar("Final"): 6,
}


def _jogo_chave(jogo: Jogo) -> int:
    if jogo.id is not None:
        return int(jogo.id)
    if jogo.api_id is not None:
        return int(jogo.api_id)
    return id(jogo)


def _adicionar_indices_jogo(mapa: Dict[int, Jogo], jogo: Jogo) -> None:
    if jogo.id is not None:
        mapa[int(jogo.id)] = jogo
    if jogo.api_id is not None:
        mapa[int(jogo.api_id)] = jogo


def _parse_data_jogo(data_hora: Optional[str]) -> tuple[int, float, int]:
    if not data_hora:
        return (1, float("inf"), 0)

    try:
        data = datetime.fromisoformat(str(data_hora).replace("Z", "+00:00"))
    except ValueError:
        return (1, float("inf"), 0)

    if data.tzinfo is None:
        data = data.replace(tzinfo=datetime.now().astimezone().tzinfo)

    return (0, data.timestamp(), 0)


def _ordem_match_number(jogo: Jogo) -> tuple[int, float, int, int, int]:
    ordenacao_data = _parse_data_jogo(jogo.data_jogo)
    return (
        ordenacao_data[0],
        ordenacao_data[1],
        _FASE_ORDEM_MATCH_NUMBER.get(_normalizar(jogo.fase), 99),
        int(jogo.round_number or 0),
        _jogo_chave(jogo),
    )


def atribuir_match_numbers_copa(jogos: List[Jogo]) -> List[Jogo]:
    """Atribui o numero oficial do jogo da Copa em memoria."""
    jogos_ordenados = sorted(copy.deepcopy(jogos), key=_ordem_match_number)
    for indice, jogo in enumerate(jogos_ordenados, start=1):
        jogo.match_number = indice
    return jogos_ordenados


def _mapear_jogos_por_match_number(jogos: List[Jogo]) -> Dict[int, Jogo]:
    mapa: Dict[int, Jogo] = {}
    for jogo in jogos:
        match_number = getattr(jogo, "match_number", None)
        if match_number is None:
            continue
        mapa[int(match_number)] = jogo
    return mapa


def _debug_resolucao_simulacao(
    debug_logs: List[str],
    mensagem: str,
) -> None:
    debug_logs.append(mensagem)
    print(f"[SIM] {mensagem}")


def _estatisticas_vazias() -> Dict[str, int]:
    return {
        "pontos": 0,
        "jogos": 0,
        "vitorias": 0,
        "empates": 0,
        "derrotas": 0,
        "gols_pro": 0,
        "gols_contra": 0,
    }


def inicializar_simulacao_state(jogos_reais: List[Jogo]) -> Dict[str, Any]:
    """Monta o estado inicial da simulacao a partir dos jogos reais."""
    jogos_base = atribuir_match_numbers_copa(jogos_reais)
    resultados: Dict[int, Dict[str, Any]] = {}
    for jogo in jogos_base:
        chave = _jogo_chave(jogo)
        resultados[chave] = {
            "gols_casa": jogo.gols_casa if jogo.gols_casa is not None else jogo.placar_a,
            "gols_fora": jogo.gols_fora if jogo.gols_fora is not None else jogo.placar_b,
            "vencedor_posicao": None,
        }

    return {
        "simulacao_jogos": jogos_base,
        "simulacao_resultados": resultados,
        "simulacao_classificacao": {},
        "simulacao_chaveamento": {},
        "simulacao_jogos_resolvidos": copy.deepcopy(jogos_base),
        "simulacao_jogos_por_match_number": _mapear_jogos_por_match_number(jogos_base),
        "simulacao_debug_chaveamento": [],
    }


def resetar_simulacao_state(jogos_reais: List[Jogo]) -> Dict[str, Any]:
    """Reconstroi o estado da simulacao com base nos jogos reais atuais."""
    return inicializar_simulacao_state(jogos_reais)


def _resultado_do_jogo(jogo: Jogo, resultados: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    chave = _jogo_chave(jogo)
    return resultados.get(chave, {})


def aplicar_resultados_simulados(
    jogos_base: List[Jogo],
    resultados: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    """Aplica os placares simulados em memoria e recalcula tudo."""
    jogos_simulados = atribuir_match_numbers_copa(jogos_base)
    indice_por_chave: Dict[int, Jogo] = {}
    for jogo in jogos_simulados:
        _adicionar_indices_jogo(indice_por_chave, jogo)
    jogos_por_match_number = _mapear_jogos_por_match_number(jogos_simulados)

    for jogo in jogos_simulados:
        resultado = resultados.get(_jogo_chave(jogo), {})
        gols_casa = resultado.get("gols_casa")
        gols_fora = resultado.get("gols_fora")
        if gols_casa is not None:
            jogo.gols_casa = int(gols_casa)
            jogo.placar_a = int(gols_casa)
        if gols_fora is not None:
            jogo.gols_fora = int(gols_fora)
            jogo.placar_b = int(gols_fora)
        if gols_casa is not None and gols_fora is not None:
            jogo.finalizado = True

    classificacao = calcular_classificacao_grupos_simulada(jogos_simulados)
    classificados = obter_classificados_simulados(classificacao)
    terceiros = obter_melhores_terceiros_simulados(classificacao)
    jogos_resolvidos, chaveamento, debug_logs = atualizar_chaveamento_simulado(
        jogos_simulados,
        classificacao,
        terceiros,
        resultados,
        jogos_por_match_number,
    )

    return {
        "simulacao_jogos": copy.deepcopy(jogos_simulados),
        "simulacao_resultados": resultados,
        "simulacao_classificacao": classificacao,
        "simulacao_classificados": classificados,
        "simulacao_melhores_terceiros": terceiros,
        "simulacao_chaveamento": chaveamento,
        "simulacao_jogos_resolvidos": jogos_resolvidos,
        "simulacao_jogos_por_match_number": jogos_por_match_number,
        "simulacao_debug_chaveamento": debug_logs,
    }


def calcular_classificacao_grupos_simulada(jogos: List[Jogo]) -> Dict[str, List[ClassificacaoGrupo]]:
    """Calcula a tabela dos grupos usando os placares simulados."""
    tabelas: Dict[str, Dict[str, Dict[str, int]]] = {
        grupo: {time: _estatisticas_vazias() for time in times}
        for grupo, times in WORLD_CUP_GROUPS_2026.items()
    }

    for jogo in jogos:
        if _normalizar(jogo.competicao) and _normalizar(jogo.competicao) != _normalizar(COMPETICAO_PADRAO):
            continue
        if _normalizar(jogo.fase) != _normalizar("Fase de Grupos"):
            continue

        if jogo.gols_casa is None or jogo.gols_fora is None:
            continue

        grupo = validar_grupo_copa(jogo.grupo) or inferir_grupo_por_times(jogo.time_a, jogo.time_b)
        if not grupo:
            continue

        time_a = canonicalizar_time(jogo.time_a) or str(jogo.time_a or "").strip()
        time_b = canonicalizar_time(jogo.time_b) or str(jogo.time_b or "").strip()
        grupo_tabela = tabelas.setdefault(grupo, {})
        stats_a = grupo_tabela.setdefault(time_a, _estatisticas_vazias())
        stats_b = grupo_tabela.setdefault(time_b, _estatisticas_vazias())

        stats_a["jogos"] += 1
        stats_b["jogos"] += 1
        stats_a["gols_pro"] += int(jogo.gols_casa)
        stats_a["gols_contra"] += int(jogo.gols_fora)
        stats_b["gols_pro"] += int(jogo.gols_fora)
        stats_b["gols_contra"] += int(jogo.gols_casa)

        if int(jogo.gols_casa) > int(jogo.gols_fora):
            stats_a["pontos"] += 3
            stats_a["vitorias"] += 1
            stats_b["derrotas"] += 1
        elif int(jogo.gols_fora) > int(jogo.gols_casa):
            stats_b["pontos"] += 3
            stats_b["vitorias"] += 1
            stats_a["derrotas"] += 1
        else:
            stats_a["pontos"] += 1
            stats_b["pontos"] += 1
            stats_a["empates"] += 1
            stats_b["empates"] += 1

    classificacao: Dict[str, List[ClassificacaoGrupo]] = {}
    for grupo in WORLD_CUP_GROUPS_2026.keys():
        times = tabelas.get(grupo, {})
        ordenados = sorted(
            times.items(),
            key=lambda item: (
                -item[1]["pontos"],
                -(item[1]["gols_pro"] - item[1]["gols_contra"]),
                -item[1]["gols_pro"],
                item[0].lower(),
            ),
        )

        grupo_classificacao: List[ClassificacaoGrupo] = []
        for posicao, (time_nome, stats) in enumerate(ordenados, start=1):
            saldo = stats["gols_pro"] - stats["gols_contra"]
            grupo_classificacao.append(
                ClassificacaoGrupo(
                    id=None,
                    grupo=grupo,
                    time_nome=time_nome,
                    posicao=posicao,
                    pontos=stats["pontos"],
                    jogos=stats["jogos"],
                    vitorias=stats["vitorias"],
                    empates=stats["empates"],
                    derrotas=stats["derrotas"],
                    gols_pro=stats["gols_pro"],
                    gols_contra=stats["gols_contra"],
                    saldo_gols=saldo,
                )
            )
        classificacao[grupo] = grupo_classificacao

    return classificacao


def obter_classificados_simulados(classificacao: Dict[str, List[ClassificacaoGrupo]]) -> Dict[str, List[str]]:
    """Retorna os dois primeiros colocados de cada grupo."""
    classificados: Dict[str, List[str]] = {}
    for grupo, itens in classificacao.items():
        ordenados = sorted(
            itens,
            key=lambda item: (
                -item.pontos,
                -item.saldo_gols,
                -item.gols_pro,
                item.time_nome.lower(),
            ),
        )
        classificados[grupo] = [item.time_nome for item in ordenados[:2]]
    return classificados


def obter_melhores_terceiros_simulados(
    classificacao: Dict[str, List[ClassificacaoGrupo]],
) -> List[ClassificacaoGrupo]:
    """Retorna os oito melhores terceiros colocados."""
    terceiros: List[ClassificacaoGrupo] = []
    for grupo, itens in classificacao.items():
        ordenados = sorted(
            itens,
            key=lambda item: (
                -item.pontos,
                -item.saldo_gols,
                -item.gols_pro,
                item.time_nome.lower(),
            ),
        )
        if len(ordenados) >= 3:
            terceiro = ordenados[2]
            terceiros.append(
                ClassificacaoGrupo(
                    id=terceiro.id,
                    grupo=grupo,
                    time_nome=terceiro.time_nome,
                    posicao=terceiro.posicao,
                    pontos=terceiro.pontos,
                    jogos=terceiro.jogos,
                    vitorias=terceiro.vitorias,
                    empates=terceiro.empates,
                    derrotas=terceiro.derrotas,
                    gols_pro=terceiro.gols_pro,
                    gols_contra=terceiro.gols_contra,
                    saldo_gols=terceiro.saldo_gols,
                )
            )

    terceiros.sort(
        key=lambda item: (
            -item.pontos,
            -item.saldo_gols,
            -item.gols_pro,
            item.time_nome.lower(),
        )
    )
    return terceiros[:8]


def obter_vencedor_simulado(jogo: Jogo, resultados: Dict[int, Dict[str, Any]]) -> Optional[str]:
    """Retorna o vencedor de um jogo simulado, se houver."""
    resultado = _resultado_do_jogo(jogo, resultados)
    gols_casa = resultado.get("gols_casa", jogo.gols_casa)
    gols_fora = resultado.get("gols_fora", jogo.gols_fora)
    vencedor_posicao = resultado.get("vencedor_posicao")

    if gols_casa is None or gols_fora is None:
        return None

    if int(gols_casa) > int(gols_fora):
        return jogo.time_casa or jogo.time_a
    if int(gols_fora) > int(gols_casa):
        return jogo.time_fora or jogo.time_b

    if vencedor_posicao == "home":
        return jogo.time_casa or jogo.time_a
    if vencedor_posicao == "away":
        return jogo.time_fora or jogo.time_b
    return None


def obter_perdedor_simulado(jogo: Jogo, resultados: Dict[int, Dict[str, Any]]) -> Optional[str]:
    """Retorna o perdedor de um jogo simulado, se houver."""
    vencedor = obter_vencedor_simulado(jogo, resultados)
    if vencedor is None:
        return None

    home = jogo.time_casa or jogo.time_a
    away = jogo.time_fora or jogo.time_b
    if _normalizar(vencedor) == _normalizar(home):
        return away
    if _normalizar(vencedor) == _normalizar(away):
        return home
    return None


def resolver_placeholder_simulacao(
    token: Optional[str],
    classificacao: Dict[str, List[ClassificacaoGrupo]],
    melhores_terceiros: List[ClassificacaoGrupo],
    jogos_por_match_number: Dict[int, Jogo],
    resultados: Dict[int, Dict[str, Any]],
) -> Tuple[str, bool, Optional[str]]:
    """Resolves bracket placeholders as well as possible."""
    texto = str(token or "").strip()
    if not texto:
        return "", True, None

    token_normalizado = texto.replace(" ", "").upper()
    if not _PLACEHOLDER_RE.fullmatch(token_normalizado):
        return texto, True, None

    if re.fullmatch(r"[12][A-L]", token_normalizado):
        posicao = int(token_normalizado[0]) - 1
        grupo = f"Grupo {token_normalizado[1]}"
        itens = classificacao.get(grupo, [])
        if len(itens) > posicao:
            return itens[posicao].time_nome, True, None
        return texto, False, "Dependente da classificacao simulada"

    if re.fullmatch(r"3[A-L]", token_normalizado):
        grupo = f"Grupo {token_normalizado[1]}"
        itens = classificacao.get(grupo, [])
        if len(itens) >= 3:
            return itens[2].time_nome, True, None
        return texto, False, "Dependente da classificacao simulada"

    if re.fullmatch(r"3[A-L](?:/3[A-L])+", token_normalizado):
        candidatos = [parte[1] for parte in token_normalizado.split("/") if len(parte) >= 2]
        ranking_terceiros = {item.grupo: indice for indice, item in enumerate(melhores_terceiros)}
        melhor_candidato: Optional[str] = None
        melhor_posicao = 10_000
        for candidato in candidatos:
            grupo = f"Grupo {candidato}"
            itens = classificacao.get(grupo, [])
            if len(itens) < 3:
                continue
            if grupo not in ranking_terceiros:
                continue
            posicao = ranking_terceiros[grupo]
            if posicao < melhor_posicao:
                melhor_posicao = posicao
                melhor_candidato = itens[2].time_nome
        if melhor_candidato:
            observacao = None
            if len(candidatos) > 1:
                observacao = "Dependente de combinacao dos melhores terceiros"
            return melhor_candidato, True, observacao
        return texto, False, "Dependente de combinacao dos melhores terceiros"

    if token_normalizado.startswith("W") or token_normalizado.startswith("L"):
        alvo = token_normalizado[1:]
        if not alvo.isdigit():
            return texto, False, "Dependente do jogo de origem"

        jogo_origem = jogos_por_match_number.get(int(alvo))
        if not jogo_origem:
            return texto, False, f"Dependente do jogo {alvo}"

        if token_normalizado.startswith("W"):
            vencedor = obter_vencedor_simulado(jogo_origem, resultados)
            if vencedor:
                return vencedor, True, None
            return texto, False, f"Dependente do vencedor do jogo {alvo}"

        perdedor = obter_perdedor_simulado(jogo_origem, resultados)
        if perdedor:
            return perdedor, True, None
        return texto, False, f"Dependente do perdedor do jogo {alvo}"

    return texto, True, None


def atualizar_chaveamento_simulado(
    jogos_simulados: List[Jogo],
    classificacao: Dict[str, List[ClassificacaoGrupo]],
    melhores_terceiros: List[ClassificacaoGrupo],
    resultados: Dict[int, Dict[str, Any]],
    jogos_por_match_number: Optional[Dict[int, Jogo]] = None,
) -> Tuple[List[Jogo], Dict[int, Dict[str, Any]], List[str]]:
    """Resolve placeholders dos jogos simulados sem alterar o banco."""
    jogos_resolvidos = atribuir_match_numbers_copa(jogos_simulados)
    jogos_por_match = jogos_por_match_number or {}
    if not jogos_por_match:
        jogos_por_match = _mapear_jogos_por_match_number(jogos_resolvidos)

    jogos_ordenados = sorted(
        jogos_resolvidos,
        key=lambda jogo: (
            int(getattr(jogo, "match_number", 0) or 0) or 10_000,
            _parse_data_jogo(jogo.data_jogo),
            _jogo_chave(jogo),
        ),
    )

    chaveamento: Dict[int, Dict[str, Any]] = {}
    debug_logs: List[str] = []
    for jogo in jogos_ordenados:
        match_number = getattr(jogo, "match_number", None)
        fase_nome = jogo.fase or "Fase desconhecida"
        home_original = jogo.time_casa or jogo.time_a
        away_original = jogo.time_fora or jogo.time_b
        home_token = str(home_original or "").strip().upper().replace(" ", "")
        away_token = str(away_original or "").strip().upper().replace(" ", "")
        home_resolvido, home_ok, home_obs = resolver_placeholder_simulacao(
            home_original,
            classificacao,
            melhores_terceiros,
            jogos_por_match,
            resultados,
        )
        away_resolvido, away_ok, away_obs = resolver_placeholder_simulacao(
            away_original,
            classificacao,
            melhores_terceiros,
            jogos_por_match,
            resultados,
        )

        if home_resolvido:
            jogo.time_a = home_resolvido
            jogo.time_casa = home_resolvido
        if away_resolvido:
            jogo.time_b = away_resolvido
            jogo.time_fora = away_resolvido

        vencedor = obter_vencedor_simulado(jogo, resultados)
        if match_number is not None:
            placar_casa = resultados.get(_jogo_chave(jogo), {}).get("gols_casa", jogo.gols_casa)
            placar_fora = resultados.get(_jogo_chave(jogo), {}).get("gols_fora", jogo.gols_fora)
            if placar_casa is not None and placar_fora is not None:
                mensagem_jogo = (
                    f"Jogo {match_number} ({fase_nome}): "
                    f"{home_resolvido or home_original} {int(placar_casa)} x {int(placar_fora)} {away_resolvido or away_original}"
                )
                if vencedor:
                    mensagem_jogo += f" -> vencedor {vencedor}"
                _debug_resolucao_simulacao(debug_logs, mensagem_jogo)

        if home_token.startswith("W") or home_token.startswith("L"):
            if home_resolvido and home_resolvido != home_original:
                _debug_resolucao_simulacao(debug_logs, f"{home_token} resolvido como {home_resolvido}")
            elif not home_ok:
                _debug_resolucao_simulacao(debug_logs, f"{home_token} pendente: {home_obs or 'Dependencia nao resolvida'}")
        if away_token.startswith("W") or away_token.startswith("L"):
            if away_resolvido and away_resolvido != away_original:
                _debug_resolucao_simulacao(debug_logs, f"{away_token} resolvido como {away_resolvido}")
            elif not away_ok:
                _debug_resolucao_simulacao(debug_logs, f"{away_token} pendente: {away_obs or 'Dependencia nao resolvida'}")

        chave = _jogo_chave(jogo)
        chaveamento[chave] = {
            "time_casa": home_resolvido,
            "time_fora": away_resolvido,
            "resolvido": bool(home_ok and away_ok),
            "observacao": home_obs or away_obs,
            "placeholder": bool(
                _PLACEHOLDER_RE.fullmatch(str(jogo.time_a or "").replace(" ", "").upper())
                or _PLACEHOLDER_RE.fullmatch(str(jogo.time_b or "").replace(" ", "").upper())
            ),
            "match_number": match_number,
            "fase": fase_nome,
        }

    return jogos_resolvidos, chaveamento, debug_logs


def resumir_simulacao(
    jogos_reais: List[Jogo],
    resultados: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    """Monta o pacote completo do estado simulado."""
    jogos_base = atribuir_match_numbers_copa(jogos_reais)
    for jogo in jogos_base:
        resultado = resultados.get(_jogo_chave(jogo), {})
        gols_casa = resultado.get("gols_casa")
        gols_fora = resultado.get("gols_fora")
        if gols_casa is not None:
            jogo.gols_casa = int(gols_casa)
            jogo.placar_a = int(gols_casa)
        if gols_fora is not None:
            jogo.gols_fora = int(gols_fora)
            jogo.placar_b = int(gols_fora)

    classificacao = calcular_classificacao_grupos_simulada(jogos_base)
    classificados = obter_classificados_simulados(classificacao)
    melhores_terceiros = obter_melhores_terceiros_simulados(classificacao)
    jogos_resolvidos, chaveamento, debug_logs = atualizar_chaveamento_simulado(
        jogos_base,
        classificacao,
        melhores_terceiros,
        resultados,
    )

    return {
        "simulacao_jogos": copy.deepcopy(jogos_base),
        "simulacao_resultados": resultados,
        "simulacao_classificacao": classificacao,
        "simulacao_classificados": classificados,
        "simulacao_melhores_terceiros": melhores_terceiros,
        "simulacao_chaveamento": chaveamento,
        "simulacao_jogos_resolvidos": jogos_resolvidos,
        "simulacao_jogos_por_match_number": _mapear_jogos_por_match_number(jogos_base),
        "simulacao_debug_chaveamento": debug_logs,
    }


__all__ = [
    "atribuir_match_numbers_copa",
    "aplicar_resultados_simulados",
    "atualizar_chaveamento_simulado",
    "calcular_classificacao_grupos_simulada",
    "inicializar_simulacao_state",
    "obter_classificados_simulados",
    "obter_melhores_terceiros_simulados",
    "obter_perdedor_simulado",
    "obter_vencedor_simulado",
    "resetar_simulacao_state",
    "resumir_simulacao",
    "resolver_placeholder_simulacao",
]
