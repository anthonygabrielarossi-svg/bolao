"""Cria um usuario administrador de forma explicita.

Uso:
    python scripts/criar_admin.py --nome admin
    python scripts/criar_admin.py --nome admin --senha "senha_forte"
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import cadastrar_usuario, init_db


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cria um usuario administrador para o bolao.")
    parser.add_argument("--nome", required=True, help="Nome do usuario administrador.")
    parser.add_argument("--senha", default="", help="Senha do administrador. Se vazio, sera solicitada no terminal.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    nome = args.nome.strip()
    senha = args.senha

    if not senha:
        senha = getpass.getpass("Senha do administrador: ")
        confirmar = getpass.getpass("Confirme a senha: ")
        if senha != confirmar:
            print("As senhas nao conferem.")
            return 1

    init_db()
    ok, mensagem = cadastrar_usuario(nome, senha, is_admin=True)
    if not ok:
        print(f"Falha: {mensagem}")
        return 1

    print(f"Administrador criado com sucesso: {nome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
