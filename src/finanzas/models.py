"""Modelos de dominio de la aplicación."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum


class Tipo(str, Enum):
    """Tipo de movimiento financiero."""

    INGRESO = "ingreso"
    GASTO = "gasto"


class ErrorValidacion(ValueError):
    """Se lanza cuando un dato de entrada no es válido."""


def a_centavos(monto: str | int | float | Decimal) -> int:
    """Convierte un monto a centavos enteros para evitar errores de punto flotante.

    >>> a_centavos("12.345")
    1235
    >>> a_centavos(10)
    1000
    """
    try:
        valor = Decimal(str(monto))
    except InvalidOperation as exc:
        raise ErrorValidacion(f"Monto inválido: {monto!r}") from exc
    if not valor.is_finite():
        raise ErrorValidacion(f"Monto inválido: {monto!r}")
    if valor <= 0:
        raise ErrorValidacion("El monto debe ser mayor que cero")
    return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def formatear(centavos: int) -> str:
    """Formatea centavos como texto legible.

    >>> formatear(123456)
    '1,234.56'
    >>> formatear(-500)
    '-5.00'
    """
    signo = "-" if centavos < 0 else ""
    return f"{signo}{abs(centavos) / 100:,.2f}"


MONEDA_BASE = "CRC"
MONEDAS = ("CRC", "USD", "EUR")


def validar_moneda(codigo: str) -> str:
    """Normaliza y valida un código de moneda.

    >>> validar_moneda(" usd ")
    'USD'
    """
    normalizado = codigo.strip().upper()
    if normalizado not in MONEDAS:
        raise ErrorValidacion(f"Moneda no soportada: {codigo!r}. Opciones: {', '.join(MONEDAS)}")
    return normalizado


@dataclass(frozen=True)
class Transaccion:
    """Un movimiento de dinero (ingreso o gasto)."""

    tipo: Tipo
    centavos: int
    categoria: str
    fecha: date
    descripcion: str = ""
    moneda: str = MONEDA_BASE
    id: int | None = None

    def __post_init__(self) -> None:
        if self.centavos <= 0:
            raise ErrorValidacion("El monto debe ser mayor que cero")
        if not self.categoria.strip():
            raise ErrorValidacion("La categoría no puede estar vacía")
        if self.moneda not in MONEDAS:
            raise ErrorValidacion(f"Moneda no soportada: {self.moneda!r}")

    @property
    def monto_con_signo(self) -> int:
        """Monto positivo para ingresos y negativo para gastos."""
        return self.centavos if self.tipo is Tipo.INGRESO else -self.centavos


@dataclass(frozen=True)
class Meta:
    """Una meta de ahorro con monto objetivo y, opcionalmente, fecha límite."""

    nombre: str
    objetivo: int
    ahorrado: int = 0
    fecha_limite: date | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise ErrorValidacion("El nombre de la meta no puede estar vacío")
        if self.objetivo <= 0:
            raise ErrorValidacion("El objetivo debe ser mayor que cero")
        if self.ahorrado < 0:
            raise ErrorValidacion("El monto ahorrado no puede ser negativo")
