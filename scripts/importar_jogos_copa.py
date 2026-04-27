"""Importa jogos da Copa do Mundo via API BSD.

Uso:
    python scripts/importar_jogos_copa.py
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import init_db
from services.api_service import BSDAPIError
from services.jogos_service import importar_jogos_copa


def _agora_formatado() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(mensagem: str) -> None:
    print(f"[{_agora_formatado()}] {mensagem}")


def main() -> int:
    init_db()

    log("Iniciando importacao de jogos da Copa do Mundo (liga 27).")

    try:
        total = importar_jogos_copa()
    except BSDAPIError as exc:
        log(f"Falha ao consultar a API BSD: {exc}")
        return 1
    except sqlite3.Error as exc:
        log(f"Falha ao salvar no SQLite: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - protecao extra para execucao manual
        log(f"Erro inesperado: {exc}")
        return 1

    if total == 0:
        log("Nenhum jogo foi retornado pela API.")
        return 0

    log(f"Importacao concluida com sucesso. {total} jogos importados ou atualizados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
