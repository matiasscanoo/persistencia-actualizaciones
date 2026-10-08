# persistencia-actualizaciones

Microservicio de **escritura** de documentos PDF del sistema `microservicios-pdf`
(UTN — Desarrollo de Software). Crea, modifica y elimina documentos en MongoDB,
mantiene Redis coherente tras cada escritura y garantiza la unicidad de
`checksum`. El contrato está en [`docs/contrato.md`](docs/contrato.md).

## Instalación

Requisitos: Python 3.10+, [uv](https://docs.astral.sh/uv/) y, opcionalmente,
Docker (para levantar MongoDB/Redis locales o para correr la imagen).

```bash
git clone https://github.com/matiasscanoo/persistencia-actualizaciones.git
cd persistencia-actualizaciones
uv sync
```

## Configuración

Toda la configuración va por variables de entorno (12-Factor), validadas al
arrancar con pydantic-settings: si falta una, la aplicación no inicia y el error
lista los campos faltantes. Para desarrollo local, copiar `.env.example` a `.env`
(ignorado por git) y completar los valores.

| Variable | Obligatoria | Descripción | Ejemplo |
|---|---|---|---|
| `MONGO_URI` | sí | Conexión a MongoDB | `mongodb://localhost:27017` |
| `MONGO_DATABASE` | sí | Base de datos | `pdf` |
| `MONGO_COLLECTION` | sí | Colección de documentos PDF (compartida con persistencia-consultas) | `documentos` |
| `REDIS_URL` | sí | Conexión a Redis (lock e invalidación) | `redis://localhost:6379/0` |
| `LOCK_TIMEOUT_SECONDS` | sí | Expiración y espera máxima del lock; entero mayor que 0 | `5` |
| `LOG_LEVEL` | no | `DEBUG`, `INFO` (por defecto), `WARNING` o `ERROR` (contrato 1.2.0); otro valor impide arrancar | `INFO` |

`REDIS_TTL_SECONDS` figura en el contrato pero este servicio **no la consume**
(ver [Deuda técnica](#deuda-técnica)). Si está definida en el entorno, se ignora.

`PORT` (opcional, por defecto `8000`) no es parte del contrato compartido
(A12): fija el puerto de escucha de uvicorn. Se usa al ejecutar localmente o
con Docker, no está en `.env.example`.

## Ejecución local

```bash
cp .env.example .env
# completar MONGO_URI, MONGO_DATABASE, MONGO_COLLECTION, REDIS_URL, LOCK_TIMEOUT_SECONDS
# con un MongoDB y un Redis alcanzables (docker run mongo:7 / redis:7-alpine, o el stack compartido)

uv run uvicorn app.main:app --reload
```

Al arrancar, crea el índice único de `checksum` en MongoDB. Con las variables
completas y los servicios accesibles, `GET /health` responde `200
{"status": "ok", "dependencias": {"mongodb": "ok", "redis": "ok"}}`.

## Endpoints

Resumen; contrato completo, ejemplos de request/response y códigos de error
en [`docs/contrato.md`](docs/contrato.md).

| Método | Ruta | Éxito | Errores |
|---|---|---|---|
| `POST` | `/pdf` | `201` + documento | `400`, `409`, `503`, `500` |
| `PATCH` | `/pdf/{id}` | `200` + documento | `400`, `404`, `503`, `500` |
| `DELETE` | `/pdf/{id}` | `204` sin cuerpo | `400`, `404`, `503`, `500` |
| `GET` | `/health` | `200` | `503` si MongoDB no responde |

`GET /health` (contrato 1.2.0, reemplaza el liveness sin dependencias de A16)
consulta MongoDB (`ping`, cortado a 1 s) y Redis (`PING`, con el timeout de 1 s
del cliente). Con Redis caído responde `200` e informa `"redis": "caido"`: la
escritura sigue sin lock y sin invalidar (fail-open). Con MongoDB caído responde
`503 {"status": "error", ...}` y el `HEALTHCHECK` de la imagen falla. Probado en
el stack de integración (2026-10-07): MongoDB detenido → `503` en 1,0 s.

Toda respuesta, éxito o error, lleva el header `X-Correlation-ID` (se
respeta el recibido o se genera uno). Los errores usan el formato común
`{"error": {"code", "message", "details", "correlation_id"}}`.

## Estructura

```
app/
├── main.py           # composición: routers, middleware, handlers, DI, lifespan
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

## Logs (12-Factor XI)

Van a `stdout`, sin archivos. La configuración está en [`logging.json`](logging.json),
en la raíz del repo (formato `dictConfig`): handler a stdout con
`CorrelationIdFilter` y el formato del contrato 1.2.0 (`pymongo` en `WARNING`).
El nivel sale de `LOG_LEVEL`, que se aplica en el `lifespan`.

```text
INFO app.main correlation_id=- servicio iniciado
INFO app.services.documento_service correlation_id=75c93b70-... documento creado id=13f4459b-... checksum=7e72f0...
INFO app.main correlation_id=75c93b70-... method=POST path=/pdf status=201 duracion_ms=18.5
WARNING app.services.documento_service correlation_id=1b2c... Lock no disponible; se escribe sin lock: lock:pdf:checksum:...
```

| Nivel | Qué registra este servicio |
|---|---|
| `INFO` | Cada request (método, ruta, status, duración), documento creado (`id`, `checksum`), modificado o eliminado (`id`), inicio y apagado. |
| `WARNING` | Redis no disponible para el lock o la invalidación (fail-open), base de datos no disponible. |
| `ERROR` | Errores no controlados, con traza. |

**No se registran** el nombre ni el texto del documento (pueden tener datos
personales); hay un test que lo verifica.

## Finalización segura (12-Factor IX)

La imagen corre uvicorn como PID 1 (`exec`) con `--timeout-graceful-shutdown 30`.
Ante `SIGTERM` (`docker stop`) deja de aceptar conexiones, termina las escrituras
en curso y en el `lifespan` cierra MongoDB y Redis (`apagado iniciado` /
`apagado completo`); sale con código 0 (probado con la imagen `1.0.2`). Cada alta
es una sola escritura en MongoDB: aunque llegara un `SIGKILL`, no queda un
documento a medias.

## Decisiones técnicas

- **N-capas + Repository**: `controller → service → repository → BD`, con
  puertos abstractos (`Repository`, `Cache`, `Lock`) y su doble en memoria
  para tests hermético (`InMemoryRepository`, `InMemoryCache`, `InMemoryLock`).
- **Invalidación, no write-through**: el servicio no escribe caché, solo la
  borra tras cada escritura exitosa en Mongo (`pdf:id:{id}`,
  `pdf:checksum:{checksum}`, `pdf:list:*`; contrato, sección 7.1).
- **Lock distribuido en Redis** (`SET NX PX` + token propio, liberación
  atómica con Lua): reduce la contención entre escrituras concurrentes; la
  garantía final de unicidad de `checksum` es el índice único en MongoDB
  (contrato, sección 7.2).
- **Redis caído: fail-open**. La escritura en Mongo sigue igual y se loguea
  un warning con `correlation_id`; ver [Deuda técnica](#deuda-técnica).
- **`_id` en MongoDB es un UUID string**, no `ObjectId` (A10), para que
  coincida con el `id` que expone la API.
- **`400 VALIDATION_ERROR`** en vez del `422` por defecto de FastAPI (A4),
  con un handler propio de `RequestValidationError` y `extra="forbid"` en
  los schemas de request.

El resto de las ambigüedades del contrato y cómo se resolvieron:
[`docs/contrato.md`](docs/contrato.md#10-ambigüedades).

## Tests

```bash
uv sync
uv run pytest tests/ -v
uv run pytest --cov=app --cov-report=term-missing
```

La suite es hermética: corre sin `.env`, sin MongoDB y sin Redis. Los tests
de service y de la capa HTTP usan los dobles en memoria
(`InMemoryRepository`, `InMemoryCache`, `InMemoryLock`), inyectados con
`app.dependency_overrides` — sin mockear internals.

### Qué se testea y qué no (seam)

Controllers y services quedan completamente cubiertos con dobles en
memoria. Los adaptadores reales (`MongoRepository`, `RedisCache`,
`RedisLock`) y el `lifespan` de `main.py` (que los cablea al arrancar) son
deliberadamente delgados y se prueban con MongoDB y Redis reales, no con
mocks — ver la sección siguiente. Sin esos servicios, esas líneas quedan sin
cubrir en el reporte de `--cov`; es la excepción documentada, no un
descuido.

### Tests de integración con MongoDB y Redis reales

Los tests marcados `integration` (adaptadores, más el wiring del `lifespan`)
se saltean si no está definida su variable:

| Variable | Habilita |
|---|---|
| `TEST_MONGO_URI` | tests de `MongoRepository` y del `lifespan` contra un MongoDB real |
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
puerto cerrado y corren siempre. En la integración con el stack completo (#14)
estos mismos tests se corren contra los contenedores de la infraestructura.
Resultados de la validación con servicios reales:
[`docs/integracion.md`](docs/integracion.md).

## Docker

```bash
docker build -t persistencia-actualizaciones:1.0.4 .
```

La versión del servicio es la de `pyproject.toml` (1.0.4): es la que muestra Swagger en
`/docs` y el tag de la imagen. `tests/integration/test_openapi.py` verifica que
`FastAPI(version=...)` en `app/main.py` coincida con `pyproject.toml`; en una versión
nueva se cambian los dos.

La imagen (`python:3.12-slim`) instala las dependencias con `uv sync --frozen`
antes de copiar `app/`, para aprovechar la cache de capas. El proceso corre
como usuario sin privilegios (`appuser`, no root) y expone el puerto `8000`
con un `HEALTHCHECK` contra `GET /health` hecho con la librería estándar de
Python (sin agregar `curl` a la imagen). No incluye `.env`, tests ni
credenciales (ver `.dockerignore`): toda la configuración se inyecta en
runtime.

```bash
docker run -d --name persistencia-actualizaciones \
  --env-file .env \
  -p 8000:8000 \
  persistencia-actualizaciones
```

Variables: las de la tabla de [Configuración](#configuración), más `PORT`
(opcional, por defecto `8000`) para el puerto de escucha de uvicorn dentro del
contenedor.

Para conectar el contenedor a MongoDB y Redis del stack compartido, unirlo a
la red de `infraestructura` (`docker network connect <red> persistencia-actualizaciones`)
y usar en `MONGO_URI`/`REDIS_URL` el nombre de servicio de esos contenedores
en vez de `localhost`.

## Integración con el stack

- **MongoDB**: la colección (`MONGO_COLLECTION`) es compartida con
  **persistencia-consultas**, que solo lee; este servicio es el único que
  escribe y el que crea el índice único de `checksum` al arrancar.
- **Redis — invalidación**: tras cada escritura exitosa borra `pdf:id:{id}`,
  `pdf:checksum:{checksum}` y `pdf:list:*`. Esas claves las llena y lee
  **persistencia-consultas** (cache-aside); este servicio nunca escribe en
  la caché, solo la invalida (contrato, sección 7.1).
- **Redis — lock**: `lock:pdf:checksum:{checksum}` (POST) o
  `lock:pdf:id:{id}` (PATCH/DELETE), propio de este servicio; no se
  superpone con las claves `pdf:*` de la caché.
- **orquestador**: dispara las escrituras vía HTTP y trata `503
  DEPENDENCY_UNAVAILABLE` (`details.reason = "lock_timeout"`) y `503
  DATABASE_ERROR` como errores transitorios, reintentables. Un `DELETE`
  repetido responde `404` y se interpreta como compensación SAGA ya
  aplicada (A6).
- **Red y compose del stack**: se definen en el repo `infraestructura`
  (fuera de este repo); no se versiona acá.
- **Arranque**: al iniciar, el servicio crea el índice único de `checksum`. Si
  MongoDB no responde, **no arranca** (`exit 3` a los ~5 s): sin ese índice no
  hay garantía de unicidad. El compose del stack tiene que declarar
  `restart: unless-stopped` y `depends_on: mongo: condition: service_healthy`.

## Deuda técnica

- **Staleness posible con Redis caído** (A9): si Redis no responde durante
  la invalidación, la escritura en Mongo ya se hizo y se responde con
  éxito; la caché puede quedar con datos viejos hasta que
  persistencia-consultas los pise por su propio TTL. Se loguea un warning
  con `correlation_id`, pero no hay reintento de invalidación desde este
  servicio.
- **`REDIS_TTL_SECONDS` no se consume** (A7): con la estrategia de
  invalidación este servicio no escribe caché, así que no tiene un TTL
  propio que aplicar; la variable existe en el contrato compartido pero
  queda sin uso acá. El TTL real lo aplica persistencia-consultas.
- **Access log con `correlation_id`** (resuelto en la auditoría de
  integración): la imagen corre uvicorn con `--no-access-log` y el middleware
  registra cada request (método, ruta, status y duración) dentro de su contexto,
  así que toda línea lleva el `correlation_id` (contrato 6.5). Los logs van a
  `stdout` (12-Factor XI). Desde el contrato 1.2.0 el formato es
  `correlation_id=<id>` (antes `[<id>]`), igual en los cinco servicios.
- El resto de las ambigüedades y su estado (acordada / abierta a
  comunicar): [`docs/contrato.md`](docs/contrato.md#10-ambigüedades).
