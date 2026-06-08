from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import contacts, courses, customers, ingredients, orders, sales, settings, warehouse


def create_app() -> FastAPI:
    api = FastAPI(title="Gestion IREKS API", version="0.1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.include_router(customers.router)
    api.include_router(contacts.router)
    api.include_router(courses.router)
    api.include_router(ingredients.router)
    api.include_router(orders.router)
    api.include_router(sales.router)
    api.include_router(settings.router)
    api.include_router(warehouse.router)

    @api.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return api


app = create_app()
