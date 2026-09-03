"""Teacher Copilot 配置模块。

配置来源:环境变量(前缀 TC_)。为本地开发与演示提供合理默认值:
- 数据库:默认 SQLite 文件(零外部依赖),可切 MySQL 异步方言
- LLM:DeepSeek Anthropic Messages API(base url https://api.deepseek.com/anthropic,
  model deepseek-v4-flash);数学 easy/medium 与 hard 均用同一模型(按用户提供的密钥)
- OCR:智谱 GLM-OCR(zai-sdk);密钥未配置时由调用方按宪法 VII 上报并使用 mock
- 评测:可选 Langfuse(不强制)

真实密钥由用户提供(2026-09-02),经环境变量注入,不硬编码在代码中。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    """读取环境变量 TC_<name>,未设置时返回默认值。"""
    return os.environ.get(f"TC_{name}", default)


@dataclass
class AppConfig:
    """Teacher Copilot 全局配置(所有字段可经环境变量覆盖)。"""

    # ----- 数据库(唯一业务事实源) -----
    database_url: str = field(
        default_factory=lambda: _env(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{Path(_env('DATA_DIR', 'tc-data')) / 'teacher_copilot.db'}",
        )
    )
    database_echo: bool = field(
        default_factory=lambda: _env("DATABASE_ECHO", "0") == "1"
    )

    # ----- Redis(画像缓存) -----
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", "redis://127.0.0.1:6379/0"))
    redis_enabled: bool = field(default_factory=lambda: _env("REDIS_ENABLED", "0") == "1")

    # ----- LLM:DeepSeek Anthropic Messages API(用户已提供密钥) -----
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY"))
    llm_api_base: str = field(
        default_factory=lambda: _env("LLM_API_BASE", "https://api.deepseek.com/anthropic")
    )
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "deepseek-v4-flash"))
    llm_timeout: float = field(default_factory=lambda: float(_env("LLM_TIMEOUT", "300")))

    # ----- OCR:智谱 GLM-OCR(zai-sdk) -----
    ocr_api_key: str = field(default_factory=lambda: _env("OCR_API_KEY"))
    ocr_model: str = field(default_factory=lambda: _env("OCR_MODEL", "glm-ocr"))

    # ----- 阿里云 OSS(图片上传,卡点:AK/SK 待用户提供) -----
    oss_access_key_id: str = field(default_factory=lambda: _env("OSS_ACCESS_KEY_ID"))
    oss_access_key_secret: str = field(default_factory=lambda: _env("OSS_ACCESS_KEY_SECRET"))
    oss_bucket: str = field(default_factory=lambda: _env("OSS_BUCKET"))
    oss_endpoint: str = field(default_factory=lambda: _env("OSS_ENDPOINT"))

    # ----- 评测(可选) -----
    langfuse_enabled: bool = field(default_factory=lambda: _env("LANGFUSE_ENABLED", "0") == "1")

    @property
    def has_real_llm(self) -> bool:
        """是否已配置真实 LLM 密钥(否则批改走 mock 退路)。"""
        return bool(self.llm_api_key)

    @property
    def has_real_ocr(self) -> bool:
        """OCR 密钥是否已配置(未配置时 OcrClient 走 mock)。"""
        return bool(self.ocr_api_key)


# 模块级单例:各模块统一从 get_config() 获取,避免重复解析环境变量
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """获取(惰性初始化)全局配置单例。"""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config
