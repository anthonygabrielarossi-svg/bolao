"""Compatibilidade com o nome antigo do script de importacao.

O fluxo principal agora vive em `scripts/importar_jogos_copa.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.importar_jogos_copa import main


if __name__ == "__main__":
    raise SystemExit(main())
