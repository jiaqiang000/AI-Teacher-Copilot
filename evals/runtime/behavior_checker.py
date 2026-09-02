"""Behavior Checker:基于 DeerFlow RunEventStore 的 Agent 行为判定(参考文档 08 §7)。

从 RunEventStore 读取真实执行证据(Tool call/Sub-Agent/Skill/Memory),
程序化断言 required/forbidden 行为;Result Pass 与 Behavior Pass 独立判定。
必要时用 EvalTraceAdapter 做只读转换(参考文档 08 §9.1:先检查现有查询能力,
不能满足才新增 Adapter)。
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("evals.behavior")


class BehaviorChecker:
    """把 EvalTraceView 与用例断言对比,输出 Behavior Pass。"""

    def __init__(self, trace_view: dict) -> None:
        # trace_view: RunEventStore 投影(EvalTraceView)
        #   {"tool_calls": [{"name": ..., "arguments": ...}],
        #    "subagents": [{"type": ..., "lifecycle": ...}],
        #    "skills": [...], "final_answer": ...}
        self.view = trace_view

    def check(self, case: dict) -> tuple[bool, list[str]]:
        """检查用例的 expected/forbidden behavior。"""
        issues: list[str] = []
        expected = case.get("expected_behavior", {})
        forbidden = case.get("forbidden_behavior", [])

        tools_called = {tc["name"] for tc in self.view.get("tool_calls", [])}
        skills_called = set(self.view.get("skills", []))
        subagent_types = {sa.get("type") for sa in self.view.get("subagents", [])}

        # required_tools 覆盖
        for t in expected.get("required_tools", []):
            if t not in tools_called:
                issues.append(f"缺少必需 Tool: {t}")
        # required_subagents
        for sa in expected.get("required_subagents", []):
            if sa not in subagent_types:
                issues.append(f"缺少必需 Sub-Agent: {sa}")
        # skills(技能级别:显式 /skill 或 SKILL.md 加载)
        for sk in expected.get("skills", []):
            if sk not in skills_called:
                issues.append(f"缺少 Skill: {sk}")
        # forbidden behavior(禁止出现的架构行为)
        for fb in forbidden:
            if isinstance(fb, str):
                if fb in ("task", "task Tool Call"):
                    if any(subagent_types):
                        issues.append(f"出现禁止行为: {fb}")
                elif fb == "ask_clarification":
                    if "ask_clarification" in tools_called:
                        issues.append(f"出现禁止行为: {fb}")
        return (not issues, issues)


def eval_trace_view_from_run_events(events: list[dict]) -> dict:
    """把 RunEventStore 事件投影为 EvalTraceView(只读取模型转换)。

    events: [{"type": "llm.tool.call", "data": {"name": ..., "arguments": ...}}, ...]
    """
    view = {"tool_calls": [], "subagents": [], "skills": [], "final_answer": ""}
    for ev in events:
        etype = ev.get("type", "")
        data = ev.get("data", {}) or {}
        if etype in ("llm.tool.call", "tool.call"):
            view["tool_calls"].append({"name": data.get("name"), "arguments": data.get("arguments")})
        elif etype == "subagent.start":
            view["subagents"].append({"type": data.get("subagent_type"), "lifecycle": "start"})
        elif etype == "middleware:skill_activation":
            view["skills"].append(data.get("skill", ""))
        elif etype == "llm.ai.response" and not view["final_answer"]:
            view["final_answer"] = data.get("content", "")
    return view
