from datetime import date

import pytest

from finanzas.models import ErrorValidacion, Tipo, Transaccion


def test_agregar_y_listar(repo, muestra):
    ids = [repo.agregar(t) for t in muestra]
    assert ids == [1, 2, 3, 4, 5]
    filas = repo.listar()
    assert len(filas) == 5
    assert [f.fecha for f in filas] == sorted(f.fecha for f in filas)


def test_normaliza_categoria(repo):
    repo.agregar(Transaccion(Tipo.GASTO, 100, "  Comida ", date(2026, 1, 1)))
    assert repo.listar()[0].categoria == "comida"
    assert len(repo.listar(categoria="COMIDA")) == 1


def test_filtros(repo, muestra):
    for t in muestra:
        repo.agregar(t)
    assert len(repo.listar(desde=date(2026, 10, 1))) == 2
    assert len(repo.listar(hasta=date(2026, 9, 30))) == 3
    assert len(repo.listar(tipo=Tipo.INGRESO)) == 2
    assert len(repo.listar(categoria="comida", desde=date(2026, 10, 1))) == 1


def test_eliminar(repo, muestra):
    id_ = repo.agregar(muestra[0])
    assert repo.eliminar(id_) is True
    assert repo.eliminar(id_) is False
    assert repo.listar() == []


def test_presupuesto_upsert(repo):
    repo.fijar_presupuesto("Comida", 1000)
    repo.fijar_presupuesto("comida", 2000)
    assert repo.presupuestos() == {"comida": 2000}


def test_csv_ida_y_vuelta(repo, muestra, tmp_path):
    for t in muestra:
        repo.agregar(t)
    archivo = tmp_path / "datos.csv"
    assert repo.exportar_csv(archivo) == 5

    from finanzas.storage import Repositorio

    with Repositorio(":memory:") as otro:
        assert otro.importar_csv(archivo) == 5
        quitar_id = [(t.tipo, t.centavos, t.categoria, t.fecha) for t in otro.listar()]
        original = [(t.tipo, t.centavos, t.categoria, t.fecha) for t in repo.listar()]
        assert quitar_id == original


def test_importar_es_atomico(repo, tmp_path):
    archivo = tmp_path / "malo.csv"
    archivo.write_text(
        "fecha,tipo,monto,categoria,descripcion\n"
        "2026-01-01,gasto,100,comida,ok\n"
        "2026-13-01,gasto,100,comida,fecha mala\n",
        encoding="utf-8",
    )
    with pytest.raises(ErrorValidacion, match="Línea 3"):
        repo.importar_csv(archivo)
    assert repo.listar() == []


def test_importar_columnas_faltantes(repo, tmp_path):
    archivo = tmp_path / "x.csv"
    archivo.write_text("fecha,monto\n2026-01-01,5\n", encoding="utf-8")
    with pytest.raises(ErrorValidacion, match="Faltan columnas"):
        repo.importar_csv(archivo)


def test_persistencia_en_disco(tmp_path, muestra):
    from finanzas.storage import Repositorio

    ruta = tmp_path / "f.db"
    with Repositorio(ruta) as r:
        r.agregar(muestra[0])
    with Repositorio(ruta) as r:
        assert len(r.listar()) == 1
