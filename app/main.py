"""FastAPI 应用入口：注册路由、挂载静态文件与媒体目录。"""
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import export, materials, settings, tree
from app.config import MEDIA_DIR, STATIC_DIR
from app.database import init_db

app = FastAPI(title="Listen Lab - 英语听读素材库")

app.include_router(tree.router)
app.include_router(materials.router)
app.include_router(export.router)
app.include_router(settings.router)


@app.on_event("startup")
def on_startup() -> None:
    """启动时初始化数据库。"""
    init_db()


@app.get("/")
def index() -> FileResponse:
    """返回主页面。"""
    return FileResponse(STATIC_DIR / "index.html")


# 媒体文件（视频）与静态资源
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
