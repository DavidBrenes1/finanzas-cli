import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from finanzas.models import ErrorValidacion, Tipo, Transaccion, validar_moneda
from finanzas.monedas import a_base, convertir, parsear_tasa
from finanzas.storage import Repositorio

TASAS = {"USD": Decimal("505.50"), "EUR": Decimal("590")}


def test_a_base_redondea():
    assert a_base(1, "USD", {"USD": Decimal("0.004")}) == 1  # nunca baja a cero
    assert a_base(333, "EUR", TASAS) == 196470
    assert a_base(101, "USD", {"USD": Decimal("1.005")}) == 102  # 101.505 -> 102


def test_a_base_sin_tasa():
    with pytest.raises(ErrorValidacion, match="Falta el tipo de cambio de USD"):
        a_base(100, "USD", {})


def test_convertir_no_modifica_originales():
    t = Transaccion(Tipo.GASTO, 1000, "comida", date(2026, 10, 1), moneda="USD")
    (c,) = convertir([t], TASAS)
    assert (c.centavos, c.moneda) == (505500, "CRC")
    assert (t.centavos, t.moneda) == (1000, "USD")


@pytest.mark.parametrize("texto", ["0", "-1", "abc", "nan"])
def test_parsear_tasa_invalida(texto):
    with pytest.raises(ErrorValidacion):
        parsear_tasa(texto)


def test_validar_moneda():
    assert validar_moneda("eur") == "EUR"
    with pytest.raises(ErrorValidacion):
        validar_moneda("JPY")
    with pytest.raises(ErrorValidacion):
        Transaccion(Tipo.GASTO, 1, "x", date.today(), moneda="JPY")


def test_tipos_cambio_en_repositorio(repo):
    repo.fijar_tipo_cambio("usd", Decimal("500"))
    repo.fijar_tipo_cambio("USD", Decimal("505.50"))
    assert repo.tipos_cambio() == {"USD": Decimal("505.50")}
    with pytest.raises(ErrorValidacion, match="moneda base"):
        repo.fijar_tipo_cambio("CRC", Decimal("1"))


def test_guarda_moneda(repo):
    repo.agregar(Transaccion(Tipo.GASTO, 1999, "ocio", date(2026, 10, 1), moneda="EUR"))
    assert repo.listar()[0].moneda == "EUR"


def test_migra_base_de_datos_v1(tmp_path):
    ruta = tmp_path / "v1.db"
    conn = sqlite3.connect(ruta)
    conn.executescript(
        "CREATE TABLE transacciones (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL,"
        " centavos INTEGER NOT NULL, categoria TEXT NOT NULL, fecha TEXT NOT NULL,"
        " descripcion TEXT NOT NULL DEFAULT '');"
        "INSERT INTO transacciones (tipo, centavos, categoria, fecha)"
        " VALUES ('gasto', 500, 'comida', '2026-01-01');"
    )
    conn.commit()
    conn.close()
    with Repositorio(ruta) as r:
        (t,) = r.listar()
        assert t.moneda == "CRC"
        r.agregar(Transaccion(Tipo.GASTO, 100, "x", date(2026, 1, 2), moneda="USD"))
        assert [x.moneda for x in r.listar()] == ["CRC", "USD"]


def test_csv_con_y_sin_moneda(repo, tmp_path):
    archivo = tmp_path / "m.csv"
    archivo.write_text(
        "fecha,tipo,monto,categoria,descripcion,moneda\n"
        "2026-01-01,gasto,10,comida,,usd\n"
        "2026-01-02,gasto,10,comida,,\n",
        encoding="utf-8",
    )
    assert repo.importar_csv(archivo) == 2
    assert [t.moneda for t in repo.listar()] == ["USD", "CRC"]
    salida = tmp_path / "out.csv"
    repo.exportar_csv(salida)
    assert salida.read_text(encoding="utf-8").splitlines()[0].endswith(",moneda")


def test_csv_moneda_invalida(repo, tmp_path):
    archivo = tmp_path / "m.csv"
    archivo.write_text(
        "fecha,tipo,monto,categoria,descripcion,moneda\n2026-01-01,gasto,10,x,,JPY\n",
        encoding="utf-8",
    )
    with pytest.raises(ErrorValidacion, match="Línea 2"):
        repo.importar_csv(archivo)
