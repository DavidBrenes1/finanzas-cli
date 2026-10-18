from datetime import date

import pytest

from finanzas.models import ErrorValidacion, Tipo, Transaccion, a_centavos, formatear


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("10", 1000), ("0.1", 10), ("12.345", 1235), (99.99, 9999), ("1e3", 100000)],
)
def test_a_centavos(entrada, esperado):
    assert a_centavos(entrada) == esperado


@pytest.mark.parametrize("entrada", ["0", "-5", "abc", "", "nan", "inf"])
def test_a_centavos_rechaza_invalidos(entrada):
    with pytest.raises(ErrorValidacion):
        a_centavos(entrada)


def test_formatear():
    assert formatear(0) == "0.00"
    assert formatear(123456789) == "1,234,567.89"
    assert formatear(-1) == "-0.01"


def test_monto_con_signo():
    hoy = date(2026, 1, 1)
    assert Transaccion(Tipo.INGRESO, 500, "x", hoy).monto_con_signo == 500
    assert Transaccion(Tipo.GASTO, 500, "x", hoy).monto_con_signo == -500


def test_transaccion_valida_campos():
    with pytest.raises(ErrorValidacion):
        Transaccion(Tipo.GASTO, 0, "comida", date.today())
    with pytest.raises(ErrorValidacion):
        Transaccion(Tipo.GASTO, 100, "   ", date.today())
