"""Servico de calculo de ranking e pontuacao dos usuarios.

A pontuacao e recalculada a partir dos palpites de partidas e dos palpites
especiais, mantendo o ranking sempre derivado da base local SQLite.
"""

from __future__ import annotations

import unicodedata
from typing import Dict, List, Optional

from database import (
    COMPETICAO_PADRAO,
    PontuacaoUsuario,
    atualizar_pontuacao_usuario,
    atualizar_pontuacoes_usuarios_em_lote,
    carregar_palpites_especiais,
    carregar_resultados_oficiais,
    contar_usuarios_aprovados,
    listar_jogos,
    listar_palpites_partidas_usuario,
    listar_todos_palpites_especiais,
    listar_todos_palpites_partidas,
    listar_usuarios,
    listar_usuarios_ranking,
    usuario_eh_admin,
)


PESOS_ESPECIAIS = {
    "campeao": 20,
    "vice": 15,
    "artilheiro": 10,
    "melhor_jogador": 10,
    "primeiro_grupo_a": 5,
    "segundo_grupo_a": 5,
}


def calcular_premiacao_bolao(total_usuarios_aprovados: int) -> Dict[str, float]:
    valor_acumulado = int(total_usuarios_aprovados) * 50
    return {
        "valor_acumulado": valor_acumulado,
        "primeiro": valor_acumulado * 0.60,
        "segundo": valor_acumulado * 0.30,
        "terceiro": valor_acumulado * 0.10,
    }


def obter_premiacao_bolao() -> Dict[str, float]:
    total_aprovados = contar_usuarios_aprovados()
    premiacao = calcular_premiacao_bolao(total_aprovados)
    premiacao["total_usuarios_aprovados"] = total_aprovados
    return premiacao


def _normalizar_texto(texto: Optional[str]) -> str:
    texto = texto or ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("ASCII")
    return texto.strip().lower()


def _exigir_admin(executed_by_user_id: Optional[int]) -> None:
    if executed_by_user_id is not None and not usuario_eh_admin(executed_by_user_id):
        raise PermissionError("Apenas administradores podem recalcular o ranking.")


def pontuar_partida(palpite_a: int, palpite_b: int, placar_a: int, placar_b: int) -> int:
    """Aplica a regra simples de pontuacao para uma partida."""
    if palpite_a == placar_a and palpite_b == placar_b:
        return 10

    resultado_palpite = (palpite_a > palpite_b) - (palpite_a < palpite_b)
    resultado_real = (placar_a > placar_b) - (placar_a < placar_b)
    if resultado_palpite == resultado_real:
        return 5

    return 0


def pontuar_palpite_especial(chave: str, palpite: str, oficial: str) -> int:
    if not palpite or not oficial:
        return 0
    if _normalizar_texto(palpite) == _normalizar_texto(oficial):
        return PESOS_ESPECIAIS.get(chave, 0)
    return 0


def calcular_pontuacao_usuario(
    user_id: int,
    *,
    usuarios_por_id: Optional[Dict[int, object]] = None,
    jogos_finalizados: Optional[Dict[int, object]] = None,
    resultados_oficiais=None,
) -> PontuacaoUsuario:
    """Recalcula a pontuacao de um usuario com base nos palpites cadastrados."""
    palpites_partidas = {item.match_id: item for item in listar_palpites_partidas_usuario(user_id)}
    palpites_especiais = carregar_palpites_especiais(user_id)
    resultados_oficiais = resultados_oficiais or carregar_resultados_oficiais()
    if jogos_finalizados is None:
        jogos_finalizados = {
            jogo.id: jogo
            for jogo in listar_jogos()
            if jogo.finalizado
            and jogo.placar_a is not None
            and jogo.placar_b is not None
            and jogo.id is not None
            and jogo.competicao == COMPETICAO_PADRAO
        }

    pontos_partidas = 0
    for match_id, palpite in palpites_partidas.items():
        jogo = jogos_finalizados.get(match_id)
        if not jogo:
            continue
        pontos_partidas += pontuar_partida(palpite.palpite_a, palpite.palpite_b, int(jogo.placar_a), int(jogo.placar_b))

    pontos_especiais = 0
    if palpites_especiais:
        pontos_especiais += pontuar_palpite_especial("campeao", palpites_especiais.campeao, resultados_oficiais.campeao)
        pontos_especiais += pontuar_palpite_especial("vice", palpites_especiais.vice, resultados_oficiais.vice)
        pontos_especiais += pontuar_palpite_especial("artilheiro", palpites_especiais.artilheiro, resultados_oficiais.artilheiro)
        pontos_especiais += pontuar_palpite_especial("melhor_jogador", palpites_especiais.melhor_jogador, resultados_oficiais.melhor_jogador)
        pontos_especiais += pontuar_palpite_especial("primeiro_grupo_a", palpites_especiais.primeiro_grupo_a, resultados_oficiais.primeiro_grupo_a)
        pontos_especiais += pontuar_palpite_especial("segundo_grupo_a", palpites_especiais.segundo_grupo_a, resultados_oficiais.segundo_grupo_a)

    pontuacao_total = pontos_partidas + pontos_especiais
    atualizar_pontuacao_usuario(user_id, pontuacao_total)

    if usuarios_por_id is None:
        usuario = next((item for item in listar_usuarios() if item.id == user_id), None)
    else:
        usuario = usuarios_por_id.get(user_id)
    nome = usuario.nome if usuario else f"Usuario {user_id}"

    return PontuacaoUsuario(
        user_id=user_id,
        nome=nome,
        pontos_partidas=pontos_partidas,
        pontos_especiais=pontos_especiais,
        pontuacao_total=pontuacao_total,
    )


