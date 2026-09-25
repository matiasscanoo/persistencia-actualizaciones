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

La suite es hermética: corre sin `.env`, sin MongoDB y sin Redis. Los tests del
service usan los dobles en memoria (`InMemoryRepository`, `InMemoryCache`,
`InMemoryLock`).

### Tests de integración con MongoDB y Redis reales

Los adaptadores reales (`MongoRepository`, `RedisCache`, `RedisLock`) son el
*seam* del servicio: se prueban con las mismas suites de contrato que los dobles
en memoria (`tests/integration/test_*_contrato.py`), más tests propios de cada
adaptador. Los tests marcados `integration` se saltean si no está definida su
variable:

| Variable | Habilita |
|---|---|
| `TEST_MONGO_URI` | tests de `MongoRepository` contra un MongoDB real |
| `TEST_REDIS_URL` | tests de `RedisCache` y `RedisLock` contra un Redis real |

> ⚠️ Cada test **vacía la base Redis** de `TEST_REDIS_URL` (`FLUSHDB`) antes y
> después de correr. Usar una instancia o un número de base descartable, nunca
> el Redis del stack. En MongoDB cada test usa una colección propia en la base
> `persistencia_actualizaciones_test` y la borra al terminar.

Para correrlos en local con Docker:

```bash
docker run -d --name pa-mongo-test -p 27018:27017 mongo:7
docker run -d --name pa-redis-test -p 6380:6379 redis:7-alpine

TEST_MONGO_URI=mongodb://localhost:27018 \
TEST_REDIS_URL=redis://localhost:6380/0 \
uv run pytest tests/ -v
```

Los tests de "MongoDB o Redis caído" no necesitan ningún servicio: apuntan a un
puerto cerrado y corren siempre. En la integración con el stack completo (#13)
estos mismos tests se corren contra los contenedores de la infraestructura.
