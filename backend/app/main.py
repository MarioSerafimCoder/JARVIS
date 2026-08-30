from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and "." not in Path(path).name:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and "." not in Path(path).name:
            return await super().get_response("index.html", scope)
        return response

from app.api.router import router
from app.core.database import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Jarvis Local API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

if getattr(sys, "frozen", False):
    frontend_path = Path(sys._MEIPASS) / "frontend"
else:
    frontend_path = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/", SPAStaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": "Jarvis Local", "status": "online", "docs": "/docs"}