def recalcular_ranking_automaticamente(executed_by_user_id: Optional[int] = None) -> List[PontuacaoUsuario]:
    """Atualiza a pontuacao total de todos os usuarios e devolve o ranking."""
    _exigir_admin(executed_by_user_id)
    ranking_calculado: List[PontuacaoUsuario] = []
    usuarios = listar_usuarios()
    usuarios_por_id = {int(usuario.id): usuario for usuario in usuarios if usuario.id is not None}
    resultados_oficiais = carregar_resultados_oficiais()
    palpites_partidas_por_usuario: Dict[int, Dict[int, object]] = {}
    for palpite in listar_todos_palpites_partidas():
        palpites_partidas_por_usuario.setdefault(int(palpite.user_id), {})[int(palpite.match_id)] = palpite
    palpites_especiais_por_usuario = {
        int(palpite.user_id): palpite
        for palpite in listar_todos_palpites_especiais()
    }
    jogos_finalizados = {
        jogo.id: jogo
        for jogo in listar_jogos()
        if jogo.finalizado
        and jogo.placar_a is not None
        and jogo.placar_b is not None
        and jogo.id is not None
        and jogo.competicao == COMPETICAO_PADRAO
    }
    for usuario in usuarios:
        if usuario.id is None:
            continue
        user_id = int(usuario.id)
        palpites_partidas = palpites_partidas_por_usuario.get(user_id, {})
        palpites_especiais = palpites_especiais_por_usuario.get(user_id)

        pontos_partidas = 0
        for match_id, palpite in palpites_partidas.items():
            jogo = jogos_finalizados.get(match_id)
            if not jogo:
                continue
            pontos_partidas += pontuar_partida(
                palpite.palpite_a,
                palpite.palpite_b,
                int(jogo.placar_a),
                int(jogo.placar_b),
            )

        pontos_especiais = 0
        if palpites_especiais:
            pontos_especiais += pontuar_palpite_especial("campeao", palpites_especiais.campeao, resultados_oficiais.campeao)
            pontos_especiais += pontuar_palpite_especial("vice", palpites_especiais.vice, resultados_oficiais.vice)
            pontos_especiais += pontuar_palpite_especial("artilheiro", palpites_especiais.artilheiro, resultados_oficiais.artilheiro)
            pontos_especiais += pontuar_palpite_especial("melhor_jogador", palpites_especiais.melhor_jogador, resultados_oficiais.melhor_jogador)
            pontos_especiais += pontuar_palpite_especial("primeiro_grupo_a", palpites_especiais.primeiro_grupo_a, resultados_oficiais.primeiro_grupo_a)
            pontos_especiais += pontuar_palpite_especial("segundo_grupo_a", palpites_especiais.segundo_grupo_a, resultados_oficiais.segundo_grupo_a)

        pontuacao_total = pontos_partidas + pontos_especiais
        ranking_calculado.append(
            PontuacaoUsuario(
                user_id=user_id,
                nome=usuarios_por_id[user_id].nome,
                pontos_partidas=pontos_partidas,
                pontos_especiais=pontos_especiais,
                pontuacao_total=pontuacao_total,
            )
        )

    atualizar_pontuacoes_usuarios_em_lote(
        {item.user_id: item.pontuacao_total for item in ranking_calculado}
    )
    ranking_calculado.sort(key=lambda item: (-item.pontuacao_total, item.nome.lower()))
    return ranking_calculado


def listar_ranking_atual() -> List[PontuacaoUsuario]:
    """Retorna o ranking salvo no banco de dados."""
    return [
        PontuacaoUsuario(
            user_id=item.id,
            nome=item.nome,
            pontos_partidas=0,
            pontos_especiais=0,
            pontuacao_total=item.pontuacao_total,
        )
        for item in listar_usuarios_ranking()
    ]
