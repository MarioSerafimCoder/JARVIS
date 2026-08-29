from fastapi import APIRouter

from app.api import backup, chat, conversations, domains, tools


router = APIRouter(prefix="/api")
router.include_router(chat.router)
router.include_router(conversations.router)
router.include_router(tools.router)
router.include_router(backup.router)
router.include_router(domains.router)
