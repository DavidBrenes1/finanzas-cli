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


# --- v1.1: multimoneda, metas, análisis y gráficos ---------------------


@pytest.fixture
def hoy(monkeypatch):
    from datetime import date

    import finanzas.cli

    monkeypatch.setattr(finanzas.cli, "_hoy", lambda: date(2026, 10, 15))


def test_multimoneda(db, capsys):
    run(db, "gasto", "20", "ocio", "-M", "usd", "-f", "2026-10-02")
    run(db, "gasto", "1000", "comida", "-f", "2026-10-03")
    assert run(db, "reporte") == 1
    assert "Falta el tipo de cambio de USD" in capsys.readouterr().err

    assert run(db, "cambio", "USD", "500") == 0
    capsys.readouterr()
    assert run(db, "reporte") == 0
    salida = capsys.readouterr().out
    assert "convertidos a CRC" in salida and "11,000.00" in salida

    run(db, "listar")
    assert "USD" in capsys.readouterr().out
    run(db, "cambio")
    assert "1 USD = 500 CRC" in capsys.readouterr().out


def test_moneda_invalida_es_error_de_argparse(db):
    with pytest.raises(SystemExit):
        run(db, "gasto", "5", "x", "-M", "JPY")


def test_cambio_errores(db, capsys):
    assert run(db, "cambio") == 0
    assert "No hay tipos de cambio" in capsys.readouterr().out
    assert run(db, "cambio", "USD") == 1
    assert run(db, "cambio", "USD", "abc") == 1


def test_metas_cli(db, capsys, hoy):
    assert run(db, "meta") == 0
    assert "No hay metas" in capsys.readouterr().out
    assert run(db, "meta", "crear", "Viaje", "120000", "-f", "2026-12-31") == 0
    assert run(db, "meta", "crear", "fondo", "50000") == 0
    assert run(db, "meta", "crear", "listo", "100") == 0
    assert run(db, "meta", "crear", "vieja", "100", "-f", "2026-01-01") == 0
    assert run(db, "meta", "aportar", "viaje", "30000") == 0
    assert run(db, "meta", "aportar", "listo", "100") == 0
    assert run(db, "meta", "retirar", "viaje", "6000") == 0
    capsys.readouterr()
    assert run(db, "meta") == 0
    salida = capsys.readouterr().out
    assert "20.0%" in salida and "ahorra 32,000.00/mes" in salida  # 96,000 / 3 meses
    assert "faltan 50,000.00" in salida and "COMPLETADA" in salida and "VENCIDA" in salida
    assert run(db, "meta", "retirar", "viaje", "999999") == 1
    assert run(db, "meta", "eliminar", "viaje") == 0
    assert run(db, "meta", "eliminar", "viaje") == 1


def test_analisis(db, capsys, hoy):
    for mes in ("07", "08", "09"):
        run(db, "gasto", "100", "comida", "-f", f"2026-{mes}-05")
    run(db, "gasto", "50", "ocio", "-f", "2026-09-10")
    run(db, "gasto", "500", "comida", "-f", "2026-10-02")
    run(db, "presupuesto", "comida", "600")
    capsys.readouterr()

    assert run(db, "analisis") == 0
    salida = capsys.readouterr().out
    assert "Comparado con 2026-09" in salida
    assert "▲ 400.0%" in salida and "▼ 100.0%" in salida
    assert "día 15 de 31" in salida and "1,033.33" in salida
    assert "comida: a este ritmo llegarás a 1,033.33" in salida
    assert "Gastos inusuales" in salida and "5.0x el promedio" in salida

    assert run(db, "analisis", "-m", "2026-09") == 0
    salida = capsys.readouterr().out
    assert "Proyección" not in salida and "nuevo" in salida
    assert run(db, "analisis", "-m", "2025-01") == 0
    assert "No hay gastos" in capsys.readouterr().out


def test_grafico(db, tmp_path, capsys):
    pytest.importorskip("matplotlib")
    assert run(db, "grafico", str(tmp_path / "vacio.png")) == 1
    run(db, "importar", str(EJEMPLO))
    destino = tmp_path / "reporte.png"
    assert run(db, "grafico", str(destino)) == 0
    assert destino.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert run(db, "grafico", str(tmp_path / "sep.png"), "-m", "2026-09") == 0


def test_grafico_sin_matplotlib(db, monkeypatch, capsys):
    import builtins

    original = builtins.__import__

    def falso(nombre, *args, **kwargs):
        if nombre.startswith("matplotlib"):
            raise ImportError(nombre)
        return original(nombre, *args, **kwargs)

    run(db, "gasto", "5", "x", "-f", "2026-10-01")
    monkeypatch.setattr(builtins, "__import__", falso)
    assert run(db, "grafico", "x.png") == 1
    assert "finanzas-cli[graficos]" in capsys.readouterr().err
