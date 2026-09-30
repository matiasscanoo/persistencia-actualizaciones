"""Composición de la aplicación: routers, middleware, handlers de error y DI."""

from fastapi import FastAPI

from app.controllers.documento_controller import router as documento_router
from app.controllers.health_controller import router as health_router

app = FastAPI(title="persistencia-actualizaciones")

app.include_router(health_router)
app.include_router(documento_router)
