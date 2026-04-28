"""Atualiza resultados, classificacao e ranking a partir da API BSD.

Uso:
    python scripts/atualizar_resultados.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import DatabaseError, init_db
from services.api_service import BSDAPIError
from services.classificacao_service import atualizar_tabela_classificacao
from services.jogos_service import atualizar_resultados
from services.ranking_service import recalcular_ranking_automaticamente


def _agora_formatado() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(mensagem: str) -> None:
    print(f"[{_agora_formatado()}] {mensagem}")


def main() -> int:
    init_db()

    log("Iniciando atualizacao dos resultados da Copa do Mundo (liga 27).")

    try:
        atualizados = atualizar_resultados()
        classificacao = atualizar_tabela_classificacao()
        ranking = recalcular_ranking_automaticamente()
    except BSDAPIError as exc:
        log(f"Falha ao consultar a API BSD: {exc}")
        return 1
    except DatabaseError as exc:
        log(f"Falha ao salvar no banco: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - protecao extra para execucao manual
        log(f"Erro inesperado: {exc}")
        return 1

    log(
        "Atualizacao concluida. "
        f"Resultados processados: {atualizados}, "
        f"linhas de classificacao: {len(classificacao)}, "
        f"usuarios recalculados: {len(ranking)}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
