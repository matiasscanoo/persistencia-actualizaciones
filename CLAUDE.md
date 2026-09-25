# persistencia-actualizaciones

Microservicio de **escritura** de documentos PDF (MongoDB + Redis) del sistema
`microservicios-pdf` (UTN — Desarrollo de Software, 3er año). Repo:
https://github.com/matiasscanoo/persistencia-actualizaciones

Trabajo planificado en 14 issues de GitHub (#1 principal + #2..#14 sub-issues).
**Antes de tocar código, leer la issue correspondiente** (`gh issue view <n>`).
No cerrar una issue hasta cumplir todos sus criterios de aceptación.

## Responsabilidad

Crear, modificar y eliminar documentos; mantener Redis coherente tras cada
escritura; garantizar unicidad de `checksum`.

**Fuera de alcance** (son otros microservicios): consultas y listados
(persistencia-consultas), validación de PDF y tamaño (validacion-pdf),
extracción de texto/checksum/páginas (extraccion-texto), orquestación, retry y
SAGA (orquestador), Traefik y docker-compose del stack (infraestructura).
Tampoco se persiste el binario del PDF.

## Contrato compartido `microservicios-pdf` v1.0.0

JSON UTF-8 · IDs UUID · fechas ISO-8601 UTC. **Congelado**: cualquier cambio
sube versión y se documenta como compatible o BREAKING CHANGE.

| Método | Ruta | Éxito | Errores |
|---|---|---|---|
| POST | `/pdf` | 201 + documento | 400, 409, 503, 500 |
| PATCH | `/pdf/{id}` | 200 + documento | 400, 404, 503, 500 |
| DELETE | `/pdf/{id}` | 204 sin cuerpo | 400, 404, 503, 500 |
| GET | `/health` | 200 | — |

Documento: `id`, `nombre`, `checksum`, `texto`, `tamano_bytes`, `paginas`,
`created_at`, `updated_at`.
POST recibe `nombre`, `checksum`, `texto`, `tamano_bytes`, `paginas?`.
PATCH recibe solo `nombre`.

Errores: `{"error": {"code", "message", "details", "correlation_id"}}` con
`VALIDATION_ERROR` 400 · `RESOURCE_NOT_FOUND` 404 · `DUPLICATE_CHECKSUM` 409 ·
`DATABASE_ERROR` 503 · `DEPENDENCY_UNAVAILABLE` 503 · `INTERNAL_ERROR` 500.

Todos los servicios exponen `GET /health` y propagan `X-Correlation-ID`.

Variables: `MONGO_URI`, `MONGO_DATABASE`, `MONGO_COLLECTION`, `REDIS_URL`,
`REDIS_TTL_SECONDS`, `LOCK_TIMEOUT_SECONDS`.

## Arquitectura obligatoria (idéntica en los 5 repos)

```
app/
├── main.py           # composición: routers, middleware, handlers, DI
├── controllers/      # CAPA 1 — HTTP, rutas, status codes
├── schemas/          # CAPA 1 — DTOs Pydantic
├── services/         # CAPA 2 — reglas de negocio
├── models/           # CAPA 2 — entidades Python puro
└── core/             # CAPA 3 + transversal
    ├── config.py, exceptions.py, repository.py, database.py
    └── adaptadores concretos (mongo_repository, memory_repository, redis_*)
tests/unit/ · tests/integration/
```

Reglas: `controller → service → repository → BD`, nunca al revés ni salteando.
Controllers no importan Motor/pymongo/Redis ni repositorios concretos. Services
no importan `fastapi`. Models sin Pydantic ni decoradores de ORM. Schemas
distintos de las entidades. Todo repositorio con interfaz abstracta +
implementación real + implementación en memoria. Cableado concreto solo en
`main.py`. Type hints a la abstracción (`Repository[T]`), constructores sin
defaults para los puertos.

## Decisiones acordadas

- **Caché: invalidación**, no write-through. Tras escribir en Mongo se borran
  `pdf:id:{id}`, `pdf:checksum:{checksum}` y `pdf:list:*`.
- **Concurrencia**: lock en Redis por clave (`SET NX PX` + token, liberación
  segura con Lua), expiración `LOCK_TIMEOUT_SECONDS`. El índice único de
  `checksum` en Mongo es la garantía final.
- **Redis caído: fail-open**. La escritura en Mongo continúa y se loguea warning
  con `correlation_id`. Declarado como deuda técnica en el README.
- **Duplicados**: insertar y capturar `DuplicateKeyError` → `409`. No consultar
  antes (condición de carrera).
- **Mongo**: `_id` = UUID string, índice único en `checksum`, fechas datetime UTC.
- **Validación**: handler propio de `RequestValidationError` → `400`
  (FastAPI devuelve 422 por defecto). Schemas con `extra="forbid"`.

## Ambigüedades del contrato (detalle y estado en la issue #2)

A1 checksum: el modelo común dice SHA-256 y el ejemplo tiene 32 hex →
**64 hex en minúsculas** (el monolito usa `hashlib.sha256().hexdigest()`).
A2 `paginas` opcional en request, presente en response. A3 PATCH responde 200
con el documento completo. A4 400 en vez del 422 de FastAPI. A5 campos extra →
400. A6 DELETE repetido → 404 (el orquestador lo trata como compensación ya
aplicada). A7 `REDIS_TTL_SECONDS` no se consume con estrategia de invalidación.
A8 lock no obtenido → 503 `DEPENDENCY_UNAVAILABLE` con
`details.reason="lock_timeout"`. A9 staleness posible con Redis caído (deuda
técnica). A10 `_id` UUID. A11 `id` no-UUID → 400. A12 puerto por `PORT`.

## Reutilización del monolito

Origen: https://github.com/Enzo-Ezequiel/Proyecto-de-Desarrollo (público).

**Se porta**: `core/repository.py` (interfaz + `InMemoryRepository`, recortando
métodos sin uso), `core/mongo_repository.py` (mapeo `id ↔ _id` con Motor),
`models/base_model.py` (`BaseEntity`: UUID, timestamps UTC, `update_timestamp`),
`services/base_service.py` (CRUD con repositorio inyectado),
`core/exceptions.py` (jerarquía con `error_code`), `tests/conftest.py` (suite
hermética con `dependency_overrides` y env vars de test).

**No se porta**: `pdf_text_extractor.py` y pypdf, `_validar_formato`,
`_validar_tamano`, `FileSizeLimitMiddleware`, los GET de `pdf_routes.py`.

**Renombres respecto del monolito**: `nombre_pdf` → `nombre`, `contenido_pdf` →
`texto`; se agregan `tamano_bytes` y `paginas`; `{"detail": ...}` → formato de
error del contrato; duplicado 400 → 409; prefijo `/api/v1/pdfs` → `/pdf`.

## Metodología (evaluada por la cátedra)

**TDD, una slice vertical por ciclo**, un commit por fase:

1. `test(actualizaciones): crear test de <comportamiento>` ← falla (commit rojo)
2. `feat(actualizaciones): implementar <comportamiento>` ← lo mínimo para pasar
3. `refactor(actualizaciones): <mejora>` ← solo si hace falta

El commit rojo es la evidencia de test-first y **no toca código de producción**.
No escribir los diez tests y después las diez implementaciones.

Tests: rápidos, atómicos, independientes, **herméticos** (la suite corre sin
`.env`, sin MongoDB y sin Redis). Sin mocks de internals: el doble es
`InMemoryRepository`, inyectado con `app.dependency_overrides`.

**Git**: rama por cambio (`git switch -c <tipo>/<descripcion>`), nunca directo a
`main`. Antes de commitear, mostrar el diff y el mensaje propuesto y esperar
confirmación. Nunca `git add .` ni `git add -A`: listar los archivos de ese
commit. Push después de cada commit. Suite en verde antes de cada commit.
Nunca `push --force`, `reset --hard` ni reescritura de historial.
**Los mensajes de commit no llevan metadatos de herramientas** (nada de
`Co-Authored-By` ni enlaces de sesión).

**Stack fijo**: Python 3.10+, FastAPI, **uv** (nunca pip ni requirements.txt),
MongoDB con Motor, Redis, pytest, Ruff, Black. Toda config por variables de
entorno con pydantic-settings; `.env` ignorado, `.env.example` versionado.

**Antes de entregar**:

```bash
uv run pytest tests/ -v
uv run ruff check app/ tests/
uv run black --check app/ tests/
uv run pytest --cov=app --cov-report=term-missing
git ls-files | grep -E "\.(env|pyc)$"   # debe salir vacío
```

Más revisión manual: lógica duplicada, símbolos sin llamadores, imports
prohibidos entre capas, README suficiente para levantar desde un clon limpio,
commits rojos antes de los verdes.

**Deuda técnica**: declararla en el README con su motivo, no esconderla.

## Qué modelo usar en cada issue

Regla: **Opus para decidir, Sonnet para escribir.** Cambiar con `/model sonnet`
o `/model opus` sin perder el contexto de la sesión.

| Issue | Modelo | Por qué |
|---|---|---|
| #2 contrato | Opus | Resolver las 12 ambigüedades; cada decisión afecta a los otros repos |
| #3 estructura | Sonnet | Carpetas, `pyproject.toml`, `.gitignore` |
| #4 entorno | Sonnet | Pydantic Settings y `uv add` |
| #5 tests unitarios | Opus | Elegir casos límite y diseñar los dobles condiciona todo lo demás |
| #6 modelos y schemas | Sonnet | Dataclass y DTOs con el contrato ya cerrado |
| #7 Repository | Opus | Diseño de puertos (ISP, LSP, DIP) y lock con Lua |
| #8 reglas de negocio | Opus | Orden entre lock, escritura e invalidación; concurrencia |
| #9 controllers | Sonnet | Rutas, mapeo de errores, middleware |
| #10 integración HTTP | Sonnet | Más tests sobre el patrón ya armado |
| #11 Dockerfile | Sonnet | Receta conocida |
| #12 documentar | Sonnet | Redacción con todo decidido |
| #13 calidad | Sonnet + Opus | Sonnet corre los comandos; Opus revisa duplicación y historial TDD |
| #14 integración completa | Opus | Depuración entre servicios reales, timeouts, concurrencia |

Si en Sonnet un test se resiste y el arreglo da vueltas, pasar a Opus en vez de
insistir.

## Entorno de desarrollo

Windows, repo en `C:\dev\persistencia-actualizaciones` (fuera de OneDrive a
propósito). Python 3.11 y uv en Windows; Docker Desktop para los contenedores
(la integración con WSL está sin activar). MongoDB y Redis se levantan con
Docker cuando haga falta.
