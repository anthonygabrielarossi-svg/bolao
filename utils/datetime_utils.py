"""Utilitarios de data e hora com comparacao timezone-aware."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


_STATUS_BLOQUEIO_IMEDIATO = {
    "inprogress",
    "in progress",
    "halftime",
    "half time",
    "finished",
    "ft",
    "fulltime",
    "full time",
    "complete",
    "completed",
    "final",
    "cancelled",
    "canceled",
}


def _normalizar_texto(texto: Optional[str]) -> str:
    return " ".join(str(texto or "").split()).strip().lower()


def parse_iso_datetime(data_hora: Optional[str]) -> Optional[datetime]:
    """Converte uma string ISO em datetime timezone-aware."""
    if not data_hora:
        return None

    texto = str(data_hora).strip().replace("Z", "+00:00")
    if not texto:
        return None

    try:
        data = datetime.fromisoformat(texto)
    except ValueError:
        return None

    if data.tzinfo is None:
        data = data.replace(tzinfo=datetime.now().astimezone().tzinfo or timezone.utc)

    return data


def _agora_no_mesmo_fuso(base: datetime, agora: Optional[datetime] = None) -> datetime:
    """Ajusta `agora` para o mesmo fuso de `base`."""
    base_tz = base.tzinfo or datetime.now().astimezone().tzinfo or timezone.utc

    if agora is None:
        return datetime.now(base_tz)

    if agora.tzinfo is None:
        return agora.replace(tzinfo=base_tz)

    return agora.astimezone(base_tz)


def jogo_ja_comecou(data_hora: Optional[str], agora: Optional[datetime] = None) -> bool:
    """Retorna True quando a hora atual ja atingiu o inicio do jogo."""
    inicio = parse_iso_datetime(data_hora)
    if inicio is None:
        return False

    agora_ref = _agora_no_mesmo_fuso(inicio, agora=agora)
    return agora_ref >= inicio


def palpite_bloqueado_para_jogo(
    data_hora: Optional[str],
    status: Optional[str] = None,
    finalizado: bool = False,
    agora: Optional[datetime] = None,
) -> bool:
    """Define se um palpite deve ficar bloqueado para um jogo."""
    if finalizado:
        return True

    status_normalizado = _normalizar_texto(status)
    if status_normalizado in _STATUS_BLOQUEIO_IMEDIATO:
        return True

    if status_normalizado == "postponed":
        inicio = parse_iso_datetime(data_hora)
        if inicio is None:
            return True
        return _agora_no_mesmo_fuso(inicio, agora=agora) >= inicio

    return jogo_ja_comecou(data_hora, agora=agora)


def bloquear_palpite_para_jogo(jogo: object, agora: Optional[datetime] = None) -> bool:
    """Atalho para checar bloqueio diretamente a partir do objeto Jogo."""
    return palpite_bloqueado_para_jogo(
        getattr(jogo, "data_jogo", None),
        getattr(jogo, "status", None),
        bool(getattr(jogo, "finalizado", False)),
        agora=agora,
    )


__all__ = [
    "bloquear_palpite_para_jogo",
    "jogo_ja_comecou",
    "palpite_bloqueado_para_jogo",
    "parse_iso_datetime",
]
