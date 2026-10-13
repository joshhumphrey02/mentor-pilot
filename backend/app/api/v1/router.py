from fastapi import APIRouter

from app.api.v1 import admin, auth, health, schools, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(schools.router)
api_router.include_router(admin.router)
