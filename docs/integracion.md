# Resultados de integración (issue #14)

Validación del servicio con dependencias reales en contenedores, en dos etapas:

1. **2026-09-30, servicio solo** con `mongo:7`, `redis:7-alpine` y la imagen del
   `Dockerfile` de este repo: todo lo que depende solo de este servicio, MongoDB y
   Redis. Los otros repos todavía no existían.
2. **2026-11-09, stack completo** (contrato 1.6.0): infraestructura (Consul, Traefik,
   MongoDB y Redis) y los cinco microservicios, levantados con los composes de
   `dockers` e `integracion`. Ver [Stack completo](#stack-completo-2026-11-09).

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
| Orquestador → POST/DELETE; lectura desde persistencia-consultas; Redis MISS → HIT → MISS | ✅ | [Stack completo](#stack-completo-2026-11-09) |

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
3. **Access log con `correlation_id`** (resuelto). La imagen desactiva el access
   log de uvicorn y el middleware registra cada request con su `correlation_id`.
   Todos los logs van a `stdout`.
4. **Esquema de MongoDB acordado con persistencia-consultas (A10).** Consultas
   lee `_id` (UUID en texto) y serializa las fechas con milisegundos y `Z` (A15),
   igual que este servicio.

## Stack completo (2026-11-09)

Los seis repos clonados al lado de este en `C:\dev` (`dockers` es el repo
`infraestructura`), con las imágenes de `main` de cada uno. La infraestructura se levantó
con `docker compose up -d --wait` en `dockers` y los microservicios con
`./scripts/levantar.sh` en `integracion`, que termina con el humo: los cinco `/health` en
`200` y el orquestador por Traefik (HTTPS) en `200`.

Los escenarios corrieron desde un contenedor descartable en la red `redutn`, por HTTP contra
cada servicio y leyendo Redis y MongoDB solo para verificar.

| Escenario | Resultado |
|---|---|
| Configuración desde el KV de Consul y registro | ✅ claves bajo `config/persistencia-actualizaciones/`; health check `passing` |
| Alta por Traefik (HTTPS) → orquestador → validación → extracción → este servicio | ✅ `201` en 228 ms, 12 ms en este servicio |
| La respuesta del orquestador es el documento de este servicio | ✅ mismo `id`; `checksum` = SHA-256 del PDF |
| `X-Correlation-ID` de punta a punta | ✅ el mismo ID en los logs de los cinco servicios (el orquestador solo acepta UUID, ver hallazgo 6) |
| Esquema en MongoDB | ✅ `_id` UUID, `tamano_bytes` int64, fechas `date` |
| persistencia-consultas lee lo escrito | ✅ por id devuelve exactamente el documento del `POST`, campo por campo |
| Redis MISS → HIT en consultas | ✅ 22,8 ms → 5,4 ms; quedan cacheadas `pdf:id`, `pdf:checksum` y `pdf:list` |
| `PATCH` invalida y consultas ve el dato nuevo | ✅ se borran las tres claves; por id, checksum y listado devuelve el nombre nuevo |
| Duplicado | ✅ `409 DUPLICATE_CHECKSUM` por el orquestador y directo; un solo documento |
| 20 `POST` simultáneos con el mismo `checksum` | ✅ `201` ×1 y `409` ×19; un solo documento |
| 20 `PATCH` simultáneos sobre el mismo `id` | ✅ `200` ×20; consultas muestra el último nombre; no quedan `lock:*` |
| Compensación SAGA | ✅ `DELETE` → `204`, repetido → `404`; consultas responde `404` y la caché queda limpia |
| Redis caído | ✅ `201` en 2,0 s (1 s de lock + 1 s de caché), dos warnings con el `correlation_id`; `/health` `200` con `"redis": "caido"` |
| MongoDB caído | ✅ `503 DATABASE_ERROR` en 5,3 s; `/health` `503` |
| MongoDB caído más de 1 minuto y de vuelta | ❌ → ✅ ver hallazgo 5, corregido en el PR #39 |

### Hallazgos del stack completo

5. **El servicio no volvía a Consul después de una baja** (corregido, PR #39). Se
   registraba solo al arrancar, con `DeregisterCriticalServiceAfter: 1m`. Con MongoDB
   detenido 80 s, Consul lo borró del catálogo; al volver MongoDB quedó sano pero
   invisible, y el orquestador respondía `503` ("no tiene instancias saludables") en todas
   las altas hasta reiniciar el contenedor (Docker lo ve `healthy` y no lo reinicia).
   Ahora revisa cada 30 s que siga registrado y, si no está, se vuelve a registrar:

   | Momento | Antes del arreglo | Después |
   |---|---|---|
   | MongoDB detenido +25 s | `critical` | `critical` |
   | +85 s | dado de baja | dado de baja |
   | MongoDB de vuelta +20 s | sigue dado de baja | **`passing`** |

6. **El orquestador reemplaza los `X-Correlation-ID` que no son UUID.** Es una decisión
   del orquestador; este servicio acepta cualquier ID de ASCII imprimible de hasta 128
   caracteres (A17). Con un UUID, el ID recorre los cinco servicios.
7. **persistencia-consultas tiene el mismo problema del hallazgo 5**: en la misma prueba
   desapareció del catálogo de Consul y no volvió. No es de este repo; queda reportado a
   su equipo.

El requisito del hallazgo 2 ya está en el compose de `integracion`
(`restart: unless-stopped` en este servicio).

## Cómo reproducir

Servicio solo:

```bash
docker run -d --name pa-mongo-test -p 27018:27017 mongo:7
docker run -d --name pa-redis-test -p 6380:6379 redis:7-alpine

TEST_MONGO_URI=mongodb://localhost:27018 \
TEST_REDIS_URL=redis://localhost:6380/0 \
uv run pytest tests/ -v
```

Stack completo (desde `C:\dev`, con los seis repos clonados y el certificado de
Traefik generado como dice `dockers/traefik/README.md`):

```bash
docker network create redutn          # una sola vez
(cd dockers && docker compose up -d --wait)
(cd integracion && ./scripts/levantar.sh)
```
