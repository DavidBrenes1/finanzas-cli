"""Interfaz de línea de comandos."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from . import __version__
from .models import ErrorValidacion, Tipo, Transaccion, a_centavos, formatear
from .reports import (
    balance_mensual,
    barra,
    estado_presupuestos,
    gastos_por_categoria,
    resumen,
)
from .storage import Repositorio

RUTA_POR_DEFECTO = Path.home() / ".finanzas.db"


def _fecha(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"fecha inválida '{texto}', use AAAA-MM-DD") from exc


def _mes(texto: str) -> tuple[date, date]:
    """Convierte 'AAAA-MM' en el rango (primer día, último día) del mes."""
    try:
        inicio = date.fromisoformat(f"{texto}-01")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"mes inválido '{texto}', use AAAA-MM") from exc
    sig = date(inicio.year + inicio.month // 12, inicio.month % 12 + 1, 1)
    return inicio, date.fromordinal(sig.toordinal() - 1)


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="finanzas", description="Control de finanzas personales.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ.get("FINANZAS_DB", RUTA_POR_DEFECTO)),
        help="ruta de la base de datos (o variable FINANZAS_DB)",
    )
    sub = p.add_subparsers(dest="comando", required=True)

    for nombre, tipo in (("ingreso", Tipo.INGRESO), ("gasto", Tipo.GASTO)):
        s = sub.add_parser(nombre, help=f"registrar un {nombre}")
        s.add_argument("monto", help="monto, p. ej. 15000 o 12.50")
        s.add_argument("categoria")
        s.add_argument("-d", "--descripcion", default="")
        s.add_argument(
            "-f", "--fecha", type=_fecha, default=date.today(), help="AAAA-MM-DD (por defecto: hoy)"
        )
        s.set_defaults(tipo=tipo)

    s = sub.add_parser("listar", help="ver transacciones")
    s.add_argument("-m", "--mes", type=_mes, help="AAAA-MM")
    s.add_argument("-c", "--categoria")

    s = sub.add_parser("eliminar", help="borrar una transacción por id")
    s.add_argument("id", type=int)

    s = sub.add_parser("reporte", help="resumen, categorías y tendencia mensual")
    s.add_argument("-m", "--mes", type=_mes, help="AAAA-MM")

    s = sub.add_parser("presupuesto", help="fijar o ver presupuestos mensuales")
    s.add_argument("categoria", nargs="?")
    s.add_argument("monto", nargs="?")
    s.add_argument("-m", "--mes", type=_mes, help="mes a evaluar (por defecto: actual)")

    s = sub.add_parser("importar", help="importar transacciones desde CSV")
    s.add_argument("archivo", type=Path)

    s = sub.add_parser("exportar", help="exportar transacciones a CSV")
    s.add_argument("archivo", type=Path)
    return p


def _cmd_registrar(repo: Repositorio, a: argparse.Namespace) -> None:
    t = Transaccion(a.tipo, a_centavos(a.monto), a.categoria, a.fecha, a.descripcion)
    id_ = repo.agregar(t)
    etiqueta = a.tipo.value.capitalize()
    print(f"✔ {etiqueta} #{id_} registrado: {formatear(t.centavos)} en '{t.categoria}'")


def _cmd_listar(repo: Repositorio, a: argparse.Namespace) -> None:
    desde, hasta = a.mes or (None, None)
    filas = repo.listar(desde, hasta, a.categoria)
    if not filas:
        print("No hay transacciones.")
        return
    print(f"{'ID':>4}  {'FECHA':<10}  {'CATEGORÍA':<14}  {'MONTO':>12}  DESCRIPCIÓN")
    for t in filas:
        print(
            f"{t.id:>4}  {t.fecha}  {t.categoria:<14}  "
            f"{formatear(t.monto_con_signo):>12}  {t.descripcion}"
        )


def _cmd_eliminar(repo: Repositorio, a: argparse.Namespace) -> None:
    if not repo.eliminar(a.id):
        raise ErrorValidacion(f"No existe la transacción #{a.id}")
    print(f"✔ Transacción #{a.id} eliminada")


def _cmd_reporte(repo: Repositorio, a: argparse.Namespace) -> None:
    desde, hasta = a.mes or (None, None)
    filas = repo.listar(desde, hasta)
    r = resumen(filas)
    print(f"Ingresos:  {formatear(r.ingresos):>14}")
    print(f"Gastos:    {formatear(r.gastos):>14}")
    print(f"Balance:   {formatear(r.balance):>14}   (ahorro {r.tasa_ahorro}%)")

    categorias = gastos_por_categoria(filas)
    if categorias:
        print("\nGastos por categoría")
        maximo = categorias[0][1]
        for cat, total in categorias:
            print(f"  {cat:<14} {barra(total, maximo)} {formatear(total):>12}")

    meses = balance_mensual(filas)
    if len(meses) > 1:
        print("\nBalance mensual")
        for mes, total in meses:
            print(f"  {mes}  {formatear(total):>12}")


def _cmd_presupuesto(repo: Repositorio, a: argparse.Namespace) -> None:
    if a.categoria and a.monto:
        repo.fijar_presupuesto(a.categoria, a_centavos(a.monto))
        print(f"✔ Presupuesto de '{a.categoria.lower()}': {a.monto}")
        return
    if a.categoria:
        raise ErrorValidacion("Indique categoría y monto, o ninguno para ver el estado")
    presupuestos = repo.presupuestos()
    if not presupuestos:
        print("No hay presupuestos. Ejemplo: finanzas presupuesto comida 150000")
        return
    desde, hasta = a.mes or _mes(date.today().strftime("%Y-%m"))
    print(f"Presupuestos {desde:%Y-%m}")
    for e in estado_presupuestos(repo.listar(desde, hasta), presupuestos):
        alerta = "  ⚠ EXCEDIDO" if e.excedido else ""
        print(
            f"  {e.categoria:<14} {barra(e.gastado, e.limite)} "
            f"{e.porcentaje:>5}%  quedan {formatear(e.restante)}{alerta}"
        )


def _cmd_importar(repo: Repositorio, a: argparse.Namespace) -> None:
    print(f"✔ {repo.importar_csv(a.archivo)} transacciones importadas")


def _cmd_exportar(repo: Repositorio, a: argparse.Namespace) -> None:
    print(f"✔ {repo.exportar_csv(a.archivo)} transacciones exportadas a {a.archivo}")


COMANDOS = {
    "ingreso": _cmd_registrar,
    "gasto": _cmd_registrar,
    "listar": _cmd_listar,
    "eliminar": _cmd_eliminar,
    "reporte": _cmd_reporte,
    "presupuesto": _cmd_presupuesto,
    "importar": _cmd_importar,
    "exportar": _cmd_exportar,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        with Repositorio(args.db) as repo:
            COMANDOS[args.comando](repo, args)
    except (ErrorValidacion, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
