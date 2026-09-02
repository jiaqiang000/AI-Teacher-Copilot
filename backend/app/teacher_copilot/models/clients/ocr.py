"""OCR 客户端:智谱 GLM-OCR 布局解析(真实接入)。

SDK:zai-sdk(ZhipuAiClient.layout_parsing.create)。
- file 参数支持 URL 或 base64 编码图片(≤10MB)
- 响应:md_results + layout_details(List[List[LayoutDetail]])
  LayoutDetail 字段:index/label/bbox_2d/content/height/width
- 密钥未配置时走 mock(返回单 Block 结构),保证本地链路可演示

【待办】公网图片 URL(2026-09-02 用户确认方案):智谱服务器仅能访问公网
可下载 URL;本地文件/base64 对简单图返回空。学生上传图片须先传至
阿里云 OSS 等对象存储并取得公网链接,再作为 file 参数传入(见 tasks.md 待办)。
"""

from __future__ import annotations

import base64
from typing import Any

from app.teacher_copilot.config.settings import get_config


class OcrClient:
    """OCR 客户端(OCR_API_KEY 未配置 → mock 结果)。"""

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
        """
        if not self._cfg.ocr_api_key:
            return self._mock_recognize()
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

    def _mock_recognize(self) -> dict[str, Any]:
        """mock 识别:返回单 Block 的公式文本与占位坐标(与真实结构一致)。"""
        return {
            "md_results": (
                "[Block 1 | text]\nAnswer: Let x be the unknown.\n\n"
                "[Block 2 | formula]\n$$ 2x + 4 = 8 $$\n\n"
                "[Block 3 | text]\nThen, by transposition,\n\n"
                "[Block 4 | formula]\n$$ x = 2 $$\n"
            ),
            "layout_details": [
                {"index": 1, "label": "text", "content": "Answer: Let x be the unknown.",
                 "bbox2d": [0, 0, 100, 40], "width": 100, "height": 600},
                {"index": 2, "label": "formula", "content": "$$ 2x + 4 = 8 $$",
                 "bbox2d": [0, 40, 100, 80], "width": 100, "height": 600},
                {"index": 3, "label": "text", "content": "Then, by transposition,",
                 "bbox2d": [0, 80, 100, 120], "width": 100, "height": 600},
                {"index": 4, "label": "formula", "content": "$$ x = 2 $$",
                 "bbox2d": [0, 120, 100, 160], "width": 100, "height": 600},
            ],
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
