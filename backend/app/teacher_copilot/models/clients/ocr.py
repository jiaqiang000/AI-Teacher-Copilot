"""OCR 客户端:智谱 GLM-OCR 布局解析(真实接入)。

SDK:zai-sdk(ZhipuAiClient.layout_parsing.create)。
- file 参数支持 URL 或 base64 编码图片(≤10MB)
- 响应:md_results + layout_details(List[List[LayoutDetail]])
  LayoutDetail 字段:index/label/bbox_2d/content/height/width
- 密钥未配置时**显式失败**(抛 OcrNotConfigured),不再返回硬编码的占位识别文本:
  该文本刻意对齐了评测金标准(含"移项"与 2x+4=8),返回它会让假数据看起来"正确"(008 FR-004)

【待办】公网图片 URL(2026-09-02 用户确认方案):智谱服务器仅能访问公网
可下载 URL;本地文件/base64 对简单图返回空。学生上传图片须先传至
阿里云 OSS 等对象存储并取得公网链接,再作为 file 参数传入(见 tasks.md 待办)。
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from app.teacher_copilot.config.settings import get_config
from app.teacher_copilot.errors import OcrNotConfigured

logger = logging.getLogger("teacher_copilot.ocr")


class OcrClient:
    """OCR 客户端(OCR_API_KEY 未配置 → 抛 OcrNotConfigured)。"""

    def __init__(self) -> None:
        self._cfg = get_config()

    def _make_client(self) -> Any:
        """构造智谱客户端(兼容 SDK 版本差异:顶层导出失败则取子模块)。"""
        try:
            from zai import ZhipuAiClient  # type: ignore
        except ImportError:
            from zai._client import ZhipuAiClient  # type: ignore
        return ZhipuAiClient(api_key=self._cfg.ocr_api_key)

    async def recognize(self, image_path: str, image_url: str | None = None) -> dict[str, Any]:
        """识别单张图片,返回 {md_results, layout_details}。

        image_path: 本地文件路径(转 base64 data URL);
        image_url: 提供时优先使用远程 URL(与参考设计一致)。

        未配置密钥时显式失败(008 FR-004):禁止返回占位识别文本,
        否则下游会拿到"结构完整、内容正确"的假识别结果。
        """
        if not self._cfg.ocr_api_key:
            logger.error(
                "OCR 未配置密钥,拒绝识别: model=%s, image_path=%s, image_url=%s;"
                " 请配置 TC_OCR_API_KEY 后重试",
                self._cfg.ocr_model, image_path, image_url,
            )
            raise OcrNotConfigured(
                f"识别未配置密钥(TC_OCR_API_KEY),无法完成识别;model={self._cfg.ocr_model}"
            )
        if image_url:
            file_arg = image_url
        else:
            with open(image_path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
            file_arg = f"data:image/jpeg;base64,{b64}"

        # zai SDK 为同步调用,用线程包装避免阻塞事件循环
        return await _run_in_thread(self._recognize_sync, file_arg)

    def _recognize_sync(self, file_arg: str) -> dict[str, Any]:
        client = self._make_client()
        resp = client.layout_parsing.create(model=self._cfg.ocr_model, file=file_arg)
        # layout_details 外层可能是多页列表;单图片取第一页
        pages = resp.layout_details or []
        blocks = _normalize_blocks(pages[0] if pages else [])
        return {
            "md_results": resp.md_results or "",
            "layout_details": blocks,
        }


async def _run_in_thread(fn, *args) -> Any:
    """在线程中执行同步 SDK 调用。"""
    import asyncio

    return await asyncio.to_thread(fn, *args)


def _normalize_blocks(page: list) -> list[dict]:
    """把 SDK 的 LayoutDetail(bbox_2d)转换为内部 bbox2d 约定。"""
    out = []
    for b in page:
        bbox = getattr(b, "bbox_2d", None)
        out.append({
            "index": b.index,
            "label": b.label,
            "content": b.content or "",
            "bbox2d": list(bbox) if bbox else None,
            "width": b.width,
            "height": b.height,
        })
    return out
