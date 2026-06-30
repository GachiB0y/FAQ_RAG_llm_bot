from fastapi import APIRouter
from .auth import router as auth_router
from .chat import router as chat_router
from .documents import router as documents_router
from .users import router as users_router
from .settings import router as settings_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(documents_router)
api_router.include_router(users_router)
api_router.include_router(settings_router)
