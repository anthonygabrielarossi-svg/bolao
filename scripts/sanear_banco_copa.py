"""Limpa o banco e remove dados contaminados por outras competicoes.

Uso:
    python scripts/sanear_banco_copa.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import init_db, limpar_dados_invalidos
from services.classificacao_service import atualizar_tabela_classificacao
from services.ranking_service import recalcular_ranking_automaticamente


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Remove dados invalidados do bolao.")
    parser.add_argument(
        "--remover-usuarios",
        action="store_true",
        help="Remove usuarios tambem. Por padrao, os usuarios sao preservados.",
    )
    parser.add_argument(
        "--recalcular",
        action="store_true",
        help="Recalcula classificacao e ranking apos o saneamento.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    init_db()

    resumo = limpar_dados_invalidos(preservar_usuarios=not args.remover_usuarios)
    linhas_classificacao = 0
    usuarios_recalculados = 0
    if args.recalcular:
        classificacao = atualizar_tabela_classificacao()
        ranking = recalcular_ranking_automaticamente()
        linhas_classificacao = len(classificacao)
        usuarios_recalculados = len(ranking)

    print(
        "Banco saneado com sucesso. "
        f"Jogos removidos: {resumo['jogos']}, "
        f"palpites de partidas: {resumo['palpites_partidas']}, "
        f"palpites especiais: {resumo['palpites_especiais']}, "
        f"classificacao: {resumo['classificacao']}, "
        f"usuarios existentes: {resumo['usuarios']}. "
        + (
            f"Recalculo concluido: {linhas_classificacao} linhas de classificacao, "
            f"{usuarios_recalculados} usuarios recalculados."
            if args.recalcular
            else ""
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
