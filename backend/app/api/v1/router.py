from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    chat,
    health,
    media,
    mentoring,
    projects,
    schools,
    users,
    workspace,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(schools.router)
api_router.include_router(admin.router)
api_router.include_router(projects.router)
api_router.include_router(chat.router)
api_router.include_router(media.router)
api_router.include_router(workspace.router)
api_router.include_router(mentoring.router)
