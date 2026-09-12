"""SQLAlchemy 数据模型：文件夹、素材、字幕、重点单词。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """ORM 基类。"""


class Folder(Base):
    """树状导航文件夹。"""

    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("folders.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    children: Mapped[list["Folder"]] = relationship(
        "Folder", back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped["Folder | None"] = relationship(
        "Folder", back_populates="children", remote_side=[id]
    )
    materials: Mapped[list["Material"]] = relationship(
        "Material", back_populates="folder", cascade="all, delete-orphan"
    )


class Material(Base):
    """听读素材（一个视频对应一条素材）。"""

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    folder_id: Mapped[int | None] = mapped_column(
        ForeignKey("folders.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    video_path: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_sec: Mapped[float | None] = mapped_column(nullable=True)
    # processing / ready / failed
    status: Mapped[str] = mapped_column(String(20), default="processing")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    folder: Mapped["Folder | None"] = relationship("Folder", back_populates="materials")
    subtitles: Mapped[list["Subtitle"]] = relationship(
        "Subtitle", back_populates="material", cascade="all, delete-orphan",
        order_by="Subtitle.seq",
    )
    keywords: Mapped[list["Keyword"]] = relationship(
        "Keyword", back_populates="material", cascade="all, delete-orphan"
    )


class Subtitle(Base):
    """字幕句子（句级时间戳）。"""

    __tablename__ = "subtitles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, nullable=False)
    text_zh: Mapped[str | None] = mapped_column(Text, nullable=True)

    material: Mapped["Material"] = relationship("Material", back_populates="subtitles")


class Keyword(Base):
    """重点单词卡片。"""

    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    word: Mapped[str] = mapped_column(String(100), nullable=False)
    phonetic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pos: Mapped[str | None] = mapped_column(String(50), nullable=True)
    meaning_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtitle_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)

    material: Mapped["Material"] = relationship("Material", back_populates="keywords")
