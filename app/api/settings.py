"""模型接入配置 API：读取/保存密钥到 .env，并即时更新运行时配置。

LLM 侧支持服务商预设切换：所有预设均为 OpenAI 兼容端点，
切换预设只需替换 base_url / api_key / model。
"""
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import BASE_DIR, settings

router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_PATH = BASE_DIR / ".env"

# LLM 服务商预设（均为 OpenAI 兼容端点）
LLM_PRESETS: dict[str, dict] = {
    "deepseek": {
        "label": "DeepSeek 官方（按量）",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "note": "按 token 计费，价格低，适合日常使用。",
    },
    "volc_coding": {
        "label": "火山方舟 Coding Plan",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model": "doubao-seed-2.0-code",
        "note": "包月套餐。可用 doubao-seed / kimi-k2.5 / glm-4.7 / deepseek-v3.2 等，以套餐内模型清单为准。",
    },
    "ali_coding": {
        "label": "阿里百炼 Coding Plan",
        "base_url": "https://coding.dashscope.aliyuncs.com/v1",
        "model": "",
        "note": "需使用 Coding Plan 专属 API Key（非百炼通用 sk- Key）。注意：阿里官方条款限定套餐仅限编程工具场景使用。",
    },
    "tencent": {
        "label": "腾讯混元（按量）",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "model": "hunyuan-lite",
        "note": "按量付费，hunyuan-lite 免费额度可用。",
    },
    "custom": {
        "label": "自定义（OpenAI 兼容）",
        "base_url": "",
        "model": "",
        "note": "任何 OpenAI 兼容的端点都可以接入。",
    },
}

# 前端字段名 → (env 键, settings 属性, 显示名)
CONFIG_FIELDS: dict[str, tuple[str, str, str]] = {
    "volc_app_id": ("VOLC_APP_ID", "volc_app_id", "火山引擎 App ID"),
    "volc_access_token": ("VOLC_ACCESS_TOKEN", "volc_access_token", "火山引擎 Access Token"),
    "llm_provider": ("LLM_PROVIDER", "llm_provider", "LLM 服务商"),
    "llm_api_key": ("LLM_API_KEY", "llm_api_key", "LLM API Key"),
    "llm_base_url": ("LLM_BASE_URL", "llm_base_url", "Base URL"),
    "llm_model": ("LLM_MODEL", "llm_model", "模型"),
}

SECRET_FIELDS = {"volc_access_token", "llm_api_key"}


class SettingsUpdate(BaseModel):
    """配置更新请求体（空字符串表示不修改该项，llm_provider 除外）。"""

    volc_app_id: str = ""
    volc_access_token: str = ""
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""


def _mask(value: str) -> str:
    """敏感字段脱敏预览：保留前 3 位。"""
    if not value:
        return ""
    return value[:3] + "***" if len(value) > 3 else "***"


@router.get("")
def get_settings() -> dict:
    """获取当前配置状态（敏感字段仅返回脱敏预览，不回传明文）及 LLM 预设列表。"""
    fields = {}
    for field, (_, attr, label) in CONFIG_FIELDS.items():
        value = getattr(settings, attr, "")
        # 模板占位符（your_xxx）视为未配置
        configured = bool(value) and not value.startswith("your_")
        fields[field] = {
            "label": label,
            "configured": configured,
            "secret": field in SECRET_FIELDS,
            # 敏感字段只给脱敏预览，非敏感字段回传完整值便于编辑
            "value": (_mask(value) if field in SECRET_FIELDS else value) if configured else "",
        }
    return {"fields": fields, "presets": LLM_PRESETS}


@router.post("")
def update_settings(payload: SettingsUpdate) -> dict:
    """保存配置：写入 .env 并即时更新运行时 settings，无需重启。"""
    updates = payload.model_dump()
    changed: dict[str, str] = {}
    for field, value in updates.items():
        value = value.strip()
        # llm_provider 必须落在预设集合内，其余字段空字符串表示不修改
        if field == "llm_provider":
            if value in LLM_PRESETS:
                changed[field] = value
        elif value:
            changed[field] = value

    if changed:
        # 读取现有 .env，替换/追加对应键
        lines: list[str] = []
        if ENV_PATH.exists():
            lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        env_map: dict[str, int] = {}
        for i, line in enumerate(lines):
            if "=" in line and not line.strip().startswith("#"):
                env_map[line.split("=", 1)[0].strip()] = i

        for field, value in changed.items():
            env_key, attr, _ = CONFIG_FIELDS[field]
            entry = f"{env_key}={value}"
            if env_key in env_map:
                lines[env_map[env_key]] = entry
            else:
                lines.append(entry)
            # 即时更新运行时配置
            setattr(settings, attr, value)

        ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"ok": True, "updated": list(changed.keys())}
