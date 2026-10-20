from datetime import date

from finanzas.analisis import (
    Variacion,
    comparar_meses,
    gastos_inusuales,
    proyectar,
    proyectar_por_categoria,
)
from finanzas.models import Tipo, Transaccion

OCT = (date(2026, 10, 1), date(2026, 10, 31))


def gasto(monto, cat="comida", dia=1, mes=10):
    return Transaccion(Tipo.GASTO, monto, cat, date(2026, mes, dia))


def test_comparar_meses():
    actual = [gasto(150, "comida"), gasto(50, "ocio")]
    anterior = [gasto(100, "comida", mes=9), gasto(80, "transporte", mes=9)]
    assert comparar_meses(actual, anterior) == [
        Variacion("comida", 150, 100),
        Variacion("ocio", 50, 0),
        Variacion("transporte", 0, 80),
    ]
    porcentajes = [v.porcentaje for v in comparar_meses(actual, anterior)]
    assert porcentajes == [50.0, None, -100.0]


def test_comparar_ignora_ingresos():
    ingreso = Transaccion(Tipo.INGRESO, 999, "salario", date(2026, 10, 1))
    assert comparar_meses([ingreso], []) == []


def test_proyectar_bordes():
    assert proyectar(100, date(2026, 10, 31), *OCT) == 100  # último día
    assert proyectar(0, date(2026, 9, 1), *OCT) == 0  # mes futuro
    assert proyectar(100, date(2026, 10, 1), *OCT) == 3100  # día 1


def test_proyectar_por_categoria():
    del_mes = [gasto(1000, "comida"), gasto(500, "ocio")]
    resultado = proyectar_por_categoria(del_mes, date(2026, 10, 10), *OCT)
    assert resultado == {"comida": 3100, "ocio": 1550}


def test_gastos_inusuales():
    historial = [gasto(100, mes=9), gasto(120, mes=9), gasto(110, mes=9)]
    normal, raro = gasto(130), gasto(400)
    (g,) = gastos_inusuales([normal, raro], historial)
    assert g.transaccion is raro and g.promedio == 110 and g.veces == 3.6


def test_inusuales_requiere_historial_y_maneja_desviacion_cero():
    assert gastos_inusuales([gasto(10_000)], [gasto(100, mes=9)] * 2) == []
    iguales = [gasto(100, mes=9)] * 3
    assert [
        g.transaccion.centavos for g in gastos_inusuales([gasto(140), gasto(160)], iguales)
    ] == [160]
