"""Conversión de montos a la moneda base (CRC).

Los tipos de cambio se expresan como "cuántos colones vale 1 unidad de la moneda",
por ejemplo ``{"USD": Decimal("505.50")}``. Se usan ``Decimal`` para no perder precisión.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .models import MONEDA_BASE, ErrorValidacion, Transaccion

TiposCambio = Mapping[str, Decimal]


def parsear_tasa(texto: str) -> Decimal:
    """Valida un tipo de cambio escrito por el usuario.

    >>> parsear_tasa("505.5")
    Decimal('505.5')
    """
    try:
        tasa = Decimal(texto.strip())
    except InvalidOperation as exc:
        raise ErrorValidacion(f"Tipo de cambio inválido: {texto!r}") from exc
    if not tasa.is_finite() or tasa <= 0:
        raise ErrorValidacion("El tipo de cambio debe ser un número mayor que cero")
    return tasa


def a_base(centavos: int, moneda: str, tasas: TiposCambio) -> int:
    """Convierte centavos de ``moneda`` a centavos de la moneda base.

    >>> a_base(1000, "USD", {"USD": Decimal("505.50")})
    505500
    >>> a_base(1000, "CRC", {})
    1000
    """
    if moneda == MONEDA_BASE:
        return centavos
    if moneda not in tasas:
        raise ErrorValidacion(
            f"Falta el tipo de cambio de {moneda}. Ejemplo: finanzas cambio {moneda} 505.50"
        )
    convertido = (Decimal(centavos) * tasas[moneda]).quantize(Decimal("1"), ROUND_HALF_UP)
    return max(1, int(convertido))


def convertir(transacciones: Iterable[Transaccion], tasas: TiposCambio) -> list[Transaccion]:
    """Devuelve copias de las transacciones expresadas en la moneda base."""
    return [
        t
        if t.moneda == MONEDA_BASE
        else replace(t, centavos=a_base(t.centavos, t.moneda, tasas), moneda=MONEDA_BASE)
        for t in transacciones
    ]
