from aiogram import Router
from . import start, profile, inbox

# Combine all handler routers into a single master router
router = Router()
router.include_router(start.router)
router.include_router(profile.router)
router.include_router(inbox.router)