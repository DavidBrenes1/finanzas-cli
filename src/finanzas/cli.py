"""Interfaz de línea de comandos."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

from . import __version__
from .analisis import comparar_meses, gastos_inusuales, proyectar, proyectar_por_categoria
from .metas import estado_metas
from .models import (
    MONEDA_BASE,
    MONEDAS,
    ErrorValidacion,
    Meta,
    Tipo,
    Transaccion,
    a_centavos,
    formatear,
)
from .monedas import convertir, parsear_tasa
from .reports import (
    balance_mensual,
    barra,
    estado_presupuestos,
    gastos_por_categoria,
    resumen,
)
from .storage import Repositorio

RUTA_POR_DEFECTO = Path.home() / ".finanzas.db"


def _hoy() -> date:
    """Fecha actual. Está en una función para que las pruebas puedan fijarla."""
    return date.today()


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
    return inicio, sig - timedelta(days=1)


def _mes_actual() -> tuple[date, date]:
    return _mes(_hoy().strftime("%Y-%m"))


def _mes_anterior(inicio: date) -> tuple[date, date]:
    return _mes((inicio - timedelta(days=1)).strftime("%Y-%m"))


def _moneda(texto: str) -> str:
    codigo = texto.strip().upper()
    if codigo not in MONEDAS:
        raise argparse.ArgumentTypeError(f"moneda inválida '{texto}', use {', '.join(MONEDAS)}")
    return codigo


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
        s.add_argument("-f", "--fecha", type=_fecha, help="AAAA-MM-DD (por defecto: hoy)")
        s.add_argument(
            "-M",
            "--moneda",
            type=_moneda,
            default=MONEDA_BASE,
            help=f"{', '.join(MONEDAS)} (por defecto: {MONEDA_BASE})",
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

    s = sub.add_parser("cambio", help="fijar o ver tipos de cambio a colones")
    s.add_argument("moneda", nargs="?", type=_moneda)
    s.add_argument("tasa", nargs="?", help="colones por 1 unidad, p. ej. 505.50")

    s = sub.add_parser("meta", help="metas de ahorro")
    acciones = s.add_subparsers(dest="accion")
    m = acciones.add_parser("crear", help="crear una meta")
    m.add_argument("nombre")
    m.add_argument("objetivo", help="monto a ahorrar")
    m.add_argument("-f", "--fecha", type=_fecha, help="fecha límite AAAA-MM-DD")
    for accion in ("aportar", "retirar"):
        m = acciones.add_parser(accion, help=f"{accion} dinero de una meta")
        m.add_argument("nombre")
        m.add_argument("monto")
    m = acciones.add_parser("eliminar", help="eliminar una meta")
    m.add_argument("nombre")

    s = sub.add_parser("analisis", help="comparación con el mes anterior, proyección e inusuales")
    s.add_argument("-m", "--mes", type=_mes, help="AAAA-MM (por defecto: actual)")

    s = sub.add_parser("grafico", help="exportar el reporte como imagen PNG")
    s.add_argument("archivo", type=Path)
    s.add_argument("-m", "--mes", type=_mes, help="AAAA-MM")

    s = sub.add_parser("importar", help="importar transacciones desde CSV")
    s.add_argument("archivo", type=Path)

    s = sub.add_parser("exportar", help="exportar transacciones a CSV")
    s.add_argument("archivo", type=Path)
    return p


def _en_base(repo: Repositorio, filas: list[Transaccion]) -> list[Transaccion]:
    """Convierte transacciones a colones con los tipos de cambio guardados."""
    return convertir(filas, repo.tipos_cambio())


def _cmd_registrar(repo: Repositorio, a: argparse.Namespace) -> None:
    t = Transaccion(
        a.tipo, a_centavos(a.monto), a.categoria, a.fecha or _hoy(), a.descripcion, a.moneda
    )
    id_ = repo.agregar(t)
    etiqueta = a.tipo.value.capitalize()
    print(f"✔ {etiqueta} #{id_} registrado: {formatear(t.centavos)} {t.moneda} en '{t.categoria}'")


def _cmd_listar(repo: Repositorio, a: argparse.Namespace) -> None:
    desde, hasta = a.mes or (None, None)
    filas = repo.listar(desde, hasta, a.categoria)
    if not filas:
        print("No hay transacciones.")
        return
    print(f"{'ID':>4}  {'FECHA':<10}  {'CATEGORÍA':<14}  {'MONTO':>12}  MON  DESCRIPCIÓN")
    for t in filas:
        print(
            f"{t.id:>4}  {t.fecha}  {t.categoria:<14}  "
            f"{formatear(t.monto_con_signo):>12}  {t.moneda}  {t.descripcion}"
        )


def _cmd_eliminar(repo: Repositorio, a: argparse.Namespace) -> None:
    if not repo.eliminar(a.id):
        raise ErrorValidacion(f"No existe la transacción #{a.id}")
    print(f"✔ Transacción #{a.id} eliminada")


def _cmd_reporte(repo: Repositorio, a: argparse.Namespace) -> None:
    desde, hasta = a.mes or (None, None)
    originales = repo.listar(desde, hasta)
    filas = _en_base(repo, originales)
    if any(t.moneda != MONEDA_BASE for t in originales):
        print(f"(montos convertidos a {MONEDA_BASE})")
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
        print(f"✔ Presupuesto de '{a.categoria.lower()}': {a.monto} {MONEDA_BASE}")
        return
    if a.categoria:
        raise ErrorValidacion("Indique categoría y monto, o ninguno para ver el estado")
    presupuestos = repo.presupuestos()
    if not presupuestos:
        print("No hay presupuestos. Ejemplo: finanzas presupuesto comida 150000")
        return
    desde, hasta = a.mes or _mes_actual()
    print(f"Presupuestos {desde:%Y-%m}")
    for e in estado_presupuestos(_en_base(repo, repo.listar(desde, hasta)), presupuestos):
        alerta = "  ⚠ EXCEDIDO" if e.excedido else ""
        print(
            f"  {e.categoria:<14} {barra(e.gastado, e.limite)} "
            f"{e.porcentaje:>5}%  quedan {formatear(e.restante)}{alerta}"
        )


def _cmd_cambio(repo: Repositorio, a: argparse.Namespace) -> None:
    if a.moneda and a.tasa:
        tasa = parsear_tasa(a.tasa)
        repo.fijar_tipo_cambio(a.moneda, tasa)
        print(f"✔ 1 {a.moneda} = {tasa} {MONEDA_BASE}")
        return
    if a.moneda:
        raise ErrorValidacion("Indique moneda y tasa, o ninguna para ver los tipos de cambio")
    tasas = repo.tipos_cambio()
    if not tasas:
        print("No hay tipos de cambio. Ejemplo: finanzas cambio USD 505.50")
        return
    for moneda, tasa in tasas.items():
        print(f"  1 {moneda} = {tasa} {MONEDA_BASE}")


def _cmd_meta(repo: Repositorio, a: argparse.Namespace) -> None:
    if a.accion == "crear":
        meta = Meta(a.nombre, a_centavos(a.objetivo), fecha_limite=a.fecha)
        repo.crear_meta(meta)
        limite = f" para el {a.fecha}" if a.fecha else ""
        print(f"✔ Meta '{meta.nombre.lower()}' creada: {formatear(meta.objetivo)}{limite}")
        return
    if a.accion in ("aportar", "retirar"):
        centavos = a_centavos(a.monto)
        meta = repo.mover_a_meta(a.nombre, centavos if a.accion == "aportar" else -centavos)
        print(f"✔ '{meta.nombre}': {formatear(meta.ahorrado)} de {formatear(meta.objetivo)}")
        return
    if a.accion == "eliminar":
        if not repo.eliminar_meta(a.nombre):
            raise ErrorValidacion(f"No existe la meta '{a.nombre}'")
        print(f"✔ Meta '{a.nombre}' eliminada")
        return

    metas = repo.metas()
    if not metas:
        print("No hay metas. Ejemplo: finanzas meta crear viaje 500000 -f 2027-06-30")
        return
    print("Metas de ahorro")
    for e in estado_metas(metas, _hoy()):
        if e.completada:
            detalle = "✔ COMPLETADA"
        elif e.vencida:
            detalle = f"⚠ VENCIDA, faltan {formatear(e.restante)}"
        elif e.mensual_necesario is not None:
            detalle = f"ahorra {formatear(e.mensual_necesario)}/mes hasta {e.meta.fecha_limite}"
        else:
            detalle = f"faltan {formatear(e.restante)}"
        print(
            f"  {e.meta.nombre:<14} {barra(e.meta.ahorrado, e.meta.objetivo)} "
            f"{e.porcentaje:>5}%  {formatear(e.meta.ahorrado)} / {formatear(e.meta.objetivo)}"
            f"  {detalle}"
        )


def _flecha(porcentaje: float | None) -> str:
    if porcentaje is None:
        return "nuevo"
    simbolo = "▲" if porcentaje > 0 else "▼" if porcentaje < 0 else "="
    return f"{simbolo} {abs(porcentaje)}%"


def _cmd_analisis(repo: Repositorio, a: argparse.Namespace) -> None:
    inicio, fin = a.mes or _mes_actual()
    ant_inicio, ant_fin = _mes_anterior(inicio)
    hoy = _hoy()
    actual = _en_base(repo, repo.listar(inicio, fin, tipo=Tipo.GASTO))
    anterior = _en_base(repo, repo.listar(ant_inicio, ant_fin, tipo=Tipo.GASTO))
    if not actual and not anterior:
        print(f"No hay gastos en {inicio:%Y-%m} ni en {ant_inicio:%Y-%m}.")
        return

    print(f"Análisis {inicio:%Y-%m}")
    print(f"\nComparado con {ant_inicio:%Y-%m}")
    for v in comparar_meses(actual, anterior):
        print(
            f"  {v.categoria:<14} {formatear(v.actual):>12}  vs {formatear(v.anterior):>12}"
            f"   {_flecha(v.porcentaje)}"
        )
    total_actual = sum(t.centavos for t in actual)
    total_anterior = sum(t.centavos for t in anterior)
    print(f"  {'TOTAL':<14} {formatear(total_actual):>12}  vs {formatear(total_anterior):>12}")

    if inicio <= hoy < fin:
        dia = (hoy - inicio).days + 1
        print(f"\nProyección al cierre del mes (día {dia} de {fin.day})")
        print(f"  Gasto proyectado: {formatear(proyectar(total_actual, hoy, inicio, fin))}")
        presupuestos = repo.presupuestos()
        for cat, proyectado in proyectar_por_categoria(actual, hoy, inicio, fin).items():
            limite = presupuestos.get(cat)
            if limite and proyectado > limite:
                print(
                    f"  ⚠ {cat}: a este ritmo llegarás a {formatear(proyectado)}"
                    f" (presupuesto {formatear(limite)})"
                )

    historial = _en_base(repo, repo.listar(hasta=inicio - timedelta(days=1), tipo=Tipo.GASTO))
    inusuales = gastos_inusuales(actual, historial)
    if inusuales:
        print("\nGastos inusuales")
        for g in inusuales:
            t = g.transaccion
            print(
                f"  #{t.id} {t.fecha} {t.categoria:<14} {formatear(t.centavos):>12}"
                f"  ({g.veces}x el promedio de {formatear(g.promedio)})"
            )


def _cmd_grafico(repo: Repositorio, a: argparse.Namespace) -> None:
    from .graficos import exportar_png  # importación tardía: matplotlib es opcional

    desde, hasta = a.mes or (None, None)
    filas = _en_base(repo, repo.listar(desde, hasta))
    titulo = f"Finanzas {desde:%Y-%m}" if desde else "Finanzas: todo el historial"
    meses = balance_mensual(filas)
    ruta = exportar_png(
        a.archivo, gastos_por_categoria(filas), meses if len(meses) > 1 else [], titulo
    )
    print(f"✔ Gráfico guardado en {ruta}")


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
    "cambio": _cmd_cambio,
    "meta": _cmd_meta,
    "analisis": _cmd_analisis,
    "grafico": _cmd_grafico,
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
