"""导出 MP4 API：触发导出任务、查询状态、下载文件。"""
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import EXPORT_DIR
from app.database import get_db
from app.models import Material
from app.services.video_export import export_jobs, run_export

router = APIRouter(prefix="/api/materials", tags=["export"])


@router.post("/{material_id}/export")
def start_export(
    material_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """触发 ffmpeg 硬字幕导出（后台执行）。"""
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(404, "素材不存在")
    if material.status != "ready":
        raise HTTPException(400, "素材尚未生成完成，无法导出")
    job = export_jobs.get(material_id)
    if job and job["status"] == "processing":
        return {"status": "processing"}
    background_tasks.add_task(run_export, material_id)
    return {"status": "processing"}


@router.get("/{material_id}/export/status")
def export_status(material_id: int) -> dict:
    """查询导出任务状态。"""
    job = export_jobs.get(material_id)
    if job is None:
        # 已导出过（服务重启后内存丢失，检查文件是否存在）
        out_path = EXPORT_DIR / f"{material_id}.mp4"
        if out_path.exists():
            return {"status": "done"}
        return {"status": "none"}
    return {"status": job["status"], "error": job["error"]}


@router.get("/{material_id}/export/download")
def download_export(material_id: int, db: Session = Depends(get_db)) -> FileResponse:
    """下载导出的 MP4 文件。"""
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(404, "素材不存在")
    out_path = EXPORT_DIR / f"{material_id}.mp4"
    if not out_path.exists():
        raise HTTPException(404, "导出文件不存在，请先触发导出")
    return FileResponse(
        path=Path(out_path),
        media_type="video/mp4",
        filename=f"{material.title}.mp4",
        # 禁止缓存，确保重新导出后下载到的是最新版本
        headers={"Cache-Control": "no-store"},
    )
