# Imagen del microservicio de escritura persistencia-actualizaciones.
# python:3.12-slim ya no trae setuptools ni wheel preinstalados (en 3.11-slim, Grype
# marcaba wheel y jaraco-context con vulnerabilidades High).
FROM python:3.12-slim

# Binario de uv, sin instalar nada por red aparte de la imagen oficial.
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependencias primero (cache de capas): solo se reinstalan si cambia el lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app/ ./app/

# Usuario sin privilegios; dueño de /app (venv + código) antes de bajar permisos.
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Sin curl: alcanza con la librería estándar de Python. Lee PORT como el CMD.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=2)"

# exec: uvicorn queda como PID 1 y recibe SIGTERM directo (apagado prolijo del lifespan).
# --no-access-log: la app ya registra cada request con su correlation_id.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
