from finanzas.reports import (
    EstadoPresupuesto,
    balance_mensual,
    barra,
    estado_presupuestos,
    gastos_por_categoria,
    resumen,
)


def test_resumen(muestra):
    r = resumen(muestra)
    assert (r.ingresos, r.gastos, r.balance) == (200_000, 60_000, 140_000)
    assert r.tasa_ahorro == 70.0


def test_resumen_vacio():
    r = resumen([])
    assert r.balance == 0 and r.tasa_ahorro == 0.0


def test_gastos_por_categoria_ordenado(muestra):
    assert gastos_por_categoria(muestra) == [("comida", 50_000), ("transporte", 10_000)]


def test_balance_mensual(muestra):
    assert balance_mensual(muestra) == [("2026-09", 60_000), ("2026-10", 80_000)]


def test_estado_presupuestos(muestra):
    estados = estado_presupuestos(muestra, {"comida": 40_000, "ocio": 5_000})
    comida, ocio = estados
    assert comida == EstadoPresupuesto("comida", 40_000, 50_000)
    assert comida.excedido and comida.restante == -10_000 and comida.porcentaje == 125.0
    assert not ocio.excedido and ocio.gastado == 0


def test_barra():
    assert barra(5, 10, ancho=10) == "█████░░░░░"
    assert barra(50, 10, ancho=4) == "████"
    assert barra(1, 0, ancho=3) == "░░░"
