# Imagen del microservicio de escritura persistencia-actualizaciones.
# python:3.12-slim ya no trae setuptools ni wheel preinstalados (en 3.11-slim, Grype
# marcaba wheel y jaraco-context con vulnerabilidades High).
FROM python:3.12-slim


WORKDIR /app

# Dependencias primero (cache de capas): solo se reinstalan si cambia el lock.
COPY pyproject.toml uv.lock ./
# uv se monta solo durante este RUN (--mount=from=...) y no queda en la imagen final:
# Grype marcaba High en librerías de Rust compiladas dentro del binario (quinn-proto,
# rustls-webpki).
RUN --mount=from=ghcr.io/astral-sh/uv:0.11.15,source=/uv,target=/bin/uv \
    uv sync --frozen --no-dev --no-install-project

COPY logging.json ./
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
# --timeout-graceful-shutdown: deja de aceptar conexiones y espera hasta 30 s a que
# terminen las escrituras en curso antes de salir (contrato 1.2.0, 12-Factor IX).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log --timeout-graceful-shutdown 30"]
