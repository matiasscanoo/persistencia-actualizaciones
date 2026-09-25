# persistencia-actualizaciones

Microservicio de **escritura** de documentos PDF del sistema `microservicios-pdf`
(UTN — Desarrollo de Software). Crea, modifica y elimina documentos en MongoDB,
mantiene Redis coherente tras cada escritura y garantiza la unicidad de
`checksum`. El contrato está en [`docs/contrato.md`](docs/contrato.md).

## Estructura

```
app/
├── main.py           # composición: routers, middleware, handlers, DI
├── controllers/      # capa 1: HTTP, rutas, status codes
├── schemas/          # capa 1: DTOs Pydantic
├── services/         # capa 2: reglas de negocio
├── models/           # capa 2: entidades Python puro
└── core/             # capa 3 y transversal: config, excepciones, repositorios
tests/
├── unit/
└── integration/
```

Flujo de dependencias: `controller → service → repository → BD`.

## Configuración

Toda la configuración va por variables de entorno (12-Factor), validadas al
arrancar con pydantic-settings: si falta una, la aplicación no inicia y el error
lista los campos faltantes. Para desarrollo local, copiar `.env.example` a `.env`
(ignorado por git) y completar los valores.

| Variable | Obligatoria | Descripción |
|---|---|---|
| `MONGO_URI` | sí | Conexión a MongoDB |
| `MONGO_DATABASE` | sí | Base de datos |
| `MONGO_COLLECTION` | sí | Colección de documentos PDF (compartida con persistencia-consultas) |
| `REDIS_URL` | sí | Conexión a Redis (lock e invalidación) |
| `LOCK_TIMEOUT_SECONDS` | sí | Expiración y espera máxima del lock; entero mayor que 0 |

`REDIS_TTL_SECONDS` figura en el contrato pero este servicio **no la consume**:
con estrategia de invalidación no escribe caché, y el TTL lo aplica
persistencia-consultas (A7 en [`docs/contrato.md`](docs/contrato.md)). Si está
definida en el entorno, se ignora.

## Desarrollo

```bash
uv sync
uv run pytest tests/ -v
```
