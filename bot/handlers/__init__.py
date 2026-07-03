from aiogram import Router
from .profile import router as profile_router
from .contacts import router as contacts_router
from .browse import router as browse_router
from .base import router as base_router

router = Router()

# base_router contains fallback/cancel handlers and must be included last
router.include_routers(
    profile_router,
    contacts_router,
    browse_router,
    base_router
)