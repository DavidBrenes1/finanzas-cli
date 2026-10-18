# Arquitectura y decisiones técnicas

## Capas

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│  cli.py  │ ──▶ │  storage.py  │ ──▶ │   SQLite    │
│ (entrada │     │ (Repositorio)│     └─────────────┘
│ y salida)│     └──────────────┘
│          │ ──▶ ┌──────────────┐
└──────────┘     │  reports.py  │   funciones puras
      │          └──────────────┘
      └────────▶ ┌──────────────┐
                 │  models.py   │   dominio + validación
                 └──────────────┘
```

| Módulo       | Responsabilidad                                   | Depende de           |
|--------------|---------------------------------------------------|----------------------|
| `models.py`  | Entidades, validación, conversión de montos       | nada                 |
| `reports.py` | Cálculos (resumen, categorías, presupuestos)      | `models`             |
| `storage.py` | Leer/escribir SQLite y CSV                         | `models`             |
| `cli.py`     | Parsear argumentos, orquestar y formatear salida  | todos                |

## Decisiones (ADR resumidos)

### 1. Montos en centavos enteros
**Problema:** `float` no representa exactamente valores decimales (`0.1 + 0.2 == 0.30000000000000004`).
**Decisión:** el texto de entrada se convierte con `Decimal` y se guarda como `int` de centavos,
con redondeo `ROUND_HALF_UP`. Toda la aritmética interna es entera y exacta.

### 2. SQLite en lugar de JSON
**Por qué:** consultas con filtros (fecha, categoría) sin cargar todo en memoria, restricciones
`CHECK` a nivel de base de datos como segunda línea de defensa, y transacciones ACID.

### 3. Patrón Repository
Toda la SQL vive en `Repositorio`. Cambiar a PostgreSQL implicaría reescribir una sola clase.
Las pruebas usan `":memory:"` para ser rápidas y aisladas.

### 4. Importación atómica
Primero se validan **todas** las filas del CSV y solo después se insertan en una única transacción.
Un archivo con un error en la línea 500 no deja 499 filas a medias en la base de datos.

### 5. Reportes como funciones puras
`reports.py` recibe listas de `Transaccion` y devuelve datos; no imprime ni consulta la base.
Esto los hace triviales de probar y reutilizables desde otra interfaz.

### 6. Cero dependencias en tiempo de ejecución
Instalar la herramienta no trae paquetes de terceros: menos superficie de ataque y menos
problemas de compatibilidad. Las dependencias de desarrollo (`pytest`, `ruff`) son opcionales.

## Calidad

- **43 pruebas** (unitarias + integración de la CLI) y doctests, **96 % de cobertura**.
- Pruebas parametrizadas para casos límite: años bisiestos, montos inválidos (`nan`, `inf`, negativos), CSV corruptos.
- `ruff` como linter y formateador; CI en GitHub Actions con matriz de Python 3.10–3.13.
