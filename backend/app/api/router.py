from fastapi import APIRouter

from app.api import backup, chat, cognitive, conversations, domains, tools, voice, web_browser


router = APIRouter(prefix="/api")
router.include_router(chat.router)
router.include_router(cognitive.router)
router.include_router(conversations.router)
router.include_router(tools.router)
router.include_router(backup.router)
router.include_router(domains.router)
router.include_router(voice.router)
router.include_router(web_browser.router)
