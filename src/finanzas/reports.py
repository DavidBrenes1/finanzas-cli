"""Lógica de reportes: funciones puras, sin acceso a base de datos."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from .models import Tipo, Transaccion


@dataclass(frozen=True)
class Resumen:
    ingresos: int
    gastos: int

    @property
    def balance(self) -> int:
        return self.ingresos - self.gastos

    @property
    def tasa_ahorro(self) -> float:
        """Porcentaje de los ingresos que no se gastó (0 si no hay ingresos)."""
        return 0.0 if self.ingresos == 0 else round(self.balance / self.ingresos * 100, 1)


@dataclass(frozen=True)
class EstadoPresupuesto:
    categoria: str
    limite: int
    gastado: int

    @property
    def restante(self) -> int:
        return self.limite - self.gastado

    @property
    def porcentaje(self) -> float:
        return round(self.gastado / self.limite * 100, 1)

    @property
    def excedido(self) -> bool:
        return self.gastado > self.limite


def resumen(transacciones: Iterable[Transaccion]) -> Resumen:
    ingresos = gastos = 0
    for t in transacciones:
        if t.tipo is Tipo.INGRESO:
            ingresos += t.centavos
        else:
            gastos += t.centavos
    return Resumen(ingresos, gastos)


def gastos_por_categoria(transacciones: Iterable[Transaccion]) -> list[tuple[str, int]]:
    """Total gastado por categoría, ordenado de mayor a menor."""
    totales: dict[str, int] = defaultdict(int)
    for t in transacciones:
        if t.tipo is Tipo.GASTO:
            totales[t.categoria] += t.centavos
    return sorted(totales.items(), key=lambda par: (-par[1], par[0]))


def balance_mensual(transacciones: Iterable[Transaccion]) -> list[tuple[str, int]]:
    """Balance neto por mes (AAAA-MM), en orden cronológico."""
    meses: dict[str, int] = defaultdict(int)
    for t in transacciones:
        meses[t.fecha.strftime("%Y-%m")] += t.monto_con_signo
    return sorted(meses.items())


def estado_presupuestos(
    transacciones: Iterable[Transaccion], presupuestos: dict[str, int]
) -> list[EstadoPresupuesto]:
    gastado = dict(gastos_por_categoria(transacciones))
    return [
        EstadoPresupuesto(cat, limite, gastado.get(cat, 0))
        for cat, limite in sorted(presupuestos.items())
    ]


def barra(valor: int, maximo: int, ancho: int = 20) -> str:
    """Barra de texto proporcional, p. ej. '██████░░░░'."""
    if maximo <= 0:
        return "░" * ancho
    llenos = min(ancho, round(valor / maximo * ancho))
    return "█" * llenos + "░" * (ancho - llenos)
