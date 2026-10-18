# 💰 finanzas-cli

![CI](https://github.com/DavidBrenes1/finanzas-cli/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Cobertura](https://img.shields.io/badge/cobertura-96%25-brightgreen)
![Licencia](https://img.shields.io/badge/licencia-MIT-lightgrey)

Herramienta de línea de comandos para llevar el control de tus finanzas personales:
registra ingresos y gastos, define presupuestos mensuales por categoría y genera
reportes con gráficos de barras directamente en la terminal.

**Sin dependencias externas** — solo la biblioteca estándar de Python (`sqlite3`, `argparse`, `csv`, `decimal`).

```
$ finanzas reporte
Ingresos:    1,700,000.00
Gastos:        511,500.50
Balance:     1,188,499.50   (ahorro 69.9%)

Gastos por categoría
  vivienda       ████████████████████   360,000.00
  comida         ██████░░░░░░░░░░░░░░   103,700.50
  transporte     █░░░░░░░░░░░░░░░░░░░    24,800.00
  ocio           █░░░░░░░░░░░░░░░░░░░    23,000.00

Balance mensual
  2026-09    589,499.50
  2026-10    599,000.00
```

## ✨ Funcionalidades

- **Registro de movimientos** con categoría, descripción y fecha.
- **Presupuestos mensuales** por categoría con alertas cuando se exceden.
- **Reportes**: balance, tasa de ahorro, gastos por categoría y tendencia mensual.
- **Importación/exportación CSV** — la importación es *atómica*: si una fila es inválida, no se guarda nada y se indica la línea exacta del error.
- **Precisión monetaria**: los montos se guardan como centavos enteros (nunca `float`), evitando errores de redondeo como `0.1 + 0.2 != 0.3`.

## 🚀 Instalación

```bash
git clone https://github.com/DavidBrenes1/finanzas-cli.git
cd finanzas-cli
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## 📖 Uso

```bash
# Registrar movimientos (fecha por defecto: hoy)
finanzas ingreso 850000 salario -d "Salario octubre"
finanzas gasto 42500.50 comida -d "Supermercado" -f 2026-10-05

# Consultar
finanzas listar                    # todas las transacciones
finanzas listar -m 2026-10 -c comida
finanzas reporte -m 2026-10        # reporte de un mes

# Presupuestos
finanzas presupuesto comida 50000  # fijar límite mensual
finanzas presupuesto               # ver estado del mes actual

# Datos
finanzas importar docs/ejemplo.csv
finanzas exportar respaldo.csv
finanzas eliminar 7
```

```
$ finanzas presupuesto -m 2026-10
Presupuestos 2026-10
  comida         ████████████████████ 122.4%  quedan -11,200.00  ⚠ EXCEDIDO
  ocio           ░░░░░░░░░░░░░░░░░░░░   0.0%  quedan 30,000.00
```

Los datos se guardan en `~/.finanzas.db`. Puedes cambiar la ruta con `--db ruta.db`
o la variable de entorno `FINANZAS_DB`.

### Formato CSV

```csv
fecha,tipo,monto,categoria,descripcion
2026-10-01,ingreso,850000,salario,Salario octubre
2026-10-03,gasto,180000,vivienda,Alquiler
```

## 🏗️ Arquitectura

```
src/finanzas/
├── models.py    # Dominio: Transaccion, Tipo, validación y conversión de montos
├── storage.py   # Persistencia: Repositorio sobre SQLite + import/export CSV
├── reports.py   # Lógica de negocio: funciones puras de agregación
└── cli.py       # Interfaz: parseo de argumentos y presentación
```

El código sigue una **arquitectura en capas**: la CLI depende del repositorio y de los
reportes, pero los reportes son funciones puras que no saben nada de la base de datos.
Esto permite probarlos de forma aislada y reutilizarlos (por ejemplo, en una API web).
Más detalles en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## 🧪 Pruebas

```bash
pip install -e ".[dev]"
pytest          # 43 pruebas + doctests, con reporte de cobertura
ruff check .    # linter
```

La integración continua (GitHub Actions) ejecuta el linter y las pruebas en Python 3.10 a 3.13
en cada *push*.

## 🗺️ Hoja de ruta

### v1.1 — Funcionalidad básica ampliada
- [ ] Editar transacciones existentes (`finanzas editar 7 --monto 15000`)
- [ ] Transacciones recurrentes (salario, alquiler, suscripciones) generadas automáticamente cada mes
- [ ] Búsqueda por texto en descripciones
- [ ] Subcategorías (`comida/restaurantes`, `comida/supermercado`)

### v1.2 — Análisis
- [ ] Soporte multimoneda (CRC, USD, EUR) con tipo de cambio configurable
- [ ] Metas de ahorro con seguimiento de progreso
- [ ] Comparación entre meses ("este mes gastaste 15% más en comida")
- [ ] Proyección de fin de mes según el ritmo de gasto actual
- [ ] Detección de gastos inusuales (desviación respecto al promedio de la categoría)

### v1.3 — Visualización y datos
- [ ] Exportar reportes a PNG/PDF con matplotlib
- [ ] Interfaz de terminal interactiva (TUI) con Textual
- [ ] Importar estados de cuenta bancarios en CSV con mapeo de columnas configurable
- [ ] Categorización automática por reglas (p. ej. "Uber" → transporte)

### v2.0 — Plataforma
- [ ] API REST con FastAPI reutilizando las capas existentes
- [ ] Dashboard web
- [ ] Soporte para varios usuarios con autenticación
- [ ] Migración opcional a PostgreSQL mediante el patrón Repository
- [ ] Imagen Docker y despliegue en la nube

## 📄 Licencia

MIT © 2026 David Brenes
