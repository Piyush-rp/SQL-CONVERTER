from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.connections import router as connections_router
from app.api.database import router as database_router
from app.api.health import router as health_router
from app.api.query import router as query_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(connections_router)
api_router.include_router(database_router)
api_router.include_router(query_router)
api_router.include_router(admin_router)
