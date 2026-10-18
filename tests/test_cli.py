from pathlib import Path

import pytest

from finanzas.cli import _mes, main

EJEMPLO = Path(__file__).parent.parent / "docs" / "ejemplo.csv"


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "test.db")


def run(db, *args):
    return main(["--db", db, *args])


def test_flujo_completo(db, capsys):
    assert run(db, "ingreso", "1000", "salario", "-f", "2026-10-01") == 0
    assert run(db, "gasto", "250.50", "Comida", "-d", "súper", "-f", "2026-10-02") == 0
    capsys.readouterr()

    assert run(db, "listar") == 0
    salida = capsys.readouterr().out
    assert "salario" in salida and "-250.50" in salida and "súper" in salida

    assert run(db, "reporte") == 0
    salida = capsys.readouterr().out
    assert "749.50" in salida and "ahorro 75.0%" in salida


def test_presupuesto(db, capsys):
    run(db, "gasto", "120", "comida", "-f", "2026-10-05")
    run(db, "presupuesto", "comida", "100")
    capsys.readouterr()
    assert run(db, "presupuesto", "-m", "2026-10") == 0
    salida = capsys.readouterr().out
    assert "120.0%" in salida and "EXCEDIDO" in salida


def test_importar_y_reporte_mensual(db, capsys):
    assert run(db, "importar", str(EJEMPLO)) == 0
    assert "9 transacciones" in capsys.readouterr().out
    assert run(db, "reporte", "-m", "2026-09") == 0
    salida = capsys.readouterr().out
    assert "850,000.00" in salida and "vivienda" in salida
    assert "Balance mensual" not in salida  # un solo mes


def test_exportar(db, tmp_path):
    run(db, "importar", str(EJEMPLO))
    destino = tmp_path / "out.csv"
    assert run(db, "exportar", str(destino)) == 0
    assert len(destino.read_text(encoding="utf-8").splitlines()) == 10


@pytest.mark.parametrize(
    "args",
    [
        ("gasto", "-5", "comida"),
        ("eliminar", "999"),
        ("importar", "no_existe.csv"),
        ("presupuesto", "comida"),
    ],
)
def test_errores_devuelven_1(db, capsys, args):
    assert run(db, *args) == 1
    assert capsys.readouterr().err.startswith("Error:")


def test_fecha_invalida_sale_con_error_de_argparse(db):
    with pytest.raises(SystemExit) as exc:
        run(db, "gasto", "5", "x", "-f", "31-12-2026")
    assert exc.value.code == 2


@pytest.mark.parametrize(("mes", "ultimo_dia"), [("2026-02", 28), ("2024-02", 29), ("2026-12", 31)])
def test_rango_de_mes(mes, ultimo_dia):
    inicio, fin = _mes(mes)
    assert inicio.day == 1 and fin.day == ultimo_dia
