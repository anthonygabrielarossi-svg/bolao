"""Servico de classificacao dos grupos.

A classificacao e calculada localmente a partir dos jogos finalizados,
inferindo o grupo quando o campo nao estiver preenchido.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from database import (
    COMPETICAO_PADRAO,
    ClassificacaoGrupo,
    Jogo,
    listar_jogos,
    salvar_classificacao_grupos,
    usuario_eh_admin,
    validar_grupo_copa,
)
from utils.world_cup import WORLD_CUP_GROUPS_2026, canonicalizar_time, formatar_nome_time, inferir_grupo_por_times

_STATUS_FINAIS_REAIS = {"finished", "ft", "fulltime", "full time", "complete", "completed", "final"}


def _normalizar_texto(texto: Optional[str]) -> str:
    return (texto or "").strip().upper()


def _exigir_admin(executed_by_user_id: Optional[int]) -> None:
    if executed_by_user_id is not None and not usuario_eh_admin(executed_by_user_id):
        raise PermissionError("Apenas administradores podem recalcular a classificacao.")


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


def _placar_int(valor: Optional[int]) -> Optional[int]:
    if valor is None:
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _obter_placares_reais(jogo: Jogo) -> tuple[Optional[int], Optional[int]]:
    casa = _placar_int(jogo.gols_casa if jogo.gols_casa is not None else jogo.placar_a)
    fora = _placar_int(jogo.gols_fora if jogo.gols_fora is not None else jogo.placar_b)
    return casa, fora


def _jogo_vale_para_classificacao_real(jogo: Jogo) -> bool:
    if _normalizar_texto(jogo.competicao) != _normalizar_texto(COMPETICAO_PADRAO):
        return False
    if _normalizar_texto(jogo.fase) != _normalizar_texto("Fase de Grupos"):
        return False
    if not (jogo.finalizado or _normalizar_texto(jogo.status) in _STATUS_FINAIS_REAIS):
        return False

    casa, fora = _obter_placares_reais(jogo)
    return casa is not None and fora is not None


def calcular_classificacao_real_grupos(jogos: Optional[List[Jogo]] = None) -> List[ClassificacaoGrupo]:
    """Calcula a classificacao real dos grupos usando apenas jogos finalizados."""
    if jogos is None:
        jogos = listar_jogos()

    tabelas: Dict[str, Dict[str, Dict[str, int]]] = {
        grupo: {time: _estatisticas_vazias() for time in times}
        for grupo, times in WORLD_CUP_GROUPS_2026.items()
    }

    for jogo in jogos:
        if not _jogo_vale_para_classificacao_real(jogo):
            continue

        grupo = validar_grupo_copa(jogo.grupo) or inferir_grupo_por_times(jogo.time_a, jogo.time_b)
        if not grupo:
            continue
        time_a = canonicalizar_time(jogo.time_a) or jogo.time_a.strip()
        time_b = canonicalizar_time(jogo.time_b) or jogo.time_b.strip()
        placar_a, placar_b = _obter_placares_reais(jogo)
        if placar_a is None or placar_b is None:
            continue

        grupo_tabela = tabelas.setdefault(grupo, {})
        stats_a = grupo_tabela.setdefault(time_a, _estatisticas_vazias())
        stats_b = grupo_tabela.setdefault(time_b, _estatisticas_vazias())

        stats_a["jogos"] += 1
        stats_b["jogos"] += 1
        stats_a["gols_pro"] += placar_a
        stats_a["gols_contra"] += placar_b
        stats_b["gols_pro"] += placar_b
        stats_b["gols_contra"] += placar_a

        if placar_a > placar_b:
            stats_a["pontos"] += 3
            stats_a["vitorias"] += 1
            stats_b["derrotas"] += 1
        elif placar_b > placar_a:
            stats_b["pontos"] += 3
            stats_b["vitorias"] += 1
            stats_a["derrotas"] += 1
        else:
            stats_a["pontos"] += 1
            stats_b["pontos"] += 1
            stats_a["empates"] += 1
            stats_b["empates"] += 1

    classificacoes: List[ClassificacaoGrupo] = []
    for grupo in WORLD_CUP_GROUPS_2026.keys():
        times = tabelas.get(grupo, {})
        ordenados = sorted(
            times.items(),
            key=lambda item: (
                -item[1]["pontos"],
                -(item[1]["gols_pro"] - item[1]["gols_contra"]),
                -item[1]["gols_pro"],
                formatar_nome_time(item[0]).lower(),
            ),
        )

        for posicao, (time_nome, stats) in enumerate(ordenados, start=1):
            saldo = stats["gols_pro"] - stats["gols_contra"]
            classificacoes.append(
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

    return classificacoes


def calcular_classificacao_grupos(jogos: Optional[List[Jogo]] = None) -> List[ClassificacaoGrupo]:
    """Compatibilidade com o nome antigo da classificacao real."""
    return calcular_classificacao_real_grupos(jogos=jogos)


def listar_classificacao_real_agrupada() -> Dict[str, List[ClassificacaoGrupo]]:
    """Retorna a classificacao real agrupada por grupo."""
    classificacao = calcular_classificacao_real_grupos()
    agrupada: Dict[str, List[ClassificacaoGrupo]] = defaultdict(list)
    for item in classificacao:
        agrupada[item.grupo].append(item)
    for grupo in WORLD_CUP_GROUPS_2026.keys():
        agrupada.setdefault(grupo, [])
    return agrupada


def atualizar_tabela_classificacao(executed_by_user_id: Optional[int] = None) -> List[ClassificacaoGrupo]:
    """Recalcula e persiste a classificacao dos grupos."""
    _exigir_admin(executed_by_user_id)
    classificacao = calcular_classificacao_real_grupos()
    salvar_classificacao_grupos(classificacao)
    return classificacao


def listar_classificacao_agrupada() -> Dict[str, List[ClassificacaoGrupo]]:
    """Retorna a classificacao atual agrupada por grupo."""
    return listar_classificacao_real_agrupada()


def obter_top_duas_por_grupo() -> Dict[str, List[str]]:
    """Retorna apenas os dois primeiros times de cada grupo."""
    top_duas: Dict[str, List[str]] = {}
    for grupo, times in listar_classificacao_real_agrupada().items():
        if not any(item.jogos > 0 for item in times):
            continue
        ordenados = sorted(
            times,
            key=lambda item: (
                -item.pontos,
                -item.saldo_gols,
                -item.gols_pro,
                formatar_nome_time(item.time_nome).lower(),
            ),
        )
        top_duas[grupo] = [item.time_nome for item in ordenados[:2]]
    return top_duas
