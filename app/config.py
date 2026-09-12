"""应用配置模块：从 .env 读取密钥，定义全局路径。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（listen-lab/）
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MEDIA_DIR = DATA_DIR / "media"
EXPORT_DIR = DATA_DIR / "exports"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = DATA_DIR / "app.db"


class Settings(BaseSettings):
    """应用配置，从 .env 文件加载。"""

    # ASR（火山引擎语音识别）
    volc_app_id: str = ""
    volc_access_token: str = ""
    # LLM（OpenAI 兼容接口：DeepSeek / 各家 Coding Plan / 混元 / 自定义）
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")


settings = Settings()

# 确保数据目录存在
for _dir in (DATA_DIR, MEDIA_DIR, EXPORT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
