from datetime import date

import pytest

from finanzas.metas import EstadoMeta, estado_metas, meses_restantes
from finanzas.models import ErrorValidacion, Meta

HOY = date(2026, 10, 20)


@pytest.mark.parametrize(
    ("limite", "esperado"),
    [
        (date(2026, 10, 31), 1),
        (date(2027, 1, 1), 4),
        (date(2027, 10, 1), 13),
        (date(2026, 1, 1), 0),
    ],
)
def test_meses_restantes(limite, esperado):
    assert meses_restantes(HOY, limite) == esperado


def test_mensual_necesario_redondea_hacia_arriba():
    e = EstadoMeta(Meta("viaje", 100_000, 10_000, date(2026, 12, 31)), HOY)
    assert e.restante == 90_000 and e.porcentaje == 10.0
    assert e.mensual_necesario == 30_000
    e = EstadoMeta(Meta("x", 100, 0, date(2026, 12, 31)), HOY)
    assert e.mensual_necesario == 34  # 100 / 3 meses = 33.3 -> 34


def test_meta_completada_y_vencida():
    completada = EstadoMeta(Meta("a", 100, 150, date(2020, 1, 1)), HOY)
    assert completada.completada and not completada.vencida
    assert completada.restante == 0 and completada.mensual_necesario is None
    vencida = EstadoMeta(Meta("b", 100, 50, date(2026, 9, 30)), HOY)
    assert vencida.vencida and vencida.mensual_necesario is None
    sin_fecha = EstadoMeta(Meta("c", 100, 50), HOY)
    assert not sin_fecha.vencida and sin_fecha.mensual_necesario is None


def test_estado_metas():
    assert len(estado_metas([Meta("a", 1), Meta("b", 2)], HOY)) == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"nombre": " ", "objetivo": 1},
        {"nombre": "a", "objetivo": 0},
        {"nombre": "a", "objetivo": 1, "ahorrado": -1},
    ],
)
def test_meta_invalida(kwargs):
    with pytest.raises(ErrorValidacion):
        Meta(**kwargs)


def test_metas_en_repositorio(repo):
    repo.crear_meta(Meta("Viaje", 100_000, fecha_limite=date(2027, 6, 30)))
    with pytest.raises(ErrorValidacion, match="Ya existe"):
        repo.crear_meta(Meta("viaje", 5))
    assert repo.mover_a_meta("VIAJE", 30_000).ahorrado == 30_000
    assert repo.mover_a_meta("viaje", -10_000).ahorrado == 20_000
    with pytest.raises(ErrorValidacion, match="No puede retirar"):
        repo.mover_a_meta("viaje", -50_000)
    (meta,) = repo.metas()
    assert meta.fecha_limite == date(2027, 6, 30)
    with pytest.raises(ErrorValidacion, match="No existe"):
        repo.mover_a_meta("otra", 1)
    assert repo.eliminar_meta("viaje") and not repo.eliminar_meta("viaje")
