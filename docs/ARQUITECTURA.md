# Arquitectura y decisiones técnicas

## Capas

```
                       ┌──────────────┐     ┌─────────────┐
                 ┌───▶ │  storage.py  │ ──▶ │   SQLite    │
                 │     │ (Repositorio)│     └─────────────┘
┌──────────┐     │     └──────────────┘
│  cli.py  │ ────┤     ┌──────────────────────────────────────────┐
│ (entrada │     ├───▶ │ monedas · reports · analisis · metas     │  funciones puras
│ y salida)│     │     └──────────────────────────────────────────┘
└──────────┘     │     ┌──────────────┐
                 └───▶ │ graficos.py  │  matplotlib (opcional, importación tardía)
                       └──────────────┘
          todas las capas dependen de models.py (dominio + validación)
```

| Módulo        | Responsabilidad                                              | Depende de                  |
|---------------|--------------------------------------------------------------|-----------------------------|
| `models.py`   | Entidades (`Transaccion`, `Meta`), validación de montos y monedas | nada                   |
| `monedas.py`  | Convertir montos a la moneda base con `Decimal`              | `models`                    |
| `reports.py`  | Resumen, categorías, balance mensual, presupuestos           | `models`                    |
| `analisis.py` | Comparación entre meses, proyección, gastos inusuales        | `models`, `reports`         |
| `metas.py`    | Progreso de metas y ahorro mensual necesario                 | `models`                    |
| `storage.py`  | Leer y escribir SQLite y CSV, migraciones                    | `models`                    |
| `graficos.py` | Generar PNG con matplotlib                                   | `models`                    |
| `cli.py`      | Parsear argumentos, orquestar y formatear la salida          | todos                       |

## Decisiones (ADR resumidos)

### 1. Montos en centavos enteros
**Problema:** `float` no representa exactamente valores decimales (`0.1 + 0.2 == 0.30000000000000004`).
**Decisión:** el texto de entrada se convierte con `Decimal` y se guarda como `int` de centavos,
con redondeo `ROUND_HALF_UP`. Toda la aritmética interna es entera y exacta.

### 2. SQLite en lugar de JSON
**Por qué:** consultas con filtros (fecha, categoría) sin cargar todo en memoria, restricciones
`CHECK` en la base de datos como segunda línea de defensa, y transacciones ACID.

### 3. Patrón Repository
Toda la SQL vive en `Repositorio`. Cambiar a PostgreSQL implicaría reescribir una sola clase.
Las pruebas usan `":memory:"` para ser rápidas y aisladas.

### 4. Importación atómica
Primero se validan **todas** las filas del CSV y solo después se insertan en una única transacción.
Un archivo con un error en la línea 500 no deja 499 filas a medias en la base de datos.

### 5. Cálculos como funciones puras
`reports.py`, `analisis.py`, `metas.py` y `monedas.py` reciben datos y devuelven datos: no
imprimen ni consultan la base. Incluso la fecha actual se recibe como parámetro, así que las
pruebas no dependen del día en que se ejecutan.

### 6. Cero dependencias en tiempo de ejecución
El núcleo no trae paquetes de terceros: menos superficie de ataque y menos problemas de
compatibilidad. matplotlib es un *extra* opcional (`pip install ".[graficos]"`) y se importa
solo dentro del comando `grafico`. Si falta, el usuario recibe un mensaje con la instrucción de
instalación en vez de un error.

### 7. Multimoneda: guardar la moneda original y convertir al leer
**Alternativa descartada:** convertir a colones al registrar. Se perdería el monto original
y un tipo de cambio mal escrito quedaría grabado para siempre.
**Decisión:** cada transacción guarda su monto y su moneda originales. Los reportes convierten
al consultar con los tipos de cambio actuales, que se guardan como texto y se leen como
`Decimal`. Si falta un tipo de cambio, se muestra un error explícito en vez de un total incorrecto.

### 8. Migraciones sin perder datos
Al abrir la base, `Repositorio._migrar()` revisa las columnas con `PRAGMA table_info` y agrega
`moneda` (con valor por defecto `CRC`) si la base viene de la versión 1.0. Una prueba crea una
base con el esquema antiguo y verifica la migración.

### 9. Gastos inusuales: dos umbrales
Un gasto se marca solo si supera **ambos** umbrales: el promedio de su categoría más 2
desviaciones estándar (es atípico estadísticamente) y 1.5 veces el promedio (la diferencia
importa en la práctica). Con un solo criterio estadístico, un historial muy parejo marcaba
gastos apenas 18 % mayores. Las categorías con menos de 3 gastos previos no se evalúan.

## Calidad

- **85 pruebas** (unitarias e integración de la CLI) y doctests, con **98 % de cobertura**.
- Pruebas parametrizadas para casos límite: años bisiestos, montos inválidos (`nan`, `inf`,
  negativos), CSV corruptos, metas vencidas, desviación estándar cero y ausencia de matplotlib.
- `ruff` como linter y formateador; CI en GitHub Actions con matriz de Python 3.10–3.13.
