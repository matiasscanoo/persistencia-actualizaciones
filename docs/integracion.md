# Resultados de integración (issue #14)

Validación del servicio con dependencias reales en contenedores. Ejecutada el
2026-09-30 sobre la rama `test/integracion-servicio-real` con `mongo:7`,
`redis:7-alpine` y la imagen del `Dockerfile` de este repo.

**Alcance.** Los repos de **orquestador**, **persistencia-consultas** e
**infraestructura** (el `docker compose` del stack) no estaban disponibles.
Todo lo que depende solo de este servicio, MongoDB y Redis quedó verificado.
Lo que necesita a los otros servicios figura en
[Pendiente](#pendiente-cuando-exista-el-stack).

## Escenarios de la issue

| Escenario | Resultado | Dónde |
|---|---|---|
| Invalidación con Redis real tras POST/PATCH/DELETE; no toca claves ajenas ni deja locks | ✅ | `test_servicio_real.py` |
| POST repetido tras un timeout → `409 DUPLICATE_CHECKSUM`, un solo documento | ✅ | `test_servicio_real.py` |
| Compensación SAGA: DELETE → `204`; DELETE repetido → `404` | ✅ | `test_servicio_real.py` |
| Concurrencia: N POST con el mismo `checksum` → un solo documento | ✅ | `test_servicio_real.py` |
| Concurrencia: N PATCH sobre el mismo `id` → queda la última escritura, sin caché vieja | ✅ | `test_servicio_real.py` |
| Redis caído → escritura OK y warning con `correlation_id` | ✅ | `test_servicio_real.py` + manual E3 |
| MongoDB caído → `503 DATABASE_ERROR` en tiempo acotado | ✅ | manual E4 |
| Índice único de `checksum` y suite de contrato contra `MongoRepository` real | ✅ | `test_repositorio_contrato.py`, `test_mongo_repository.py` + manual E1 |
| Esquema en Mongo legible por persistencia-consultas (sección 8 del contrato) | ✅ (tras corregir `tamano_bytes`) | `test_mongo_repository.py` + manual E2 |
| `X-Correlation-ID` recibido → header de respuesta y logs de este servicio | ✅ | manual E2–E4 |
| Orquestador → POST/DELETE; lectura desde persistencia-consultas; Redis MISS → HIT → MISS | ⏳ | falta el stack |

Distribución medida con 20 escrituras simultáneas por el ASGI real:

- 20 `POST` con el mismo checksum dieron `201` ×1 y `409` ×19.
- 20 `PATCH` sobre el mismo id dieron `200` ×20, serializados por el lock (unos
  60 ms entre cada uno por la espera de 50 ms entre intentos).

Con más de unos 30 escritores sobre la misma clave empiezan a aparecer
`503 DEPENDENCY_UNAVAILABLE` (`lock_timeout`), que es el comportamiento
esperado según A8.

## Escenarios manuales (servicio en contenedor)

El servicio corre desde su imagen, en una red Docker con `mongo` y `redis`, y
las dependencias se detienen con el servicio en marcha.

| # | Escenario | Resultado observado |
|---|---|---|
| E1 | Arranque | contenedor `healthy`; índices `_id_` y `checksum_1` (`unique: true`) |
| E2 | `POST` sin `paginas`, con `X-Correlation-ID: e2e-orq-001` | `201`, header `x-correlation-id: e2e-orq-001`, `paginas: null`. En Mongo: `_id` string, fechas `date`, `paginas` presente en `null` |
| E3 | `docker stop` de Redis y `POST` | `201` en ~1 s; en los logs, dos `WARNING [e2e-redis-caido]` (sin lock y caché sin invalidar); `/health` `200` |
| E4 | `docker stop` de MongoDB y `POST` | `503 DATABASE_ERROR` en 5,07 s (`serverSelectionTimeoutMS=5000`), `correlation_id` en cuerpo y log; `/health` `200` |
| E5 | Mongo y Redis de nuevo arriba, sin reiniciar el servicio | `POST` → `201`; no quedó ninguna clave `lock:*` después del `503` de E4 |
| E6 | MongoDB detenido **al arrancar** el servicio | `crear_indices()` falla a los ~5 s: `Application startup failed`, el contenedor termina con `exit 3` |

## Hallazgos

1. **`tamano_bytes` se guardaba como int32** cuando el contrato (sección 8)
   pide int64. PyMongo guarda int32 los valores que entran y int64 los mayores
   a 2 GiB, así que la colección quedaba con tipos mixtos. **Corregido**: rojo
   `3e47d91` → `fix` `dae1440`.
2. **El servicio no arranca con MongoDB caído (E6).** Es una decisión: sin el
   índice único no hay garantía de unicidad de `checksum`, así que se prefiere
   fallar rápido a arrancar sin él. **Requisito para infraestructura**:
   `restart: unless-stopped` y `depends_on: mongo: condition: service_healthy`.
   Documentado en el README.
3. **El access log de uvicorn no lleva `correlation_id`**. Lo emite el servidor,
   fuera del contexto del request de la app. Todas las líneas de la app sí lo
   llevan. Declarado como deuda técnica en el README frente al contrato 6.5.

## Pendiente cuando exista el stack

- Orquestador → `POST /pdf` y `DELETE /pdf/{id}` como compensación, y que la
  respuesta del `POST` sea la que el orquestador devuelve al frontend.
- persistencia-consultas lee lo escrito (`GET /pdf/{id}`,
  `GET /pdf/checksum/{checksum}`), y la secuencia MISS → HIT → PATCH/DELETE
  → MISS con datos nuevos.
- `X-Correlation-ID` desde el orquestador hasta los logs de este servicio.
- Correr todo con el `docker compose` del stack y su red compartida.
- Comunicar a infraestructura el requisito del hallazgo 2.

## Por qué la #14 sigue abierta y cómo retomarla

La #14 queda **abierta a propósito**: sus criterios de aceptación piden correr
los escenarios con el `docker compose` del stack y con orquestador y
persistencia-consultas reales, y al 2026-09-30 esos repos no estaban
disponibles. Lo que depende solo de este servicio ya está verificado (tabla de
arriba). No hay que rehacerlo; alcanza con correr la suite con
`TEST_MONGO_URI`/`TEST_REDIS_URL` como chequeo de regresión.

Cuando estén los repos de **orquestador**, **persistencia-consultas** e
**infraestructura**:

1. Clonarlos junto a este (`C:\dev\<repo>`) y leer su README y su contrato. Si
   las issues de este repo pasan a formar parte de otros, leer también la #1.
2. **Revisar la compatibilidad antes de levantar nada.** Contra
   [`contrato.md`](contrato.md), confirmar en el código de los otros servicios:
   - **persistencia-consultas:**
     - nombres exactos de las claves Redis: `pdf:id:{id}`,
       `pdf:checksum:{checksum}`, `pdf:list:*` (sección 7.1)
     - que lea `_id` como UUID string, las fechas como `date` y
       `tamano_bytes` como int64 (sección 8)
     - que use el mismo `MONGO_DATABASE`/`MONGO_COLLECTION`
     - que no cree su propio índice sobre `checksum` con otro nombre
   - **orquestador:**
     - que use `POST /pdf` y `DELETE /pdf/{id}`
     - que trate el `404` de un `DELETE` repetido como compensación ya
       aplicada (A6)
     - que reintente ante un `503` (`DATABASE_ERROR` y
       `DEPENDENCY_UNAVAILABLE`/`lock_timeout`, A8)
     - que propague `X-Correlation-ID`
     - que no mande campos extra (A5)
   - **infraestructura:**
     - que exista el servicio de este repo en el compose, con las 5
       variables de entorno
     - `restart: unless-stopped` y `depends_on: mongo: condition:
       service_healthy` (hallazgo 2)
     - la red compartida y la regla de Traefik hacia `/pdf`
3. Levantar el stack con su compose y ejecutar lo que figura en
   [Pendiente](#pendiente-cuando-exista-el-stack):
   - flujo orquestador → `POST`
   - compensación → `DELETE`
   - lectura desde persistencia-consultas y la secuencia MISS → HIT →
     PATCH/DELETE → MISS
   - `X-Correlation-ID` de punta a punta en los logs de los tres servicios
   - repetir E3/E4 (Redis y Mongo caídos) dentro del stack
4. Reportar las incompatibilidades como issue en el repo que corresponda. Si
   hay que cambiar el contrato compartido, se sube de versión y se documenta
   como compatible o *BREAKING CHANGE*.
5. Agregar los resultados a este documento, pegarlos como comentario en la
   #14 y cerrarla. En este repo el `Closes #N` no cierra issues al mergear:
   hay que cerrarla a mano con `gh issue close 14`.

## Cómo reproducir

```bash
docker run -d --name pa-mongo-test -p 27018:27017 mongo:7
docker run -d --name pa-redis-test -p 6380:6379 redis:7-alpine

TEST_MONGO_URI=mongodb://localhost:27018 \
TEST_REDIS_URL=redis://localhost:6380/0 \
uv run pytest tests/ -v
```
