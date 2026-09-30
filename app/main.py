"""Composición de la aplicación: routers, middleware, handlers de error y DI."""

from fastapi import FastAPI

from app.controllers.health_controller import router as health_router

app = FastAPI(title="persistencia-actualizaciones")

app.include_router(health_router)
