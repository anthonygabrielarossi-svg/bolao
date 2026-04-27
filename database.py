"""Compatibilidade com imports antigos do projeto.

O codigo novo vive no pacote `database/`.
"""

from database.database import *  # noqa: F401,F403


if __name__ == "__main__":
    from database.database import DB_PATH, init_db

    init_db()
    print(f"Banco inicializado em: {DB_PATH}")
