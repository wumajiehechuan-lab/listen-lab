"""素材相关 API：上传、详情、状态、删除。"""
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import MEDIA_DIR
from app.database import get_db
from app.models import Material
from app.services.pipeline import run_pipeline

router = APIRouter(prefix="/api/materials", tags=["materials"])

ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".mp3", ".wav", ".m4a"}


def _serialize_detail(material: Material) -> dict:
    """序列化素材详情（含字幕与重点词）。"""
    return {
        "id": material.id,
        "title": material.title,
        "status": material.status,
        "error_msg": material.error_msg,
        "duration_sec": material.duration_sec,
        "video_url": f"/media/{material.id}/{Path(material.video_path).name}",
        "subtitles": [
            {
                "seq": s.seq,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "text_en": s.text_en,
                "text_zh": s.text_zh or "",
            }
            for s in material.subtitles
        ],
        "keywords": [
            {
                "word": k.word,
                "phonetic": k.phonetic or "",
                "pos": k.pos or "",
                "meaning_zh": k.meaning_zh or "",
                "seq": k.subtitle_seq,
            }
            for k in material.keywords
        ],
    }


@router.post("/upload")
async def upload_material(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    title: str = Form(""),
    folder_id: int | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    """上传视频并触发素材生成流水线。"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的文件类型: {suffix}")

    # 先创建素材记录以获取 id 作为媒体目录名
    material = Material(
        folder_id=folder_id,
        title=title.strip() or Path(file.filename or "未命名").stem,
        video_path="",
        status="processing",
    )
    db.add(material)
    db.flush()

    media_dir = MEDIA_DIR / str(material.id)
    media_dir.mkdir(parents=True, exist_ok=True)
    video_path = media_dir / f"video{suffix}"
    with video_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    material.video_path = str(video_path)
    db.commit()

    background_tasks.add_task(run_pipeline, material.id)
    return {"id": material.id, "status": "processing"}


@router.get("/{material_id}")
def get_material(material_id: int, db: Session = Depends(get_db)) -> dict:
    """获取素材详情（字幕 + 重点词）。"""
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(404, "素材不存在")
    return _serialize_detail(material)


@router.get("/{material_id}/status")
def get_material_status(material_id: int, db: Session = Depends(get_db)) -> dict:
    """查询素材处理状态（供前端轮询）。"""
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(404, "素材不存在")
    return {
        "id": material.id,
        "status": material.status,
        "error_msg": material.error_msg,
    }


@router.delete("/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)) -> dict:
    """删除素材及其媒体文件。"""
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(404, "素材不存在")
    db.delete(material)
    db.commit()
    media_dir = MEDIA_DIR / str(material_id)
    if media_dir.exists():
        shutil.rmtree(media_dir)
    return {"ok": True}
