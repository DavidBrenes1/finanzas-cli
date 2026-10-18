"""Capa de persistencia sobre SQLite (patrón Repository)."""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from .models import ErrorValidacion, Tipo, Transaccion, a_centavos

ESQUEMA = """
CREATE TABLE IF NOT EXISTS transacciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT    NOT NULL CHECK (tipo IN ('ingreso', 'gasto')),
    centavos    INTEGER NOT NULL CHECK (centavos > 0),
    categoria   TEXT    NOT NULL,
    fecha       TEXT    NOT NULL,
    descripcion TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_fecha ON transacciones (fecha);
CREATE TABLE IF NOT EXISTS presupuestos (
    categoria TEXT PRIMARY KEY,
    centavos  INTEGER NOT NULL CHECK (centavos > 0)
);
"""

COLUMNAS_CSV = ["fecha", "tipo", "monto", "categoria", "descripcion"]


class Repositorio:
    """Acceso a datos de transacciones y presupuestos."""

    def __init__(self, ruta: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(ruta))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(ESQUEMA)

    def cerrar(self) -> None:
        self._conn.close()

    def __enter__(self) -> Repositorio:
        return self

    def __exit__(self, *_: object) -> None:
        self.cerrar()

    @contextmanager
    def _transaccion(self) -> Iterator[sqlite3.Connection]:
        with self._conn:  # commit automático o rollback si hay excepción
            yield self._conn

    # --- Transacciones -------------------------------------------------
    def agregar(self, t: Transaccion) -> int:
        with self._transaccion() as c:
            cur = c.execute(
                "INSERT INTO transacciones (tipo, centavos, categoria, fecha, descripcion)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    t.tipo.value,
                    t.centavos,
                    t.categoria.strip().lower(),
                    t.fecha.isoformat(),
                    t.descripcion,
                ),
            )
            return int(cur.lastrowid)

    def eliminar(self, id_: int) -> bool:
        with self._transaccion() as c:
            return c.execute("DELETE FROM transacciones WHERE id = ?", (id_,)).rowcount > 0

    def listar(
        self,
        desde: date | None = None,
        hasta: date | None = None,
        categoria: str | None = None,
        tipo: Tipo | None = None,
    ) -> list[Transaccion]:
        sql = "SELECT * FROM transacciones WHERE 1=1"
        params: list[object] = []
        if desde:
            sql += " AND fecha >= ?"
            params.append(desde.isoformat())
        if hasta:
            sql += " AND fecha <= ?"
            params.append(hasta.isoformat())
        if categoria:
            sql += " AND categoria = ?"
            params.append(categoria.strip().lower())
        if tipo:
            sql += " AND tipo = ?"
            params.append(tipo.value)
        sql += " ORDER BY fecha, id"
        return [self._a_modelo(f) for f in self._conn.execute(sql, params)]

    @staticmethod
    def _a_modelo(fila: sqlite3.Row) -> Transaccion:
        return Transaccion(
            id=fila["id"],
            tipo=Tipo(fila["tipo"]),
            centavos=fila["centavos"],
            categoria=fila["categoria"],
            fecha=date.fromisoformat(fila["fecha"]),
            descripcion=fila["descripcion"],
        )

    # --- Presupuestos --------------------------------------------------
    def fijar_presupuesto(self, categoria: str, centavos: int) -> None:
        with self._transaccion() as c:
            c.execute(
                "INSERT INTO presupuestos (categoria, centavos) VALUES (?, ?)"
                " ON CONFLICT(categoria) DO UPDATE SET centavos = excluded.centavos",
                (categoria.strip().lower(), centavos),
            )

    def presupuestos(self) -> dict[str, int]:
        filas = self._conn.execute("SELECT categoria, centavos FROM presupuestos")
        return {f["categoria"]: f["centavos"] for f in filas}

    # --- CSV -----------------------------------------------------------
    def importar_csv(self, ruta: str | Path) -> int:
        """Importa transacciones desde CSV. Es atómico: si una fila falla, no se guarda ninguna."""
        with open(ruta, newline="", encoding="utf-8") as f:
            lector = csv.DictReader(f)
            faltantes = set(COLUMNAS_CSV) - set(lector.fieldnames or [])
            if faltantes:
                raise ErrorValidacion(f"Faltan columnas en el CSV: {sorted(faltantes)}")
            transacciones = [self._fila_csv(n, fila) for n, fila in enumerate(lector, start=2)]
        self._agregar_varias(transacciones)
        return len(transacciones)

    @staticmethod
    def _fila_csv(numero: int, fila: dict[str, str]) -> Transaccion:
        try:
            return Transaccion(
                tipo=Tipo(fila["tipo"].strip().lower()),
                centavos=a_centavos(fila["monto"]),
                categoria=fila["categoria"],
                fecha=date.fromisoformat(fila["fecha"].strip()),
                descripcion=(fila.get("descripcion") or "").strip(),
            )
        except (ValueError, KeyError) as exc:
            raise ErrorValidacion(f"Línea {numero} del CSV: {exc}") from exc

    def _agregar_varias(self, transacciones: Iterable[Transaccion]) -> None:
        with self._transaccion() as c:
            c.executemany(
                "INSERT INTO transacciones (tipo, centavos, categoria, fecha, descripcion)"
                " VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        t.tipo.value,
                        t.centavos,
                        t.categoria.strip().lower(),
                        t.fecha.isoformat(),
                        t.descripcion,
                    )
                    for t in transacciones
                ],
            )

    def exportar_csv(self, ruta: str | Path) -> int:
        transacciones = self.listar()
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            escritor = csv.writer(f)
            escritor.writerow(COLUMNAS_CSV)
            for t in transacciones:
                escritor.writerow(
                    [
                        t.fecha.isoformat(),
                        t.tipo.value,
                        f"{t.centavos / 100:.2f}",
                        t.categoria,
                        t.descripcion,
                    ]
                )
        return len(transacciones)
