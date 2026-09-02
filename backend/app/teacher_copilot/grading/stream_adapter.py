"""GradingStreamAdapter:grading.* 事件 → DeerFlow StreamBridge。

复用 DeerFlow StreamBridge 的 publish/subscribe 基础机制(宪法 III):
- publish:通过 Gateway 的 app.state.stream_bridge 同实例发布 grading 事件
- 消费:SSE 端点用 bridge.subscribe(channel) 迭代,再格式化为 SSE 帧
不复制 DeerFlow 的 RunRecord/RunManager 生命周期(Submission 是业务状态,
不是 Agent Run,参考文档 01 §5.2.8.1)。

FastAPI 相关依赖惰性导入:核心 publish 不依赖 FastAPI,
便于在无 gateway 依赖的脚本/测试环境下单独运行 workflow(宪法 X 可观察性)。
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("teacher_copilot.grading.stream")


async def publish_grading_event(
    event_type: str, *, submission_id: str, stage: str = "",
    label: str = "", error_code: str = "", message: str = "",
) -> None:
    """发布 grading.* 事件(与 contracts/grading-api.md 协议一致)。

    无 Bridge(如脚本测试环境)时记录日志并跳过,不阻断批改主流程。
    用 submission_id 作为通道 key,与 DeerFlow run 通道隔离(prefix 防冲突)。
    """
    payload = {
        "type": event_type,
        "submission_id": submission_id,
        "stage": stage,
    }
    if label:
        payload["label"] = label
    if error_code:
        payload["error_code"] = error_code
        payload["message"] = message
    bridge = _current_bridge()
    if bridge is None:
        logger.debug("无 StreamBridge(脚本环境),跳过事件发布: %s", event_type)
        return
    await bridge.publish(
        f"teacher_copilot:{submission_id}",
        event_type,
        json.dumps(payload, ensure_ascii=False),
    )


def _current_bridge():
    """获取当前 Gateway 的 StreamBridge(复用之;失败返回 None 不阻断)。"""
    try:
        import app.gateway.app as gw

        return gw.app.state.stream_bridge  # type: ignore[attr-defined]
    except Exception:
        return None


def grading_event_channel(submission_id: str) -> str:
    """事件通道名(SSE 端点订阅用)。"""
    return f"teacher_copilot:{submission_id}"


def make_sse_stream(bridge, submission_id: str, request):
    """SSE 生成器:订阅 grading 通道,推送事件帧(薄 Adapter,不依赖 RunRecord)。"""

    from deerflow.runtime.stream_bridge.base import (
        END_SENTINEL,
        HEARTBEAT_SENTINEL,
        StreamGap,
    )

    async def _stream():
        async for item in bridge.subscribe(
            grading_event_channel(submission_id), heartbeat_interval=15.0
        ):
            if await request.is_disconnected():
                break
            if item is END_SENTINEL:
                yield _sse("end", None)
                break
            if item is HEARTBEAT_SENTINEL:
                yield _sse("heartbeat", None)
                continue
            if isinstance(item, StreamGap):
                yield _sse("gap", {"code": "stream_replay_gap"})
                continue
            yield _sse(item.event, item.data)

    return _stream()


def _sse(event: str, data) -> str:
    """构造 SSE 帧。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def subscribe_sse(bridge, submission_id: str, request) -> "StreamingResponse":
    """构造 SSE StreamingResponse(调用方提供 current bridge;FastAPI 惰性导入)。"""
    from fastapi import StreamingResponse

    return StreamingResponse(
        make_sse_stream(bridge, submission_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
