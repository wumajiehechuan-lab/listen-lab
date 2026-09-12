"""豆包录音文件识别极速版客户端：同步识别本地音频并返回句级时间戳。

采用新版控制台鉴权（单个 X-Api-Key），音频以 base64 直传，
一次请求即返回结果，无需 submit/query 轮询。
"""
import base64
import uuid
from pathlib import Path

import httpx

from app.config import settings

API_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
# 豆包录音文件识别模型 2.0（flash 端点同样支持该资源，base64 直传免 URL）
RESOURCE_ID = "volc.seedasr.auc"
SUCCESS_CODE = "20000000"


class ASRError(Exception):
    """语音识别失败异常。"""


def transcribe_audio(audio_path: Path, language: str = "en-US") -> list[dict]:
    """识别音频文件，返回句级字幕列表。

    Args:
        audio_path: 16k 单声道 WAV 音频路径（100MB / 2 小时以内）。
        language: 识别语言，默认英语 en-US。

    Returns:
        [{"start_ms": int, "end_ms": int, "text": str}, ...] 按时间排序。

    Raises:
        ASRError: 配置缺失、网络或服务端错误。
    """
    if not settings.volc_api_key:
        raise ASRError("未配置语音识别 API Key，请在「模型设置」中填写火山引擎语音 API Key")

    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    payload = {
        "user": {"uid": "listen-lab"},
        "audio": {"format": "wav", "codec": "raw", "data": audio_b64},
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "show_utterances": True,
            "language": language,
        },
    }
    headers = {
        "X-Api-Key": settings.volc_api_key,
        "X-Api-Resource-Id": RESOURCE_ID,
        "X-Api-Request-Id": str(uuid.uuid4()),
        "X-Api-Sequence": "-1",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
            resp = client.post(API_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise ASRError(f"识别服务网络错误: {exc}") from exc

    status_code = resp.headers.get("X-Api-Status-Code", "")
    if status_code != SUCCESS_CODE:
        message = resp.headers.get("X-Api-Message", "未知错误")
        raise ASRError(
            f"识别失败 [{status_code}]: {message}"
            "（若为鉴权错误，请确认控制台已开通「豆包录音文件识别模型」）"
        )

    result = resp.json().get("result", {})
    utterances = result.get("utterances") or []
    subtitles = [
        {
            "start_ms": int(u.get("start_time", 0)),
            "end_ms": int(u.get("end_time", 0)),
            "text": u.get("text", "").strip(),
        }
        for u in utterances
        if u.get("text", "").strip()
    ]
    if not subtitles:
        # 无分句时回退为整段文本
        full_text = result.get("text", "").strip()
        if not full_text:
            raise ASRError("识别结果为空，请确认音频包含英文语音")
        subtitles = [{"start_ms": 0, "end_ms": 0, "text": full_text}]
    return subtitles
