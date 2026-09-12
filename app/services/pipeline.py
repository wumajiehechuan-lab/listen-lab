"""素材生成流水线：提取音频 → 语音识别 → 翻译/重点词 → 入库。"""
import json
import subprocess
from pathlib import Path

from app.config import MEDIA_DIR
from app.database import SessionLocal
from app.models import Keyword, Material, Subtitle
from app.services import asr, llm


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """用 ffmpeg 从视频提取 16kHz 单声道 WAV 音频。"""
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 提取音频失败: {proc.stderr[-500:]}")


def probe_duration(video_path: Path) -> float | None:
    """用 ffprobe 获取视频时长（秒）。"""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(video_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return float(json.loads(proc.stdout)["format"]["duration"])
    except (ValueError, KeyError, json.JSONDecodeError):
        pass
    return None


def run_pipeline(material_id: int) -> None:
    """执行素材生成流水线（在后台线程中运行）。

    任何步骤失败都会将素材状态置为 failed 并记录错误信息。
    """
    db = SessionLocal()
    try:
        material = db.get(Material, material_id)
        if material is None:
            return

        media_dir = MEDIA_DIR / str(material_id)
        video_path = Path(material.video_path)
        audio_path = media_dir / "audio.wav"

        # 1. 提取音频与时长
        extract_audio(video_path, audio_path)
        material.duration_sec = probe_duration(video_path)
        db.commit()

        # 2. 语音识别
        utterances = asr.transcribe_audio(audio_path)

        # 3. 翻译 + 重点词
        sentences = [u["text"] for u in utterances]
        try:
            translations, keywords = llm.translate_and_extract(sentences)
        except llm.LLMError as exc:
            # LLM 失败不阻断素材生成，仅记录
            translations = [""] * len(sentences)
            keywords = []
            material.error_msg = f"翻译/重点词生成失败: {exc}"

        # 4. 入库
        for i, u in enumerate(utterances):
            db.add(Subtitle(
                material_id=material_id,
                seq=i + 1,
                start_ms=u["start_ms"],
                end_ms=u["end_ms"],
                text_en=u["text"],
                text_zh=translations[i] if i < len(translations) else "",
            ))
        for kw in keywords:
            db.add(Keyword(
                material_id=material_id,
                word=kw["word"],
                phonetic=kw["phonetic"],
                pos=kw["pos"],
                meaning_zh=kw["meaning_zh"],
                subtitle_seq=kw.get("seq"),
            ))

        material.status = "ready"
        db.commit()
    except Exception as exc:
        db.rollback()
        material = db.get(Material, material_id)
        if material is not None:
            material.status = "failed"
            material.error_msg = str(exc)[:1000]
            db.commit()
    finally:
        db.close()
