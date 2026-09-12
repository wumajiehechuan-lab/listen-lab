"""LLM 服务（OpenAI 兼容接口）：逐句翻译 + 提取重点单词。

支持 DeepSeek 官方、火山/阿里 Coding Plan、腾讯混元及任意 OpenAI 兼容端点，
具体服务商在设置页切换。
"""
import json
import re

from openai import OpenAI

from app.config import settings

MAX_KEYWORDS = 20


class LLMError(Exception):
    """LLM 调用失败异常。"""


def _extract_json(text: str) -> dict:
    """从模型输出中提取 JSON 对象（兼容 ```json 代码块包裹）。"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise LLMError("LLM 输出中未找到 JSON")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM 输出 JSON 解析失败: {exc}") from exc


def translate_and_extract(sentences: list[str]) -> tuple[list[str], list[dict]]:
    """对英文字幕逐句翻译并提取重点单词。

    Args:
        sentences: 英文字幕句子列表（按序）。

    Returns:
        (translations, keywords)
        translations: 与输入等长的中文翻译列表。
        keywords: [{"word", "phonetic", "pos", "meaning_zh", "seq"}, ...]

    Raises:
        LLMError: 密钥缺失或调用/解析失败。
    """
    if not settings.llm_api_key:
        raise LLMError("未配置 LLM API Key，请在「模型设置」中填写")

    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))
    prompt = (
        "你是一位英语教学专家。以下是按序号排列的一段英文视频字幕：\n\n"
        f"{numbered}\n\n"
        "请完成两项任务，并严格以 JSON 格式返回（不要输出任何其他文字）：\n"
        '1. "translations": 数组，逐句给出通顺的中文翻译，长度必须与输入句子数一致，顺序对应。\n'
        '2. "keywords": 数组，挑选 10~20 个对学习者有价值的重点单词或短语（四六级/考研难度优先），'
        "每项包含：\n"
        '   - "word": 单词或短语原型（小写）\n'
        '   - "phonetic": 音标（英式，如 /əˈfektɪŋ/）\n'
        '   - "pos": 词性缩写（如 v. / n. / adj. / phr.）\n'
        '   - "meaning_zh": 简明中文释义（可含多个义项，用；分隔）\n'
        '   - "seq": 该词首次出现的句子序号（从 1 开始）\n'
        "示例格式：\n"
        '{"translations": ["第一句翻译", "第二句翻译"], '
        '"keywords": [{"word": "affect", "phonetic": "/əˈfekt/", "pos": "v.", '
        '"meaning_zh": "影响", "seq": 1}]}'
    )

    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=180.0,
    )
    kwargs = dict(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    try:
        # 部分服务商不支持 response_format，失败时降级重试
        try:
            resp = client.chat.completions.create(
                response_format={"type": "json_object"}, **kwargs
            )
        except Exception:
            resp = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise LLMError(f"LLM 调用失败: {exc}") from exc

    data = _extract_json(resp.choices[0].message.content or "")

    translations = data.get("translations") or []
    if len(translations) != len(sentences):
        # 长度不一致时按索引兜底，缺失处留空
        translations = [
            translations[i] if i < len(translations) else ""
            for i in range(len(sentences))
        ]

    keywords = []
    for item in (data.get("keywords") or [])[:MAX_KEYWORDS]:
        word = str(item.get("word", "")).strip().lower()
        if not word:
            continue
        seq = item.get("seq")
        keywords.append(
            {
                "word": word,
                "phonetic": str(item.get("phonetic", "") or ""),
                "pos": str(item.get("pos", "") or ""),
                "meaning_zh": str(item.get("meaning_zh", "") or ""),
                "seq": int(seq) if isinstance(seq, (int, float)) else None,
            }
        )
    return translations, keywords
