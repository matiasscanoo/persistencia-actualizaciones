# Contrato de persistencia-actualizaciones

Microservicio de **escritura** de documentos PDF del sistema `microservicios-pdf`.
Implementa la parte de escritura del contrato compartido **v1.0.0**: crear,
modificar y eliminar documentos en MongoDB y dejar Redis coherente después de
cada escritura.

- **Fuente**: contrato compartido `microservicios-pdf` v1.0.0, tal como aparece
  en la issue #1 (endpoints, ejemplos de request/response, formato de error,
  códigos y variables de entorno).
- **Estado del contrato**: congelado. Todo cambio sube la versión y se documenta
  como compatible o *BREAKING CHANGE*.
- **Convenciones generales**: JSON UTF-8, IDs UUID, fechas ISO-8601 en UTC.
- Donde el contrato no dice nada, este documento remite a una ambigüedad de la
  [sección 10](#10-ambigüedades). Mientras una ambigüedad siga **abierta**, se
  implementa la propuesta que figura en la tabla.

## 1. Endpoints

| Método | Ruta | Éxito | Errores posibles |
|---|---|---|---|
| `POST` | `/pdf` | `201 Created` + documento | `400`, `409`, `503`, `500` |
| `PATCH` | `/pdf/{id}` | `200 OK` + documento | `400`, `404`, `503`, `500` |
| `DELETE` | `/pdf/{id}` | `204 No Content`, sin cuerpo | `400`, `404`, `503`, `500` |
| `GET` | `/health` | `200 OK` | — |

Todas las respuestas con cuerpo usan `Content-Type: application/json`.
Todas las respuestas, incluidas la `204` y las de error, llevan el header
`X-Correlation-ID` (ver [sección 6](#6-correlation-id)).

**Fuera de este servicio**: `GET /pdf`, `GET /pdf/{id}` y
`GET /pdf/checksum/{checksum}` pertenecen a **persistencia-consultas**. Este
servicio no los expone.

## 2. Requests

### 2.1 `POST /pdf`

```json
{
  "nombre": "contrato.pdf",
  "checksum": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "texto": "Contenido extraído del PDF",
  "tamano_bytes": 245760,
  "paginas": 3
}
```

| Campo | Tipo | Obligatorio | Restricciones | Ref. |
|---|---|---|---|---|
| `nombre` | string | sí | 1 a 255 caracteres; no puede ser vacío ni tener solo espacios | A13 |
| `checksum` | string | sí | SHA-256 en hex: exactamente 64 caracteres `[0-9a-f]`; las mayúsculas se rechazan, no se normalizan | A1 |
| `texto` | string | sí | puede ser `""` (PDF sin capa de texto); sin máximo propio | A13 |
| `tamano_bytes` | integer | sí | entero `>= 1` | A13 |
| `paginas` | integer \| null | no | entero `>= 0`; si se omite se guarda `null` | A2 |

Reglas comunes:

- **Tipos estrictos**: no se convierten tipos (`"245760"`, `true` o `3.0` en un
  campo entero → `400`) (A13).
- **Campos extra**: se rechazan con `400` (`extra="forbid"`) (A5).
- **`id`, `created_at` y `updated_at` los genera el servicio**. Si el cliente
  los envía, se tratan como campos extra y la respuesta es `400`.
- Si el body no es JSON válido o falta, la respuesta es `400 VALIDATION_ERROR` (A4).

### 2.2 `PATCH /pdf/{id}`

```json
{ "nombre": "contrato-renombrado.pdf" }
```

| Campo | Tipo | Obligatorio | Restricciones |
|---|---|---|---|
| `nombre` | string | sí | igual que en POST |

- `{id}` debe ser un UUID; si no lo es, la respuesta es `400 VALIDATION_ERROR` (A11).
- El único campo editable es `nombre`. Cualquier otro campo (por ejemplo
  `checksum` o `texto`) → `400` (A5). `{}` → `400` porque `nombre` es obligatorio.
- `updated_at` se actualiza siempre, aunque el nombre no cambie. `created_at`
  no cambia nunca.

### 2.3 `DELETE /pdf/{id}`

Sin body. `{id}` debe ser un UUID (A11).

### 2.4 `GET /health`

Sin parámetros.

## 3. Responses

### 3.1 Documento (`POST` → `201`, `PATCH` → `200`)

POST y PATCH devuelven el mismo schema: el documento completo después de la
escritura (A3).

```json
{
  "id": "8f6f7c3e-12d5-4f57-9c6c-123456789abc",
  "nombre": "contrato.pdf",
  "checksum": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "texto": "Contenido extraído del PDF",
  "tamano_bytes": 245760,
  "paginas": 3,
  "created_at": "2026-09-14T18:00:00.000Z",
  "updated_at": "2026-09-14T18:00:00.000Z"
}
```

| Campo | Tipo | Notas |
|---|---|---|
| `id` | string (UUID v4) | lo genera el servicio |
| `nombre` | string | |
| `checksum` | string | 64 hex en minúsculas |
| `texto` | string | |
| `tamano_bytes` | integer | |
| `paginas` | integer \| null | siempre presente, puede ser `null` (A2) |
| `created_at` | string ISO-8601 UTC | sufijo `Z`, precisión de milisegundos (A15) |
| `updated_at` | string ISO-8601 UTC | en el POST es igual a `created_at` |

### 3.2 `DELETE` → `204`

Sin cuerpo. Solo incluye el header `X-Correlation-ID`.

### 3.3 `GET /health` → `200`

```json
{ "status": "ok" }
```

Chequeo de *liveness*: indica que el proceso responde y no consulta MongoDB ni
Redis (A16).

## 4. Errores

Todos los errores usan el formato común del contrato:

```json
{
  "error": {
    "code": "DUPLICATE_CHECKSUM",
    "message": "Ya existe un documento con ese checksum",
    "details": {
      "checksum": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    },
    "correlation_id": "8f6f7c3e-12d5-4f57-9c6c-123456789abc"
  }
}
```

| Campo | Tipo | Notas |
|---|---|---|
| `code` | string | uno de los códigos de la tabla siguiente |
| `message` | string | texto para humanos, en español; los clientes no deben parsearlo |
| `details` | object | siempre presente (puede ser `{}`); su estructura por código se define en A14 |
| `correlation_id` | string | el mismo valor que el header `X-Correlation-ID` de la respuesta |

| `code` | HTTP | Cuándo | `details` (A14) |
|---|---|---|---|
| `VALIDATION_ERROR` | 400 | body inválido, JSON mal formado, campos extra, `id` no UUID | `{"errors": [{"field": "checksum", "message": "..."}]}` |
| `RESOURCE_NOT_FOUND` | 404 | no existe un documento con ese `id` (incluye el DELETE repetido, A6) | `{"id": "<id>"}` |
| `DUPLICATE_CHECKSUM` | 409 | ya existe un documento con ese `checksum` (índice único) | `{"checksum": "<checksum>"}` |
| `DATABASE_ERROR` | 503 | MongoDB no disponible o timeout | `{}`: no se exponen detalles internos |
| `DEPENDENCY_UNAVAILABLE` | 503 | no se obtuvo el lock dentro de `LOCK_TIMEOUT_SECONDS` (A8) | `{"reason": "lock_timeout"}` |
| `INTERNAL_ERROR` | 500 | cualquier error no controlado | `{}`: el detalle va solo al log |

En `details.errors[].field`, `field` es la ruta del campo sin el prefijo de
ubicación de FastAPI (`"checksum"`, `"id"`); si el error es del body completo
(JSON mal formado o ausente) el valor es `"body"`.

**Redis caído no produce errores**: el lock y la invalidación fallan en modo
*fail-open* (ver [sección 7](#7-redis)). `DEPENDENCY_UNAVAILABLE` solo aparece por
`lock_timeout`, cuando Redis responde pero otro proceso tiene el lock.

## 5. Códigos HTTP por endpoint

| Endpoint | Código | Situación |
|---|---|---|
| `POST /pdf` | 201 | documento creado |
| | 400 | body inválido o con campos extra |
| | 409 | `checksum` duplicado |
| | 503 | MongoDB caído (`DATABASE_ERROR`) o lock no obtenido (`DEPENDENCY_UNAVAILABLE`) |
| | 500 | error no controlado |
| `PATCH /pdf/{id}` | 200 | documento actualizado |
| | 400 | `id` no UUID, body inválido o con campos extra |
| | 404 | `id` inexistente |
| | 503 | MongoDB caído o lock no obtenido |
| | 500 | error no controlado |
| `DELETE /pdf/{id}` | 204 | documento eliminado |
| | 400 | `id` no UUID |
| | 404 | `id` inexistente o ya eliminado (A6) |
| | 503 | MongoDB caído o lock no obtenido |
| | 500 | error no controlado |
| `GET /health` | 200 | el proceso responde |

Rutas o métodos no definidos: ver A18.

**Orden de validación**: primero el formato del `id` de la ruta y el body (`400`)
y después el acceso a datos (`404`, `409`, `503`). Un request inválido nunca
llega a MongoDB ni a Redis.

## 6. Correlation ID

1. Se lee el header `X-Correlation-ID` del request.
2. Si falta o no es válido (vacío, más de 128 caracteres o con caracteres fuera
   del ASCII imprimible), se genera un UUID v4 (A17).
3. El valor se devuelve en el header `X-Correlation-ID` de **todas** las
   respuestas: éxito, error y `204`.
4. El mismo valor va en `error.correlation_id` de todo error.
5. Toda línea de log emitida durante el request lleva el `correlation_id`,
   incluidos los warnings de Redis en modo *fail-open*.

Este servicio no llama a otros microservicios, así que no propaga el header
hacia afuera.

## 7. Redis

### 7.1 Estrategia: invalidación

Este servicio **no escribe** en la caché: solo borra claves. Las claves las llena
**persistencia-consultas** (cache-aside) con su propio TTL. Por eso este servicio
no depende del formato de los valores cacheados, solo del **nombre de las claves**,
que tiene que coincidir con el que usa persistencia-consultas.

| Clave | Contenido (lo define persistencia-consultas) | Cuándo se invalida |
|---|---|---|
| `pdf:id:{id}` | documento por id | POST, PATCH y DELETE exitosos |
| `pdf:checksum:{checksum}` | documento por checksum | POST, PATCH y DELETE exitosos |
| `pdf:list:*` | listados paginados o filtrados | POST, PATCH y DELETE exitosos |

- `{id}` es el UUID del documento y `{checksum}` es el hex de 64 caracteres, sin
  prefijos ni transformaciones.
- `pdf:list:*` se borra con `SCAN` + `DEL` (o `UNLINK`), nunca con `KEYS`, para
  no bloquear Redis.
- En el PATCH se invalida también `pdf:checksum:{checksum}` aunque el checksum no
  cambie, porque el valor cacheado contiene el `nombre`.
- En el DELETE el `checksum` que hay que invalidar se obtiene del documento
  eliminado (`find_one_and_delete`).
- Solo se invalida después de una escritura **exitosa** en MongoDB. Si la
  escritura falla (`409`, `404`, `503`), no se toca la caché.

### 7.2 Lock distribuido

| Operación | Clave de lock |
|---|---|
| `POST /pdf` | `lock:pdf:checksum:{checksum}` |
| `PATCH /pdf/{id}` | `lock:pdf:id:{id}` |
| `DELETE /pdf/{id}` | `lock:pdf:id:{id}` |

- Adquisición: `SET <clave> <token> NX PX <LOCK_TIMEOUT_SECONDS * 1000>`, con un
  token UUID propio de cada request.
- Si el lock está tomado, se reintenta con espera corta hasta completar
  `LOCK_TIMEOUT_SECONDS`. Si no se obtiene: `503 DEPENDENCY_UNAVAILABLE` con
  `details.reason = "lock_timeout"` (A8).
- **Cuándo aparece `lock_timeout`**: la expiración y la espera máxima valen lo
  mismo, así que el lock del dueño vence antes de que se agote la espera de
  quien llegó después. Un dueño colgado o caído no provoca el `503`: quien espera
  obtiene el lock cuando vence, a lo sumo en `LOCK_TIMEOUT_SECONDS`. El `503`
  solo aparece cuando varias escrituras compiten por la misma clave y otra gana
  el lock recién liberado antes que este request.
- Liberación segura con un script Lua que borra la clave solo si el valor es el
  token propio.
- Orden: `lock → escritura en MongoDB → invalidación → liberar lock`.
- El prefijo `lock:` no se superpone con las claves `pdf:*` de la caché, así que
  el borrado de `pdf:list:*` nunca toca un lock.
- El lock reduce la contención, pero la garantía final de unicidad es el índice
  único de `checksum` en MongoDB.

### 7.3 Redis no disponible: *fail-open*

Si Redis no responde (conexión rechazada o timeout):

- **Lock**: la operación continúa sin lock y se loguea un warning con el
  `correlation_id`. La unicidad la sigue garantizando el índice de MongoDB.
- **Invalidación**: la escritura en MongoDB ya se hizo y se responde con éxito.
  Se loguea un warning con el `correlation_id` y las claves que no se pudieron
  borrar.

Esto puede dejar datos viejos en caché hasta que venza el TTL de
persistencia-consultas (A9). Está declarado como deuda técnica en el README.

## 8. Esquema en MongoDB

Colección: `MONGO_COLLECTION` de la base `MONGO_DATABASE`. **Compartida con
persistencia-consultas**, que solo lee: este servicio es el único que escribe.

```json
{
  "_id": "8f6f7c3e-12d5-4f57-9c6c-123456789abc",
  "nombre": "contrato.pdf",
  "checksum": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "texto": "Contenido extraído del PDF",
  "tamano_bytes": 245760,
  "paginas": 3,
  "created_at": { "$date": "2026-09-14T18:00:00.000Z" },
  "updated_at": { "$date": "2026-09-14T18:00:00.000Z" }
}
```

| Campo Mongo | Tipo BSON | Campo API | Notas |
|---|---|---|---|
| `_id` | string | `id` | UUID v4 en string, no `ObjectId` (A10) |
| `nombre` | string | `nombre` | |
| `checksum` | string | `checksum` | índice único |
| `texto` | string | `texto` | |
| `tamano_bytes` | int64 (`long`) | `tamano_bytes` | |
| `paginas` | int32 o `null` | `paginas` | el campo siempre existe; `null` si no vino en el POST |
| `created_at` | date | `created_at` | UTC, precisión de milisegundos (A15) |
| `updated_at` | date | `updated_at` | UTC |

**Índices**

| Nombre | Clave | Opciones |
|---|---|---|
| `_id_` | `{_id: 1}` | por defecto |
| `checksum_1` | `{checksum: 1}` | `unique: true` |

- Este servicio crea `checksum_1` al iniciar (`create_index` es idempotente).
- Un insert con `checksum` repetido lanza `DuplicateKeyError` → `409
  DUPLICATE_CHECKSUM`. No se consulta antes de insertar, para evitar la
  condición de carrera entre la consulta y el insert.
- El cliente Motor se crea con `tz_aware=True` para que las fechas vuelvan como
  `datetime` UTC y no como `datetime` sin zona horaria.
- No se guarda el binario del PDF (fuera de alcance en el contrato v1.0.0).

## 9. Compatibilidad con el modelo común v1.0.0

### 9.1 Documento

| Campo | Modelo común v1.0.0 | Este servicio | ¿Coincide? |
|---|---|---|---|
| `id` | UUID | UUID v4 string; `_id` en Mongo | sí (A10 fija el almacenamiento) |
| `nombre` | string | string 1–255 | sí; las restricciones de longitud son propias (A13) |
| `checksum` | SHA-256; el ejemplo tiene 32 hex | 64 hex en minúsculas | **no con el ejemplo** → A1 |
| `texto` | string | string, admite `""` | sí (A13) |
| `tamano_bytes` | integer | entero `>= 1` | sí (A13) |
| `paginas` | está en el ejemplo pero no en la lista de campos | opcional en request, siempre en response (`null` posible) | registrado → A2 |
| `created_at` | ISO-8601 UTC | ISO-8601 UTC, `Z`, milisegundos | sí; la precisión es propia (A15) |
| `updated_at` | ISO-8601 UTC | ídem | sí (A15) |

### 9.2 Endpoints, errores y transversales

| Elemento | Contrato v1.0.0 | Este servicio | ¿Coincide? |
|---|---|---|---|
| `POST /pdf` | 201 + documento | 201 + documento | sí |
| `PATCH /pdf/{id}` | solo `nombre`; no define la respuesta | 200 + documento completo | registrado → A3 |
| `DELETE /pdf/{id}` | 204 sin cuerpo | 204 sin cuerpo; repetido → 404 | sí; repetición → A6 |
| `GET /health` | 200 | 200 `{"status": "ok"}` | sí; cuerpo → A16 |
| Formato de error | `{error: {code, message, details, correlation_id}}` | idéntico | sí; `details` → A14 |
| Códigos de error | los 6 del contrato | los mismos 6, sin códigos nuevos | sí; lock → A8 |
| Validación | `400 VALIDATION_ERROR` | 400 (no el 422 de FastAPI) | sí → A4 |
| `X-Correlation-ID` | leer o generar y propagar | leer o generar, devolver y loguear | sí; formato → A17 |
| Variables de entorno | las 6 del contrato | las 6; `REDIS_TTL_SECONDS` no se consume | registrado → A7; puerto → A12 |
| Binario del PDF | fuera de alcance | no se guarda | sí |

### 9.3 Variables de entorno

| Variable | Uso en este servicio |
|---|---|
| `MONGO_URI` | conexión a MongoDB |
| `MONGO_DATABASE` | base de datos |
| `MONGO_COLLECTION` | colección de documentos PDF (compartida con persistencia-consultas) |
| `REDIS_URL` | conexión a Redis (lock e invalidación) |
| `REDIS_TTL_SECONDS` | no se consume (A7) |
| `LOCK_TIMEOUT_SECONDS` | expiración del lock y tiempo máximo de espera para obtenerlo |
| `PORT` | puerto de escucha de uvicorn, por defecto `8000`; **no es parte del contrato** (A12) |

Los valores por defecto y el `.env.example` se definen en la issue #4.

## 10. Ambigüedades

Estados:

- **Acordada**: decisión cerrada que no requiere confirmación de otro equipo.
- **Abierta**: se implementa la propuesta, pero falta la confirmación del
  equipo o de la cátedra que figura en la columna *Comunicar a*.

| # | Ambigüedad | Propuesta | Afecta a | Comunicar a | Estado |
|---|---|---|---|---|---|
| A1 | El modelo común dice que `checksum` es SHA-256, pero el ejemplo tiene 32 caracteres hex (largo de MD5). | Validar 64 hex en minúsculas (`^[0-9a-f]{64}$`), que es lo que devuelve `hashlib.sha256().hexdigest()`. Las mayúsculas se rechazan. Informar la inconsistencia del ejemplo. | extraccion-texto, orquestador, persistencia-consultas | cátedra, extraccion-texto | Abierta |
| A2 | `paginas` aparece en el ejemplo pero no en la lista de campos obligatorios. | Opcional en request (entero `>= 0`); siempre presente en response y en Mongo, con `null` si no vino. | extraccion-texto, persistencia-consultas | extraccion-texto, persistencia-consultas | Abierta |
| A3 | No se define la respuesta de `PATCH /pdf/{id}`. | `200 OK` con el documento completo actualizado, mismo schema que el POST. | orquestador / frontend | orquestador | Abierta |
| A4 | FastAPI responde `422` ante un body inválido; el contrato exige `400 VALIDATION_ERROR`. | Handler propio de `RequestValidationError` → `400`. | — | — | Acordada |
| A5 | Campos extra en POST/PATCH (por ejemplo `checksum` en PATCH). | Rechazar con `400 VALIDATION_ERROR` (`extra="forbid"`). | orquestador | orquestador (no debe mandar campos de más) | Abierta |
| A6 | `DELETE` repetido: la compensación SAGA tiene que ser idempotente. | El segundo `DELETE` responde `404 RESOURCE_NOT_FOUND`; el orquestador trata el `404` como compensación ya aplicada. | orquestador | orquestador | Abierta |
| A7 | `REDIS_TTL_SECONDS` está en las variables, pero con invalidación este servicio no escribe caché. | No consumirla, para no dejar configuración muerta. El TTL lo aplica persistencia-consultas. | persistencia-consultas | cátedra, persistencia-consultas | Abierta |
| A8 | No hay código de error para "lock no obtenido". | Reintentar hasta `LOCK_TIMEOUT_SECONDS`; si no se obtiene, `503 DEPENDENCY_UNAVAILABLE` con `details.reason = "lock_timeout"`. No se agregan códigos al contrato 1.0.0. Para el orquestador es un error transitorio, se puede reintentar. | orquestador | orquestador | Abierta |
| A9 | Con Redis caído durante la invalidación pueden quedar datos viejos, y el contrato pide que no quede información vieja. | *Fail-open* acordado: la escritura sigue y se loguea un warning; los datos viejos duran como máximo el TTL de consultas. Declarar como deuda técnica. También existe la carrera propia de cache-aside: consultas lee Mongo antes de la escritura y guarda en caché después de la invalidación. También queda acotada por el TTL y se declara. | persistencia-consultas | persistencia-consultas | Acordada (deuda técnica) |
| A10 | Identificador y formato del documento en MongoDB. | `_id` = UUID string; índice único en `checksum`; fechas como `date` BSON en UTC; `paginas` siempre presente. Este servicio crea el índice. | persistencia-consultas | persistencia-consultas | Abierta |
| A11 | `id` con formato inválido en la ruta. | `400 VALIDATION_ERROR` si no es UUID, antes de consultar MongoDB. | orquestador | — | Acordada |
| A12 | El puerto de escucha no está entre las variables del contrato. | Variable `PORT` al lanzar uvicorn, por defecto `8000` en la imagen. Documentarla en el README. | infraestructura | infraestructura | Abierta |
| A13 | El contrato no define restricciones de campos más allá del tipo. | `nombre` 1–255 caracteres, no vacío ni solo espacios (igual que el monolito). `texto` admite `""` y no tiene máximo propio (lo acotan el límite de 16 MiB por documento BSON y el tamaño máximo de validacion-pdf). `tamano_bytes >= 1`. `paginas >= 0`. Enteros estrictos, sin convertir tipos. | orquestador, extraccion-texto | orquestador | Abierta |
| A14 | `details` es un objeto sin estructura definida. | Por código: `VALIDATION_ERROR` → `{"errors": [{"field", "message"}]}`; `RESOURCE_NOT_FOUND` → `{"id"}`; `DUPLICATE_CHECKSUM` → `{"checksum"}`; `DEPENDENCY_UNAVAILABLE` → `{"reason"}`; `DATABASE_ERROR` e `INTERNAL_ERROR` → `{}`. Los clientes deciden por `code`, nunca por `details`. | orquestador | orquestador | Abierta |
| A15 | El contrato dice ISO-8601 UTC, pero no define la precisión ni la zona. MongoDB guarda milisegundos: si el POST devolviera microsegundos, persistencia-consultas devolvería otra fecha para el mismo documento. | Truncar a milisegundos al crear la entidad y serializar con sufijo `Z` (`2026-09-14T18:00:00.000Z`). | persistencia-consultas | persistencia-consultas | Abierta |
| A16 | `GET /health` solo define el `200`. | Cuerpo `{"status": "ok"}`, *liveness* sin chequear MongoDB ni Redis, para que una caída de la base no provoque reinicios del contenedor. | infraestructura | infraestructura | Abierta |
| A17 | No se define qué hacer si `X-Correlation-ID` viene con un formato inesperado. | Se propaga tal cual si no está vacío, tiene hasta 128 caracteres y usa solo ASCII imprimible (evita inyección en logs). Si no, se genera un UUID v4. No se exige que sea UUID. | orquestador | orquestador | Abierta |
| A18 | Rutas o métodos no definidos: FastAPI responde `404`/`405` con `{"detail": ...}`, fuera del formato común. | Envolver en el formato común. Ruta inexistente → `404 RESOURCE_NOT_FOUND`. Método no permitido → se mantiene `405` con `code = "VALIDATION_ERROR"` y `details.reason = "method_not_allowed"`, sin agregar códigos al contrato 1.0.0. | — | cátedra | Abierta |

### Comunicaciones pendientes

Las ambigüedades abiertas quedan cerradas cuando el equipo o la cátedra
confirman la propuesta. Resumen por destinatario:

- **Cátedra**: A1 (ejemplo de checksum con 32 hex), A7 (`REDIS_TTL_SECONDS`
  sin uso), A18 (`405` sin código propio en el contrato).
- **extraccion-texto**: A1 (formato de checksum), A2 (`paginas` opcional),
  A13 (`texto` vacío permitido).
- **orquestador**: A3, A5, A6 (DELETE repetido → 404), A8 (503
  `lock_timeout` se puede reintentar), A13, A14, A17.
- **persistencia-consultas**: A2, A7, A9, A10 (esquema Mongo e índice), A15
  (precisión de fechas) y los nombres exactos de las claves Redis de la
  [sección 7.1](#71-estrategia-invalidación).
- **infraestructura**: A12 (`PORT`), A16 (healthcheck de liveness).
