"""Capa de persistencia sobre SQLite (patrón Repository)."""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path

from .models import (
    MONEDA_BASE,
    ErrorValidacion,
    Meta,
    Tipo,
    Transaccion,
    a_centavos,
    validar_moneda,
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS transacciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT    NOT NULL CHECK (tipo IN ('ingreso', 'gasto')),
    centavos    INTEGER NOT NULL CHECK (centavos > 0),
    categoria   TEXT    NOT NULL,
    fecha       TEXT    NOT NULL,
    descripcion TEXT    NOT NULL DEFAULT '',
    moneda      TEXT    NOT NULL DEFAULT 'CRC'
);
CREATE INDEX IF NOT EXISTS idx_fecha ON transacciones (fecha);
CREATE TABLE IF NOT EXISTS presupuestos (
    categoria TEXT PRIMARY KEY,
    centavos  INTEGER NOT NULL CHECK (centavos > 0)
);
CREATE TABLE IF NOT EXISTS tipos_cambio (
    moneda TEXT PRIMARY KEY,
    tasa   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT    NOT NULL UNIQUE,
    objetivo     INTEGER NOT NULL CHECK (objetivo > 0),
    ahorrado     INTEGER NOT NULL DEFAULT 0 CHECK (ahorrado >= 0),
    fecha_limite TEXT
);
"""

COLUMNAS_CSV = ["fecha", "tipo", "monto", "categoria", "descripcion"]
"""Columnas obligatorias del CSV. ``moneda`` es opcional (por defecto CRC)."""

_INSERT_TRANSACCION = (
    "INSERT INTO transacciones (tipo, centavos, categoria, fecha, descripcion, moneda)"
    " VALUES (?, ?, ?, ?, ?, ?)"
)


def _fila_insert(t: Transaccion) -> tuple[object, ...]:
    return (
        t.tipo.value,
        t.centavos,
        t.categoria.strip().lower(),
        t.fecha.isoformat(),
        t.descripcion,
        t.moneda,
    )


class Repositorio:
    """Acceso a datos de transacciones, presupuestos, tipos de cambio y metas."""

    def __init__(self, ruta: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(ruta))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(ESQUEMA)
        self._migrar()

    def _migrar(self) -> None:
        """Actualiza bases de datos creadas con la versión 1.0 (sin columna ``moneda``)."""
        columnas = {f["name"] for f in self._conn.execute("PRAGMA table_info(transacciones)")}
        if "moneda" not in columnas:
            with self._transaccion() as c:
                c.execute("ALTER TABLE transacciones ADD COLUMN moneda TEXT NOT NULL DEFAULT 'CRC'")

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
            return int(c.execute(_INSERT_TRANSACCION, _fila_insert(t)).lastrowid)

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
            moneda=fila["moneda"],
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

    # --- Tipos de cambio -----------------------------------------------
    def fijar_tipo_cambio(self, moneda: str, tasa: Decimal) -> None:
        moneda = validar_moneda(moneda)
        if moneda == MONEDA_BASE:
            raise ErrorValidacion(f"{MONEDA_BASE} es la moneda base; no necesita tipo de cambio")
        with self._transaccion() as c:
            c.execute(
                "INSERT INTO tipos_cambio (moneda, tasa) VALUES (?, ?)"
                " ON CONFLICT(moneda) DO UPDATE SET tasa = excluded.tasa",
                (moneda, str(tasa)),
            )

    def tipos_cambio(self) -> dict[str, Decimal]:
        filas = self._conn.execute("SELECT moneda, tasa FROM tipos_cambio ORDER BY moneda")
        return {f["moneda"]: Decimal(f["tasa"]) for f in filas}

    # --- Metas de ahorro -----------------------------------------------
    def crear_meta(self, meta: Meta) -> int:
        try:
            with self._transaccion() as c:
                cur = c.execute(
                    "INSERT INTO metas (nombre, objetivo, ahorrado, fecha_limite)"
                    " VALUES (?, ?, ?, ?)",
                    (
                        meta.nombre.strip().lower(),
                        meta.objetivo,
                        meta.ahorrado,
                        meta.fecha_limite.isoformat() if meta.fecha_limite else None,
                    ),
                )
                return int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ErrorValidacion(f"Ya existe una meta llamada '{meta.nombre}'") from exc

    def obtener_meta(self, nombre: str) -> Meta:
        fila = self._conn.execute(
            "SELECT * FROM metas WHERE nombre = ?", (nombre.strip().lower(),)
        ).fetchone()
        if fila is None:
            raise ErrorValidacion(f"No existe la meta '{nombre}'")
        return self._a_meta(fila)

    def mover_a_meta(self, nombre: str, centavos: int) -> Meta:
        """Suma (``centavos`` > 0) o resta (< 0) dinero ahorrado en una meta."""
        meta = self.obtener_meta(nombre)
        if meta.ahorrado + centavos < 0:
            raise ErrorValidacion(f"No puede retirar más de lo ahorrado en '{meta.nombre}'")
        with self._transaccion() as c:
            c.execute("UPDATE metas SET ahorrado = ahorrado + ? WHERE id = ?", (centavos, meta.id))
        return self.obtener_meta(nombre)

    def metas(self) -> list[Meta]:
        return [self._a_meta(f) for f in self._conn.execute("SELECT * FROM metas ORDER BY id")]

    def eliminar_meta(self, nombre: str) -> bool:
        with self._transaccion() as c:
            cur = c.execute("DELETE FROM metas WHERE nombre = ?", (nombre.strip().lower(),))
            return cur.rowcount > 0

    @staticmethod
    def _a_meta(fila: sqlite3.Row) -> Meta:
        limite = fila["fecha_limite"]
        return Meta(
            id=fila["id"],
            nombre=fila["nombre"],
            objetivo=fila["objetivo"],
            ahorrado=fila["ahorrado"],
            fecha_limite=date.fromisoformat(limite) if limite else None,
        )

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
                moneda=validar_moneda(fila.get("moneda") or MONEDA_BASE),
            )
        except (ValueError, KeyError) as exc:
            raise ErrorValidacion(f"Línea {numero} del CSV: {exc}") from exc

    def _agregar_varias(self, transacciones: Iterable[Transaccion]) -> None:
        with self._transaccion() as c:
            c.executemany(_INSERT_TRANSACCION, [_fila_insert(t) for t in transacciones])

    def exportar_csv(self, ruta: str | Path) -> int:
        transacciones = self.listar()
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            escritor = csv.writer(f)
            escritor.writerow([*COLUMNAS_CSV, "moneda"])
            for t in transacciones:
                escritor.writerow(
                    [
                        t.fecha.isoformat(),
                        t.tipo.value,
                        f"{Decimal(t.centavos) / 100:.2f}",
                        t.categoria,
                        t.descripcion,
                        t.moneda,
                    ]
                )
        return len(transacciones)
