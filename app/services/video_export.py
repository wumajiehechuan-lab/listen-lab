"""视频导出服务：将精听页面渲染为合成视频。

页面帧用 Pillow 逐句渲染（顶部视频区 + 字幕区当前句高亮 + 右侧单词卡片栏），
再用 ffmpeg 将原视频逐段叠加到帧上并合成完整 MP4（含原音频）。
"""
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import EXPORT_DIR

# 导出任务状态：material_id -> {"status": ..., "path": ..., "error": ...}
export_jobs: dict[int, dict] = {}

# ===== 画布布局常量（Apple 风格，与网页端一致） =====
WIDTH, HEIGHT = 1920, 1080
BLUE = "#007aff"
CARD_BG = "#f7f7fa"      # 当前句卡片底 / 侧栏底
INK = "#1d1d1f"
GRAY = "#8e8e93"
BORDER = "#e5e5ea"
BG = "#ffffff"
PANEL_BG = "#f7f7fa"
RADIUS = 18

FONT_BOLD_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",   # 微软雅黑 Bold
    "C:/Windows/Fonts/msyh.ttc",
]

VIDEO_X, VIDEO_Y, VIDEO_W = 40, 110, 1180
VIDEO_H = int(VIDEO_W * 9 / 16)  # 664
SUB_Y = VIDEO_Y + VIDEO_H + 24  # 字幕区起始 y
WORD_X, WORD_W = 1270, 610  # 右侧单词栏

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑（中英文）
    "C:/Windows/Fonts/simhei.ttf",    # 黑体兜底
]
FONT_LATIN_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",   # 音标等拉丁扩展字符
    "C:/Windows/Fonts/arial.ttf",
]


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    """按候选顺序加载第一个可用的字体。"""
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap_en(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[list[str]]:
    """英文按词换行，返回每行的词列表。"""
    words = text.split()
    lines: list[list[str]] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if draw.textlength(trial, font=font) <= max_width or not current:
            current.append(word)
        else:
            lines.append(current)
            current = [word]
    if current:
        lines.append(current)
    return lines


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """中文/通用文本按字符换行。"""
    lines: list[str] = []
    current = ""
    for ch in text:
        if draw.textlength(current + ch, font=font) <= max_width or not current:
            current += ch
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def _clean_word(word: str) -> str:
    """清洗单词：去标点、小写。"""
    return re.sub(r"[^\w'-]", "", word).lower()


def _is_keyword(word: str, keyword_set: set[str]) -> bool:
    """判断单词是否为重点词（支持变形匹配，如 operate ↔ operates）。"""
    w = _clean_word(word)
    if not w:
        return False
    if w in keyword_set:
        return True
    # 双向前缀匹配（双方最短 4 字符，避免 "a" 匹配 "affecting" 这类误判）
    return len(w) >= 4 and any(
        len(kw) >= 4 and (w.startswith(kw) or kw.startswith(w))
        for kw in keyword_set
    )


def _draw_en_line(
    draw: ImageDraw.ImageDraw,
    words: list[str],
    x: int,
    y: int,
    font,
    color: str,
    keyword_set: set[str],
    kw_color: str,
) -> None:
    """逐词绘制一行英文，重点词高亮为红色。"""
    cursor = x
    space_w = draw.textlength(" ", font=font)
    for word in words:
        is_kw = _is_keyword(word, keyword_set)
        w_color = kw_color if is_kw else color
        draw.text((cursor, y), word, font=font, fill=w_color)
        if is_kw:
            # 重点词下划线
            w_w = draw.textlength(word, font=font)
            draw.line([(cursor, y + font.size + 6), (cursor + w_w, y + font.size + 6)],
                      fill=kw_color, width=3)
        cursor += draw.textlength(word, font=font) + space_w


def render_frame(subtitles: list, keywords: list, current_idx: int, out_path: Path) -> None:
    """渲染某一页帧：当前句高亮 + 上下句预览 + 右侧单词卡片栏。

    Args:
        subtitles: 字幕对象列表（需有 start_ms/end_ms/text_en/text_zh）。
        keywords: 重点词对象列表（需有 word/phonetic/pos/meaning_zh）。
        current_idx: 当前播放句索引。
        out_path: 输出 PNG 路径。
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    font_en = _load_font(FONT_BOLD_CANDIDATES, 38)  # 当前句英文用粗体
    font_en_small = _load_font(FONT_CANDIDATES, 24)
    font_zh = _load_font(FONT_CANDIDATES, 26)
    font_word = _load_font(FONT_CANDIDATES, 30)
    font_phonetic = _load_font(FONT_LATIN_CANDIDATES, 22)
    font_pos = _load_font(FONT_CANDIDATES, 20)

    # 顶栏（白底 + 细分隔线，「精听」加粗 + 副标题灰色）
    draw.rectangle([0, 0, WIDTH, 90], fill="#ffffff")
    draw.line([(0, 89), (WIDTH, 89)], fill=BORDER, width=2)
    font_brand = _load_font(FONT_CANDIDATES, 34)
    draw.text((40, 24), "精听", font=font_brand, fill=INK)
    brand_w = draw.textlength("精听", font=font_brand)
    draw.text((40 + brand_w + 24, 30), "英语听读素材库",
              font=_load_font(FONT_CANDIDATES, 24), fill=GRAY)

    # 视频区（黑色占位，ffmpeg 将原视频叠加到此区域）
    draw.rectangle([VIDEO_X, VIDEO_Y, VIDEO_X + VIDEO_W, VIDEO_Y + VIDEO_H], fill="#000000")

    keyword_set = {_clean_word(k.word) for k in keywords}
    max_text_w = VIDEO_W - 80

    # ===== 字幕区：上一句（灰） + 当前句（高亮） + 下一句（灰） =====
    y = SUB_Y
    if current_idx > 0:
        prev = subtitles[current_idx - 1].text_en
        for line in _wrap_text(draw, prev, font_en_small, max_text_w)[:1]:
            draw.text((VIDEO_X + 20, y), line, font=font_en_small, fill=GRAY)
            y += 34
        y += 6

    # 当前句：浅灰圆角卡片 + 左侧蓝色竖条（先画蓝底圆角，再用卡片色覆盖右侧）
    cur = subtitles[current_idx]
    en_lines = _wrap_en(draw, cur.text_en, font_en, max_text_w)
    box_h = len(en_lines) * 52 + 20
    zh_lines: list[str] = []
    if cur.text_zh:
        zh_lines = _wrap_text(draw, cur.text_zh, font_zh, max_text_w)
        box_h += len(zh_lines) * 36 + 8
    draw.rounded_rectangle(
        [VIDEO_X, y, VIDEO_X + VIDEO_W, y + box_h], radius=RADIUS, fill=BLUE
    )
    draw.rounded_rectangle(
        [VIDEO_X + 8, y, VIDEO_X + VIDEO_W, y + box_h],
        radius=RADIUS - 4, fill=CARD_BG,
    )

    ty = y + 10
    for line_words in en_lines:
        _draw_en_line(draw, line_words, VIDEO_X + 28, ty, font_en, INK, keyword_set, BLUE)
        ty += 52
    ty += 8
    for line in zh_lines:
        draw.text((VIDEO_X + 28, ty), line, font=font_zh, fill="#6e6e73")
        ty += 36
    y += box_h + 16

    if current_idx + 1 < len(subtitles):
        nxt = subtitles[current_idx + 1].text_en
        for line in _wrap_text(draw, nxt, font_en_small, max_text_w)[:1]:
            if y + 34 < HEIGHT - 20:
                draw.text((VIDEO_X + 20, y), line, font=font_en_small, fill=GRAY)
            y += 34

    # ===== 右侧单词栏（浅灰底 + 白色圆角感卡片） =====
    draw.rectangle([WORD_X - 24, 90, WIDTH, HEIGHT], fill=PANEL_BG)
    draw.line([(WORD_X - 24, 90), (WORD_X - 24, HEIGHT)], fill=BORDER, width=2)
    draw.text((WORD_X, VIDEO_Y), "核心词汇", font=font_word, fill=INK)

    card_y = VIDEO_Y + 56
    for kw in keywords:
        card_h = 118
        if card_y + card_h > HEIGHT - 24:
            break  # 超出画布则截断
        draw.rounded_rectangle(
            [WORD_X, card_y, WORD_X + WORD_W, card_y + card_h],
            radius=RADIUS, outline=BORDER, width=2, fill="#ffffff",
        )
        # 单词（品牌蓝） + 音标
        draw.text((WORD_X + 16, card_y + 12), kw.word, font=font_word, fill=BLUE)
        if kw.phonetic:
            w_w = draw.textlength(kw.word, font=font_word)
            draw.text((WORD_X + 26 + w_w, card_y + 18), kw.phonetic,
                      font=font_phonetic, fill=GRAY)
        # 词性 + 释义
        pos_text = kw.pos or ""
        draw.text((WORD_X + 16, card_y + 58), pos_text, font=font_pos, fill=GRAY)
        if kw.meaning_zh:
            pos_w = draw.textlength(pos_text, font=font_pos) + 10 if pos_text else 0
            meaning_lines = _wrap_text(
                draw, kw.meaning_zh, font_pos, WORD_W - 40 - int(pos_w)
            )[:2]
            my = card_y + 58
            for i, line in enumerate(meaning_lines):
                mx = WORD_X + 16 + (int(pos_w) if i == 0 else 0)
                draw.text((mx, my), line, font=font_pos, fill=INK)
                my += 26
        card_y += card_h + 12

    img.save(out_path)


def _ms_to_sec(ms: int) -> float:
    """毫秒转秒。"""
    return ms / 1000.0


def _render_segment(video_path: str, frame_path: Path, start: float, duration: float,
                    out_path: Path) -> None:
    """用 ffmpeg 将原视频片段叠加到页面帧上，输出一个分段 MP4。"""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", f"{duration:.3f}", "-i", str(frame_path),
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", video_path,
        "-filter_complex",
        f"[1:v]scale={VIDEO_W}:{VIDEO_H}[v];[0:v][v]overlay={VIDEO_X}:{VIDEO_Y}[out]",
        "-map", "[out]",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-an",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"分段渲染失败: {proc.stderr[-400:]}")


def run_export(material_id: int) -> None:
    """后台执行合成导出：逐句渲染页面帧 → 分段叠加 → 合并 → 混入原音频。"""
    from app.database import SessionLocal
    from app.models import Material

    export_jobs[material_id] = {"status": "processing", "path": "", "error": ""}
    db = SessionLocal()
    tmp_dir = EXPORT_DIR / f"tmp_{material_id}"
    try:
        material = db.get(Material, material_id)
        if material is None:
            raise RuntimeError("素材不存在")
        subtitles = list(material.subtitles)
        if not subtitles:
            raise RuntimeError("素材暂无字幕，无法导出")
        keywords = list(material.keywords)
        duration_sec = material.duration_sec or 0

        tmp_dir.mkdir(parents=True, exist_ok=True)

        # 1. 逐句渲染页面帧
        frames = []
        for i in range(len(subtitles)):
            frame_path = tmp_dir / f"frame_{i:04d}.png"
            render_frame(subtitles, keywords, i, frame_path)
            frames.append(frame_path)

        # 2. 分段渲染（4 线程并行）
        segments = []
        jobs = []
        for i, sub in enumerate(subtitles):
            start = _ms_to_sec(sub.start_ms)
            end = _ms_to_sec(sub.end_ms)
            if duration_sec > 0:
                start = min(start, duration_sec)
                end = min(end, duration_sec)
            dur = max(end - start, 0.4)
            seg_path = tmp_dir / f"seg_{i:04d}.mp4"
            segments.append(seg_path)
            jobs.append((start, dur, frames[i], seg_path))

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(_render_segment, material.video_path, frame, start, dur, seg)
                for start, dur, frame, seg in jobs
            ]
            for f in futures:
                f.result()  # 任一分段失败即抛出

        # 3. 合并分段 + 原音频
        concat_list = tmp_dir / "concat.txt"
        concat_list.write_text(
            "".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8"
        )
        out_path = EXPORT_DIR / f"{material_id}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-i", material.video_path,
            "-map", "0:v", "-map", "1:a?",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"合并失败: {proc.stderr[-400:]}")

        export_jobs[material_id] = {"status": "done", "path": str(out_path), "error": ""}
    except Exception as exc:
        export_jobs[material_id] = {"status": "failed", "path": "", "error": str(exc)[:1000]}
    finally:
        db.close()
        if export_jobs[material_id]["status"] == "done" and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
