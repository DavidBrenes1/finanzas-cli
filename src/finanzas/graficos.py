"""Exportación de reportes a imagen PNG con matplotlib (dependencia opcional).

Instalación: ``pip install "finanzas-cli[graficos]"``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .models import ErrorValidacion

# Paleta validada para daltonismo sobre fondo claro.
SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
CUADRICULA = "#e4e3df"
AZUL = "#2a78d6"  # gastos y balances positivos
ROJO = "#e34948"  # balances negativos


def _importar_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")  # sin ventana: solo genera archivos
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ErrorValidacion(
            'Para exportar gráficos instale matplotlib: pip install "finanzas-cli[graficos]"'
        ) from exc
    return plt


def _miles(centavos: int) -> str:
    return f"{centavos / 100:,.0f}"


def _estilo(ax, titulo: str) -> None:
    ax.set_title(titulo, loc="left", fontsize=12, color=TEXTO, fontweight="bold", pad=12)
    ax.set_facecolor(SUPERFICIE)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(CUADRICULA)
    ax.tick_params(colors=TEXTO_SECUNDARIO, length=0, labelsize=9)


def exportar_png(
    ruta: str | Path,
    categorias: Sequence[tuple[str, int]],
    meses: Sequence[tuple[str, int]],
    titulo: str,
) -> Path:
    """Genera un PNG con gastos por categoría y balance mensual (montos en CRC)."""
    if not categorias and not meses:
        raise ErrorValidacion("No hay datos para graficar")
    plt = _importar_matplotlib()

    paneles = [p for p in (categorias, meses) if p]
    fig, ejes = plt.subplots(
        len(paneles), 1, figsize=(8, 3.2 * len(paneles) + 0.6), facecolor=SUPERFICIE, squeeze=False
    )
    fig.suptitle(titulo, x=0.02, ha="left", fontsize=14, color=TEXTO, fontweight="bold")
    ejes_iter = iter(ejes[:, 0])

    if categorias:
        ax = next(ejes_iter)
        nombres = [c for c, _ in categorias][::-1]
        valores = [v / 100 for _, v in categorias][::-1]
        barras = ax.barh(nombres, valores, color=AZUL, height=0.6)
        ax.bar_label(
            barras,
            labels=[_miles(v) for _, v in categorias][::-1],
            padding=4,
            fontsize=9,
            color=TEXTO_SECUNDARIO,
        )
        ax.xaxis.set_visible(False)
        ax.margins(x=0.15)
        _estilo(ax, "Gastos por categoría (CRC)")
        ax.spines["bottom"].set_visible(False)

    if meses:
        ax = next(ejes_iter)
        etiquetas = [m for m, _ in meses]
        valores = [v / 100 for _, v in meses]
        colores = [AZUL if v >= 0 else ROJO for v in valores]
        barras = ax.bar(etiquetas, valores, color=colores, width=0.6)
        ax.bar_label(
            barras,
            labels=[_miles(v) for _, v in meses],
            padding=3,
            fontsize=9,
            color=TEXTO_SECUNDARIO,
        )
        ax.axhline(0, color=TEXTO_SECUNDARIO, linewidth=0.8)
        ax.yaxis.set_visible(False)
        ax.margins(y=0.2)
        _estilo(ax, "Balance mensual (CRC)")

    fig.tight_layout()
    ruta = Path(ruta)
    fig.savefig(ruta, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)
    return ruta
