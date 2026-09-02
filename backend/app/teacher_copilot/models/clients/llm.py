"""LLM 客户端:DeepSeek Anthropic Messages API + mock 退路。

按用户实际接入(2026-09-02):
- base url: https://api.deepseek.com/anthropic
- 协议:Anthropic Messages (/v1/messages)
- 模型:deepseek-v4-flash(数学 easy/medium/hard 与英语作文均使用,单一密钥)
密钥未配置时走 mock(返回预设确定性输出),保证本地链路可跑通。
所有真实调用记录"开始/完成/耗时"(宪法 IX/X)。
"""

from __future__ import annotations

import json
import logging
import re
import time

import httpx

from app.teacher_copilot.config.settings import get_config

logger = logging.getLogger("teacher_copilot.llm")


def _parse_json_robust(text: str) -> dict:
    """容错解析模型 JSON:支持无包裹 JSON / ```json 块 / 说明文字+JSON。

    嵌套 JSON 用堆栈匹配外层大括号(非贪婪正则会截断嵌套结构)。
    """
    raw = text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 2) 提取 ```json ... ``` 代码块(取最后一个 ``` 块)
    code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass
    # 3) 堆栈匹配首个 { 到配对 } 的子串(处理任意嵌套)
    start = raw.find("{")
    if start >= 0:
        depth = 0
        end = -1
        in_str = False
        escape = False
        for i in range(start, len(raw)):
            ch = raw[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError(f"模型输出不是合法 JSON: {raw[:200]}")


class LlmClient:
    """统一 LLM 客户端(配置了密钥 → 云端 Anthropic Messages;未配置 → mock)。"""

    def __init__(self) -> None:
        self._cfg = get_config()

    async def generate(self, *, prompt: str, system: str = "") -> str:
        """调用模型生成文本(Anthropic Messages 协议)。"""
        if not self._cfg.llm_api_key:
            return '{"_mock": true}'
        return await self._generate_anthropic(prompt, system)

    async def generate_json(self, *, model_kind: str = "strong", prompt: str, system: str = "") -> dict:
        """调用模型并强制 JSON 输出(与既有调用方兼容;system 透传)。

        模型偶发空/截断响应:空文本重试 1 次(宪法 X:记录重试)。
        """
        text = await self.generate(prompt=prompt, system=system)
        if not text.strip():
            logger.warning("LLM 返回空文本,重试 1 次, prompt_len=%d", len(prompt))
            text = await self.generate(prompt=prompt, system=system)
        return _parse_json_robust(text)

    async def _generate_anthropic(self, prompt: str, system: str) -> str:
        """真实调用 DeepSeek Anthropic Messages API(记录开始/完成/耗时)。"""
        t0 = time.time()
        logger.info("LLM 请求开始: model=%s, prompt_len=%d", self._cfg.llm_model, len(prompt))
        resp = await httpx.AsyncClient(timeout=self._cfg.llm_timeout).post(
            self._cfg.llm_api_base.rstrip("/") + "/v1/messages",
            headers={
                "x-api-key": self._cfg.llm_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self._cfg.llm_model,
                "max_tokens": 4096,
                "temperature": 0.2,
                "system": system or "你是数学/英语批改助手,严格按给定 JSON 格式输出。",
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        logger.info("LLM 请求完成: 耗时 %.1fs, status=%s", time.time() - t0, resp.status_code)
        resp.raise_for_status()
        data = resp.json()
        # Anthropic:content 为 block 数组,取 text 拼接
        blocks = data.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    @property
    def is_mock(self) -> bool:
        """当前是否处于 mock 模式(无真实密钥)。"""
        return not self._cfg.llm_api_key
