from datetime import date

import pytest

from finanzas.models import Tipo, Transaccion
from finanzas.storage import Repositorio


@pytest.fixture
def repo():
    with Repositorio(":memory:") as r:
        yield r


@pytest.fixture
def muestra():
    return [
        Transaccion(Tipo.INGRESO, 100_000, "salario", date(2026, 9, 1)),
        Transaccion(Tipo.GASTO, 30_000, "comida", date(2026, 9, 5)),
        Transaccion(Tipo.GASTO, 10_000, "transporte", date(2026, 9, 9)),
        Transaccion(Tipo.GASTO, 20_000, "comida", date(2026, 10, 2)),
        Transaccion(Tipo.INGRESO, 100_000, "salario", date(2026, 10, 1)),
    ]
