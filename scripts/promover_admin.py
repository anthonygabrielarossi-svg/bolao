"""Promove um usuario existente a administrador, com validacao de senha.

Uso:
    python scripts/promover_admin.py --nome Anthony
    python scripts/promover_admin.py --nome Anthony --senha "senha_atual"
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import autenticar_usuario, init_db, promover_usuario_para_admin


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promove um usuario existente para administrador.")
    parser.add_argument("--nome", required=True, help="Nome do usuario a promover.")
    parser.add_argument("--senha", default="", help="Senha atual do usuario. Se vazia, sera solicitada no terminal.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    nome = args.nome.strip()
    senha = args.senha

    if not senha:
        senha = getpass.getpass("Senha atual do usuario: ")

    init_db()
    usuario = autenticar_usuario(nome, senha)
    if not usuario:
        print("Credenciais invalidas. Nao foi possivel promover o usuario.")
        return 1

    if usuario.is_admin:
        print("Este usuario ja e administrador.")
        return 0

    if promover_usuario_para_admin(usuario.id):
        print(f"Usuario promovido para administrador: {usuario.nome}")
        return 0

    print("Nao foi possivel promover o usuario.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
