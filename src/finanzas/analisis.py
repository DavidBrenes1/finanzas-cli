"""Análisis de gastos: comparación entre meses, proyección y gastos inusuales.

Funciones puras: reciben listas de transacciones (ya convertidas a la moneda base)
y devuelven datos; no leen la base de datos ni imprimen.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from .models import Tipo, Transaccion
from .reports import gastos_por_categoria


@dataclass(frozen=True)
class Variacion:
    categoria: str
    actual: int
    anterior: int

    @property
    def porcentaje(self) -> float | None:
        """Cambio porcentual respecto al mes anterior (None si antes no hubo gasto)."""
        if self.anterior == 0:
            return None
        return round((self.actual - self.anterior) / self.anterior * 100, 1)


def comparar_meses(
    actual: Iterable[Transaccion], anterior: Iterable[Transaccion]
) -> list[Variacion]:
    """Gasto por categoría de un mes frente al anterior, de mayor a menor gasto actual."""
    act = dict(gastos_por_categoria(actual))
    ant = dict(gastos_por_categoria(anterior))
    categorias = set(act) | set(ant)
    variaciones = [Variacion(c, act.get(c, 0), ant.get(c, 0)) for c in categorias]
    return sorted(variaciones, key=lambda v: (-v.actual, -v.anterior, v.categoria))


def proyectar(gastado: int, hoy: date, inicio: date, fin: date) -> int:
    """Proyecta el gasto al cierre del mes según el ritmo diario actual.

    >>> proyectar(10_000, date(2026, 10, 10), date(2026, 10, 1), date(2026, 10, 31))
    31000
    >>> proyectar(10_000, date(2026, 11, 5), date(2026, 10, 1), date(2026, 10, 31))
    10000
    """
    if hoy >= fin:
        return gastado
    if hoy < inicio:
        return 0
    dias_transcurridos = (hoy - inicio).days + 1
    dias_mes = (fin - inicio).days + 1
    return round(gastado * dias_mes / dias_transcurridos)


def proyectar_por_categoria(
    del_mes: Iterable[Transaccion], hoy: date, inicio: date, fin: date
) -> dict[str, int]:
    return {cat: proyectar(total, hoy, inicio, fin) for cat, total in gastos_por_categoria(del_mes)}


@dataclass(frozen=True)
class GastoInusual:
    transaccion: Transaccion
    promedio: int

    @property
    def veces(self) -> float:
        """Cuántas veces el promedio de la categoría representa este gasto."""
        return round(self.transaccion.centavos / self.promedio, 1)


def gastos_inusuales(
    del_mes: Iterable[Transaccion],
    historial: Iterable[Transaccion],
    minimo_historial: int = 3,
    desviaciones: float = 2.0,
    factor_minimo: float = 1.5,
) -> list[GastoInusual]:
    """Gastos del mes muy por encima de lo normal en su categoría.

    Un gasto es inusual si supera **ambos** umbrales:

    - el promedio + ``desviaciones`` desviaciones estándar (es atípico estadísticamente), y
    - ``factor_minimo`` veces el promedio (la diferencia es relevante en la práctica;
      evita alertas cuando el historial es tan parejo que cualquier variación es "atípica").

    Solo evalúa categorías con al menos ``minimo_historial`` gastos previos, para no
    marcar como inusual algo que simplemente es nuevo.
    """
    previos: dict[str, list[int]] = defaultdict(list)
    for t in historial:
        if t.tipo is Tipo.GASTO:
            previos[t.categoria].append(t.centavos)

    resultado = []
    for t in del_mes:
        montos = previos.get(t.categoria, [])
        if t.tipo is not Tipo.GASTO or len(montos) < minimo_historial:
            continue
        promedio = statistics.fmean(montos)
        desviacion = statistics.pstdev(montos)
        umbral = max(promedio + desviaciones * desviacion, promedio * factor_minimo)
        if t.centavos > umbral:
            resultado.append(GastoInusual(t, round(promedio)))
    return sorted(resultado, key=lambda g: -g.veces)
