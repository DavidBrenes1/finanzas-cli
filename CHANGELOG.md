# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y
[versionado semántico](https://semver.org/lang/es/).

## [1.1.0] — 2026-10-20

### Agregado
- **Multimoneda**: opción `-M/--moneda` (CRC, USD, EUR) en `ingreso` y `gasto`, y nuevo
  comando `cambio` para configurar tipos de cambio. Reportes, presupuestos y análisis
  convierten a colones.
- **Metas de ahorro**: comando `meta` con las acciones `crear`, `aportar`, `retirar` y
  `eliminar`, más una vista de progreso con el ahorro mensual necesario.
- **Análisis**: comando `analisis` con comparación por categoría contra el mes anterior,
  proyección del gasto al cierre del mes, alertas de presupuesto proyectado y detección de
  gastos inusuales.
- **Gráficos**: comando `grafico` que exporta un PNG con gastos por categoría y balance
  mensual. Requiere el extra opcional `[graficos]` (matplotlib).
- Columna opcional `moneda` en la importación y exportación CSV.

### Cambiado
- Las bases de datos de la versión 1.0 se migran automáticamente (se agrega la columna `moneda`).
- La exportación CSV formatea montos con `Decimal` en vez de `float`.

## [1.0.0] — 2026-10-17

### Agregado
- Registro de ingresos y gastos, listado con filtros y eliminación.
- Reportes con balance, tasa de ahorro, gastos por categoría y balance mensual.
- Presupuestos mensuales por categoría.
- Importación atómica y exportación en CSV.
- Pruebas automatizadas, CI con GitHub Actions y documentación de arquitectura.
