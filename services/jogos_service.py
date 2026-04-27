"""Servico de jogos da Copa do Mundo.

Este modulo concentra importacao, atualizacao de resultados e geracao de
mata-mata, mantendo a regra de negocio da Copa separada da interface.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Dict, List, Optional

from database import (
    COMPETICAO_PADRAO,
    FASE_NAO_MAPEADA,
    Jogo,
    buscar_jogo_por_api_id,
    listar_jogos,
    salvar_ou_atualizar_jogo,
    salvar_jogos_em_lote,
    usuario_eh_admin,
    validar_fase_copa,
    validar_grupo_copa,
)

from .api_service import (
    BSDAPIError,
    buscar_detalhes_jogo,
    buscar_todos_eventos_copa,
    buscar_todos_eventos_copa_com_resumo,
    identificar_placeholder_bracket,
    inferir_fase,
    mapear_evento_para_jogo,
)
from .classificacao_service import atualizar_tabela_classificacao, obter_top_duas_por_grupo
from .ranking_service import recalcular_ranking_automaticamente
from utils.datetime_utils import jogo_ja_comecou
from utils.formatters import formatar_nome_time
from utils.world_cup import WORLD_CUP_GROUPS_2026, inferir_grupo_por_times


def _normalizar_texto(texto: Optional[str]) -> str:
    return (texto or "").strip().lower()


def _exigir_admin(executed_by_user_id: Optional[int]) -> None:
    if executed_by_user_id is not None and not usuario_eh_admin(executed_by_user_id):
        raise PermissionError("Apenas administradores podem executar esta acao.")


def _fase_mata_mata_inicial(total_grupos: int) -> str:
    """A Copa 2026 usa 16-avos; edicoes com menos grupos seguem em oitavas."""
    return "16-avos de Final" if total_grupos > 8 else "Oitavas de Final"


def _jogo_deve_ser_atualizado(jogo: Jogo) -> bool:
    """Indica se um jogo ja deve ter resultado consultado."""
    status = _normalizar_texto(jogo.status)
    if jogo.finalizado or status in {"finished", "ft", "fulltime", "full time", "complete", "completed", "final"}:
        return True

    if status in {"inprogress", "1st_half", "halftime", "2nd_half"}:
        return True

    if jogo.data_jogo:
        return jogo_ja_comecou(jogo.data_jogo)

    return False


def _texto_final(novo: Optional[str], existente: Optional[str] = "") -> str:
    if novo is None:
        return str(existente or "")
    if isinstance(novo, str):
        texto = novo.strip()
        return texto or str(existente or "")
    return str(novo)


def _numero_final(novo: Optional[int], existente: Optional[int] = None) -> Optional[int]:
    return novo if novo is not None else existente


def _jogo_sincronizado_igual(existente: Jogo, novo: Jogo) -> bool:
    grupo_final = validar_grupo_copa(novo.grupo)
    if grupo_final is None:
        grupo_final = validar_grupo_copa(existente.grupo)

    valores_finais = {
        "time_a": _texto_final(novo.time_a, existente.time_a),
        "time_b": _texto_final(novo.time_b, existente.time_b),
        "placar_a": _numero_final(novo.placar_a, existente.placar_a),
        "placar_b": _numero_final(novo.placar_b, existente.placar_b),
        "finalizado": bool(novo.finalizado),
        "fase": validar_fase_copa(novo.fase),
        "grupo": grupo_final,
        "data_jogo": _texto_final(novo.data_jogo, existente.data_jogo),
        "status": _texto_final(novo.status, existente.status),
        "proximo_jogo_id": _numero_final(novo.proximo_jogo_id, existente.proximo_jogo_id),
        "round_number": _numero_final(novo.round_number, existente.round_number),
        "competicao": COMPETICAO_PADRAO,
        "time_casa": _texto_final(novo.time_casa or novo.time_a, existente.time_casa or existente.time_a),
        "time_fora": _texto_final(novo.time_fora or novo.time_b, existente.time_fora or existente.time_b),
        "home_team_id": _numero_final(getattr(novo, "home_team_id", None), getattr(existente, "home_team_id", None)),
        "away_team_id": _numero_final(getattr(novo, "away_team_id", None), getattr(existente, "away_team_id", None)),
        "home_team_logo_url": _texto_final(
            getattr(novo, "home_team_logo_url", None),
            getattr(existente, "home_team_logo_url", None),
        ),
        "away_team_logo_url": _texto_final(
            getattr(novo, "away_team_logo_url", None),
            getattr(existente, "away_team_logo_url", None),
        ),
        "gols_casa": _numero_final(novo.gols_casa, existente.gols_casa),
        "gols_fora": _numero_final(novo.gols_fora, existente.gols_fora),
        "estadio": _texto_final(getattr(novo, "estadio", None), getattr(existente, "estadio", "")),
    }

    return (
        _normalizar_texto(existente.time_a) == _normalizar_texto(valores_finais["time_a"])
        and _normalizar_texto(existente.time_b) == _normalizar_texto(valores_finais["time_b"])
        and existente.placar_a == valores_finais["placar_a"]
        and existente.placar_b == valores_finais["placar_b"]
        and bool(existente.finalizado) == bool(valores_finais["finalizado"])
        and _normalizar_texto(existente.fase) == _normalizar_texto(valores_finais["fase"])
        and _normalizar_texto(existente.grupo or "") == _normalizar_texto(valores_finais["grupo"] or "")
        and _normalizar_texto(existente.data_jogo or "") == _normalizar_texto(valores_finais["data_jogo"])
        and _normalizar_texto(existente.status) == _normalizar_texto(valores_finais["status"])
        and existente.proximo_jogo_id == valores_finais["proximo_jogo_id"]
        and existente.round_number == valores_finais["round_number"]
        and _normalizar_texto(existente.competicao) == _normalizar_texto(valores_finais["competicao"])
        and _normalizar_texto(existente.time_casa or existente.time_a) == _normalizar_texto(valores_finais["time_casa"])
        and _normalizar_texto(existente.time_fora or existente.time_b) == _normalizar_texto(valores_finais["time_fora"])
        and existente.home_team_id == valores_finais["home_team_id"]
        and existente.away_team_id == valores_finais["away_team_id"]
        and _normalizar_texto(getattr(existente, "home_team_logo_url", "")) == _normalizar_texto(
            valores_finais["home_team_logo_url"]
        )
        and _normalizar_texto(getattr(existente, "away_team_logo_url", "")) == _normalizar_texto(
            valores_finais["away_team_logo_url"]
        )
        and existente.gols_casa == valores_finais["gols_casa"]
        and existente.gols_fora == valores_finais["gols_fora"]
        and _normalizar_texto(getattr(existente, "estadio", "")) == _normalizar_texto(valores_finais["estadio"])
    )


def importar_jogos_copa(
    executed_by_user_id: Optional[int] = None,
) -> int:
    """Importa os jogos da Copa do Mundo e faz upsert no banco local."""
    _exigir_admin(executed_by_user_id)

    eventos_api = buscar_todos_eventos_copa()
    print(f"[BSD] {len(eventos_api)} eventos retornados pela API")

    if not eventos_api:
        print("Nenhum jogo foi retornado pela API.")
        return 0

    jogos_brutos: List[Jogo] = []
    for evento in eventos_api:
        jogo = mapear_evento_para_jogo(evento, classificar_fase=False)
        jogo.competicao = COMPETICAO_PADRAO
        jogos_brutos.append(jogo)

    print(f"[BSD] {len(jogos_brutos)} eventos processados")
    ids_brutos = salvar_jogos_em_lote(jogos_brutos)
    print(f"[BSD] {len(ids_brutos)} jogos salvos na etapa bruta")

    jogos_classificados: List[Jogo] = []
    contagem_fases: Counter[str] = Counter()
    for evento in eventos_api:
        fase_inferida = inferir_fase(evento)
        if fase_inferida == FASE_NAO_MAPEADA:
            contagem_fases[FASE_NAO_MAPEADA] += 1
        else:
            contagem_fases[fase_inferida] += 1

        jogo_classificado = mapear_evento_para_jogo(evento, classificar_fase=True)
        jogo_classificado.competicao = COMPETICAO_PADRAO
        jogo_classificado.grupo = None
        jogos_classificados.append(jogo_classificado)

    ids_classificados = salvar_jogos_em_lote(jogos_classificados)
    print(f"[BSD] {len(ids_classificados)} jogos classificados na etapa 2")

    ordem_fases = [
        "Fase de Grupos",
        "16-avos de Final",
        "Oitavas de Final",
        "Quartas de Final",
        "Semifinal",
        "Disputa de 3º Lugar",
        "Final",
        FASE_NAO_MAPEADA,
    ]
    for fase in ordem_fases:
        if fase in contagem_fases:
            print(f"[BSD] {contagem_fases[fase]} classificados como {fase}")

    print(f"[BSD] {contagem_fases.get(FASE_NAO_MAPEADA, 0)} jogos sem fase mapeada")
    print("[BSD] 0 jogos descartados por fase")
    print(f"{len(ids_classificados)} jogos importados com sucesso")
    return len(ids_classificados)


def importar_jogos_da_api(
    executed_by_user_id: Optional[int] = None,
) -> int:
    """Compatibilidade com o nome antigo da importacao."""
    return importar_jogos_copa(executed_by_user_id=executed_by_user_id)


def atualizar_jogos_copa(
    executed_by_user_id: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """Sincroniza os jogos da Copa do Mundo com os dados mais recentes da API."""
    _exigir_admin(executed_by_user_id)

    eventos_api, resumo_api = buscar_todos_eventos_copa_com_resumo()
    total_eventos = len(eventos_api)
    print(f"[BSD] count informado pela API (season): {resumo_api.get('season_count')}")
    print(f"[BSD] count informado pela API (fallback): {resumo_api.get('fallback_count')}")
    print(f"[BSD] {total_eventos} eventos baixados para atualizacao")

    if total_eventos == 0:
        print("Nenhum jogo foi retornado pela API.")
        return {
            "total_eventos": 0,
            "baixados": 0,
            "inseridos": 0,
            "atualizados": 0,
            "sem_alteracao": 0,
            "finalizados": 0,
            "nao_mapeados": 0,
            "placeholders": 0,
            "reais": 0,
            "ranking_recalculado": 0,
            "ranking_recalculado_executado": False,
        }

    inseridos = 0
    atualizados = 0
    sem_alteracao = 0
    finalizados = 0
    nao_mapeados = 0
    placeholders = 0
    reais = 0
    jogos_processados = 0

    for indice, evento in enumerate(eventos_api, start=1):
        jogo_api = mapear_evento_para_jogo(evento)
        jogo_api.competicao = COMPETICAO_PADRAO

        existente = buscar_jogo_por_api_id(int(jogo_api.api_id)) if jogo_api.api_id is not None else None
        if existente is None:
            inseridos += 1
        elif _jogo_sincronizado_igual(existente, jogo_api):
            sem_alteracao += 1
        else:
            atualizados += 1

        if jogo_api.is_placeholder_bracket:
            placeholders += 1
        else:
            reais += 1

        if jogo_api.fase == FASE_NAO_MAPEADA:
            nao_mapeados += 1

        if jogo_api.finalizado:
            finalizados += 1

        salvar_ou_atualizar_jogo(jogo_api)
        jogos_processados += 1

        if progress_callback is not None:
            progress_callback(indice, total_eventos)

    print(f"[BSD] {jogos_processados} eventos processados")
    print(f"[BSD] {inseridos} jogos inseridos")
    print(f"[BSD] {atualizados} jogos atualizados")
    print(f"[BSD] {sem_alteracao} jogos sem alteracao")
    print(f"[BSD] {finalizados} jogos finalizados")
    print(f"[BSD] {nao_mapeados} jogos com fase nao mapeada")
    print(f"[BSD] {placeholders} confrontos placeholder de bracket")
    print(f"[BSD] {reais} partidas com selecoes reais")

    if placeholders == total_eventos and total_eventos > 0:
        print("A API retornou apenas confrontos da chave eliminatoria; fase de grupos nao presente neste retorno.")

    ranking_recalculado = 0
    ranking_recalculado_executado = False
    if finalizados > 0:
        try:
            ranking = recalcular_ranking_automaticamente(executed_by_user_id=executed_by_user_id)
        except Exception as exc:
            print(f"[BSD] Aviso: nao foi possivel recalcular o ranking automaticamente: {exc}")
        else:
            ranking_recalculado = len(ranking)
            ranking_recalculado_executado = True
            print(f"[BSD] Ranking recalculado para {ranking_recalculado} usuarios.")
    else:
        print("[BSD] Nenhum jogo finalizado encontrado; ranking nao foi recalculado.")

    return {
        "total_eventos": total_eventos,
        "baixados": resumo_api.get("total_baixados", total_eventos),
        "inseridos": inseridos,
        "atualizados": atualizados,
        "sem_alteracao": sem_alteracao,
        "finalizados": finalizados,
        "nao_mapeados": nao_mapeados,
        "placeholders": placeholders,
        "reais": reais,
        "ranking_recalculado": ranking_recalculado,
        "ranking_recalculado_executado": ranking_recalculado_executado,
    }


def corrigir_fases_copa(executed_by_user_id: Optional[int] = None) -> Dict[str, Any]:
    """Recalcula a fase dos jogos da Copa do Mundo a partir do round_number."""
    _exigir_admin(executed_by_user_id)

    jogos_copa = [
        jogo
        for jogo in listar_jogos()
        if _normalizar_texto(jogo.competicao) == _normalizar_texto(COMPETICAO_PADRAO)
    ]
    total = len(jogos_copa)
    contagem_fases: Counter[str] = Counter()
    confirmacoes: Dict[int, str] = {}
    atualizados = 0

    for jogo in jogos_copa:
        fase_correta = inferir_fase({"round_number": jogo.round_number})
        contagem_fases[fase_correta] += 1
        if _normalizar_texto(jogo.fase) != _normalizar_texto(fase_correta):
            jogo.fase = fase_correta
            jogo.competicao = COMPETICAO_PADRAO
            salvar_ou_atualizar_jogo(jogo)
            atualizados += 1

    rounds_confirmacao = {
        6: "16-avos de Final",
        27: "Quartas de Final",
        28: "Semifinal",
        50: "Disputa de 3º Lugar",
        29: "Final",
    }
    for round_number, fase_esperada in rounds_confirmacao.items():
        jogo_round = next((jogo for jogo in jogos_copa if jogo.round_number == round_number), None)
        fase_encontrada = inferir_fase({"round_number": round_number})
        confirmacoes[round_number] = fase_encontrada
        if jogo_round is not None:
            print(
                f"[BSD] round_number {round_number}: "
                f"{jogo_round.time_a} x {jogo_round.time_b} -> {jogo_round.fase}"
            )
        else:
            print(f"[BSD] round_number {round_number} -> {fase_encontrada} (nenhum jogo encontrado)")
        if fase_encontrada != fase_esperada:
            print(
                f"[BSD] ATENCAO: round_number {round_number} deveria mapear para {fase_esperada}, "
                f"mas retornou {fase_encontrada}"
            )

    ordem_fases = [
        "Fase de Grupos",
        "16-avos de Final",
        "Oitavas de Final",
        "Quartas de Final",
        "Semifinal",
        "Disputa de 3º Lugar",
        "Final",
        FASE_NAO_MAPEADA,
    ]

    print(f"[BSD] {total} jogos da Copa verificados no saneamento.")
    print(f"[BSD] {atualizados} jogos tiveram a fase atualizada.")
    for fase in ordem_fases:
        quantidade = contagem_fases.get(fase, 0)
        print(f"[BSD] {quantidade} jogos com fase='{fase}'")
    print(f"[BSD] {contagem_fases.get(FASE_NAO_MAPEADA, 0)} jogos nao mapeados.")

    return {
        "total": total,
        "atualizados": atualizados,
        "por_fase": dict(contagem_fases),
        "nao_mapeados": contagem_fases.get(FASE_NAO_MAPEADA, 0),
        "confirmacoes": confirmacoes,
    }


def corrigir_grupos_fase_de_grupos(executed_by_user_id: Optional[int] = None) -> Dict[str, Any]:
    """Recalcula os grupos dos jogos da fase de grupos a partir dos times."""
    _exigir_admin(executed_by_user_id)

    jogos_copa = [
        jogo
        for jogo in listar_jogos()
        if _normalizar_texto(jogo.competicao) == _normalizar_texto(COMPETICAO_PADRAO)
        and _normalizar_texto(jogo.fase) == _normalizar_texto("Fase de Grupos")
    ]

    total = len(jogos_copa)
    contagem_por_grupo: Counter[str] = Counter()
    jogos_nao_mapeados: List[Dict[str, Any]] = []
    atualizados = 0

    for jogo in jogos_copa:
        grupo_correto = inferir_grupo_por_times(jogo.time_a, jogo.time_b)
        if grupo_correto:
            contagem_por_grupo[grupo_correto] += 1
            if _normalizar_texto(jogo.grupo) != _normalizar_texto(grupo_correto):
                jogo.grupo = grupo_correto
                jogo.competicao = COMPETICAO_PADRAO
                salvar_ou_atualizar_jogo(jogo)
                atualizados += 1
        else:
            jogos_nao_mapeados.append(
                {
                    "id": jogo.id,
                    "api_id": jogo.api_id,
                    "time_casa_nome": jogo.time_casa or jogo.time_a,
                    "time_fora_nome": jogo.time_fora or jogo.time_b,
                    "time_casa": formatar_nome_time(jogo.time_casa or jogo.time_a),
                    "time_fora": formatar_nome_time(jogo.time_fora or jogo.time_b),
                    "home_team_id": getattr(jogo, "home_team_id", None),
                    "away_team_id": getattr(jogo, "away_team_id", None),
                    "home_team_logo_url": getattr(jogo, "home_team_logo_url", None),
                    "away_team_logo_url": getattr(jogo, "away_team_logo_url", None),
                    "fase": jogo.fase,
                    "round_number": jogo.round_number,
                    "data_jogo": jogo.data_jogo,
                }
            )

    print(f"[BSD] {total} jogos de fase de grupos verificados para correção de grupo.")
    print(f"[BSD] {atualizados} jogos tiveram o grupo atualizado.")
    for grupo in WORLD_CUP_GROUPS_2026.keys():
        quantidade = contagem_por_grupo.get(grupo, 0)
        print(f"[BSD] {grupo}: {quantidade} jogos")
    print(f"[BSD] Não mapeados: {len(jogos_nao_mapeados)}")
    if jogos_nao_mapeados:
        print("[BSD] Jogos sem grupo identificado:")
        for item in jogos_nao_mapeados:
            print(
                f"[BSD] - {item['time_casa']} x {item['time_fora']} | "
                f"fase={item['fase']} | round={item['round_number']} | data={item['data_jogo']}"
            )

    return {
        "total": total,
        "atualizados": atualizados,
        "por_grupo": dict(contagem_por_grupo),
        "nao_mapeados": len(jogos_nao_mapeados),
        "jogos_nao_mapeados": jogos_nao_mapeados,
    }


def listar_jogos_importados_debug(limit: int = 20) -> List[Dict[str, Any]]:
    """Retorna uma amostra de jogos importados para depuracao administrativa."""
    jogos_ordenados = sorted(listar_jogos(), key=lambda jogo: jogo.id or 0)
    amostra: List[Dict[str, Any]] = []
    for jogo in jogos_ordenados[: max(int(limit), 0)]:
        amostra.append(
                {
                    "id": jogo.id,
                    "api_id": jogo.api_id,
                    "time_casa_nome": jogo.time_casa or jogo.time_a,
                    "time_fora_nome": jogo.time_fora or jogo.time_b,
                    "time_casa": formatar_nome_time(jogo.time_casa or jogo.time_a),
                    "time_fora": formatar_nome_time(jogo.time_fora or jogo.time_b),
                    "home_team_id": getattr(jogo, "home_team_id", None),
                    "away_team_id": getattr(jogo, "away_team_id", None),
                    "home_team_logo_url": getattr(jogo, "home_team_logo_url", None),
                    "away_team_logo_url": getattr(jogo, "away_team_logo_url", None),
                    "data_jogo": jogo.data_jogo,
                    "round_number": jogo.round_number,
                    "fase": jogo.fase or FASE_NAO_MAPEADA,
                "grupo": jogo.grupo,
                "is_placeholder_bracket": identificar_placeholder_bracket(jogo.time_a, jogo.time_b),
                "estadio": getattr(jogo, "estadio", None),
                "status": jogo.status,
                "finalizado": jogo.finalizado,
            }
        )
    return amostra


def listar_jogos_por_fase(fase: Optional[str] = None) -> List[Jogo]:
    jogos = [jogo for jogo in listar_jogos() if _normalizar_texto(jogo.competicao) == _normalizar_texto(COMPETICAO_PADRAO)]
    if not fase:
        return jogos

    fase_normalizada = _normalizar_texto(fase)
    return [jogo for jogo in jogos if _normalizar_texto(jogo.fase) == fase_normalizada]


def atualizar_resultados(
    executed_by_user_id: Optional[int] = None,
) -> int:
    """Atualiza os resultados dos jogos ja iniciados ou finalizados."""
    _exigir_admin(executed_by_user_id)

    jogos_local = listar_jogos()
    atualizados = 0

    for jogo in jogos_local:
        if _normalizar_texto(jogo.competicao) != _normalizar_texto(COMPETICAO_PADRAO):
            continue
        if jogo.api_id is None or not _jogo_deve_ser_atualizado(jogo):
            continue

        try:
            jogo_atualizado = buscar_detalhes_jogo(int(jogo.api_id))
        except BSDAPIError as exc:
            if exc.status_code in {401, 403}:
                raise
            print(f"[BSD] Falha ao atualizar o jogo {jogo.api_id}: {exc}")
            continue

        jogo_atualizado.competicao = COMPETICAO_PADRAO
        salvar_ou_atualizar_jogo(jogo_atualizado)
        atualizados += 1

    return atualizados


def gerar_mata_mata_automatico(executed_by_user_id: Optional[int] = None) -> int:
    """Cria confrontos de mata-mata com base na classificacao atual."""
    _exigir_admin(executed_by_user_id)

    atualizar_tabela_classificacao(executed_by_user_id=executed_by_user_id)
    top_duas = obter_top_duas_por_grupo()
    grupos_ordenados = sorted(top_duas.keys())
    if len(grupos_ordenados) < 2:
        return 0

    confrontos: List[Jogo] = []
    fase_mata_mata = _fase_mata_mata_inicial(len(grupos_ordenados))
    for indice in range(0, len(grupos_ordenados) - 1, 2):
        grupo_a = grupos_ordenados[indice]
        grupo_b = grupos_ordenados[indice + 1]
        melhores_a = top_duas.get(grupo_a, [])
        melhores_b = top_duas.get(grupo_b, [])
        if len(melhores_a) < 2 or len(melhores_b) < 2:
            continue

        confrontos.extend(
            [
                Jogo(
                    None,
                    melhores_a[0],
                    melhores_b[1],
                    fase=fase_mata_mata,
                    grupo=None,
                    data_jogo=None,
                    status="agendado",
                    competicao=COMPETICAO_PADRAO,
                ),
                Jogo(
                    None,
                    melhores_b[0],
                    melhores_a[1],
                    fase=fase_mata_mata,
                    grupo=None,
                    data_jogo=None,
                    status="agendado",
                    competicao=COMPETICAO_PADRAO,
                ),
            ]
        )

    salvar_jogos_em_lote(confrontos)
    return len(confrontos)
