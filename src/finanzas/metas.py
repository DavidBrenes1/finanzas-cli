"""Cálculos de progreso de metas de ahorro (funciones puras)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .models import Meta


def meses_restantes(hoy: date, limite: date) -> int:
    """Meses disponibles para ahorrar, contando el mes actual.

    >>> meses_restantes(date(2026, 10, 20), date(2026, 12, 31))
    3
    >>> meses_restantes(date(2026, 10, 20), date(2026, 9, 1))
    0
    """
    if limite < hoy:
        return 0
    return (limite.year - hoy.year) * 12 + limite.month - hoy.month + 1


@dataclass(frozen=True)
class EstadoMeta:
    meta: Meta
    hoy: date

    @property
    def restante(self) -> int:
        return max(0, self.meta.objetivo - self.meta.ahorrado)

    @property
    def porcentaje(self) -> float:
        return round(self.meta.ahorrado / self.meta.objetivo * 100, 1)

    @property
    def completada(self) -> bool:
        return self.meta.ahorrado >= self.meta.objetivo

    @property
    def vencida(self) -> bool:
        limite = self.meta.fecha_limite
        return not self.completada and limite is not None and limite < self.hoy

    @property
    def mensual_necesario(self) -> int | None:
        """Cuánto ahorrar por mes para llegar a tiempo (None si no hay fecha o ya venció)."""
        limite = self.meta.fecha_limite
        if self.completada or limite is None or self.vencida:
            return None
        meses = meses_restantes(self.hoy, limite)
        return -(-self.restante // meses)  # división redondeando hacia arriba


def estado_metas(metas: list[Meta], hoy: date) -> list[EstadoMeta]:
    return [EstadoMeta(m, hoy) for m in metas]
