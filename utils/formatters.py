"""Utilitarios de formatacao de nomes da Copa."""

from __future__ import annotations

from .world_cup import canonicalizar_time, formatar_nome_time, normalizar_texto


def formatar_moeda_brl(valor: float) -> str:
    numero = float(valor or 0)
    texto = f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


__all__ = ["canonicalizar_time", "formatar_moeda_brl", "formatar_nome_time", "normalizar_texto"]
