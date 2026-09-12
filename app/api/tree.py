"""树状导航与文件夹管理 API。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Folder, Material

router = APIRouter(prefix="/api", tags=["tree"])


class FolderCreate(BaseModel):
    """新建文件夹请求体。"""

    name: str
    parent_id: int | None = None


class FolderRename(BaseModel):
    """重命名文件夹请求体。"""

    name: str


def _folder_children_map(folders: list[Folder]) -> dict[int | None, list[Folder]]:
    """按 parent_id 分组文件夹。"""
    mapping: dict[int | None, list[Folder]] = {}
    for f in folders:
        mapping.setdefault(f.parent_id, []).append(f)
    return mapping


def _build_folder_node(
    folder: Folder,
    children_map: dict[int | None, list[Folder]],
    materials_by_folder: dict[int | None, list[Material]],
) -> dict:
    """递归构建文件夹树节点。"""
    return {
        "id": folder.id,
        "name": folder.name,
        "type": "folder",
        "children": [
            _build_folder_node(c, children_map, materials_by_folder)
            for c in sorted(children_map.get(folder.id, []), key=lambda x: x.name)
        ],
        "materials": [
            {"id": m.id, "title": m.title, "status": m.status, "type": "material"}
            for m in materials_by_folder.get(folder.id, [])
        ],
    }


@router.get("/tree")
def get_tree(db: Session = Depends(get_db)) -> dict:
    """获取完整树状导航数据（根级文件夹 + 根级素材）。"""
    folders = db.query(Folder).all()
    materials = db.query(Material).order_by(Material.created_at.desc()).all()

    children_map = _folder_children_map(folders)
    materials_by_folder: dict[int | None, list[Material]] = {}
    for m in materials:
        materials_by_folder.setdefault(m.folder_id, []).append(m)

    root_folders = [
        _build_folder_node(f, children_map, materials_by_folder)
        for f in sorted(children_map.get(None, []), key=lambda x: x.name)
    ]
    root_materials = [
        {"id": m.id, "title": m.title, "status": m.status, "type": "material"}
        for m in materials_by_folder.get(None, [])
    ]
    return {"folders": root_folders, "materials": root_materials}


@router.post("/folders")
def create_folder(payload: FolderCreate, db: Session = Depends(get_db)) -> dict:
    """新建文件夹。"""
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "文件夹名称不能为空")
    if payload.parent_id is not None and db.get(Folder, payload.parent_id) is None:
        raise HTTPException(404, "父文件夹不存在")
    folder = Folder(name=name, parent_id=payload.parent_id)
    db.add(folder)
    db.commit()
    return {"id": folder.id, "name": folder.name, "parent_id": folder.parent_id}


@router.put("/folders/{folder_id}")
def rename_folder(
    folder_id: int, payload: FolderRename, db: Session = Depends(get_db)
) -> dict:
    """重命名文件夹。"""
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(404, "文件夹不存在")
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "文件夹名称不能为空")
    folder.name = name
    db.commit()
    return {"id": folder.id, "name": folder.name}


@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, db: Session = Depends(get_db)) -> dict:
    """删除文件夹（级联删除子文件夹与素材记录）。"""
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(404, "文件夹不存在")
    db.delete(folder)
    db.commit()
    return {"ok": True}
