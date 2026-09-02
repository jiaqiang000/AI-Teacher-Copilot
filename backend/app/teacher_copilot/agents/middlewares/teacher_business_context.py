"""TeacherBusinessContextMiddleware:把当前页面业务上下文注入模型(参考文档 06-07 §2.4)。

- DeeerFlow RunCreateRequest.context 携带 teacher_business_context
- 本中间件从 Runtime Context 读取,整理为模型可理解的隐藏业务上下文注入
- 边界:业务上下文 ≠ 授权事实;真正权限校验仍在 TeacherPermissionService
  (即使前端篡改 context,Tool 仍按 Runtime 可信身份校验)

实现基于 LangChain AgentMiddleware(DeerFlow 配置化中间件机制):
    extensions.middlewares:
      - app.teacher_copilot.agents.middlewares.teacher_business_context:TeacherBusinessContextMiddleware
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware

logger = logging.getLogger("teacher_copilot.middleware")


class TeacherBusinessContextMiddleware(AgentMiddleware):
    """将当前页面业务上下文(学生/班级/作业/题目)注入模型消息。"""

    async def before_model(self, state, config, **kwargs):
        """在模型调用前把 business context 注入消息尾部(隐藏业务上下文)。

        state 中携带 runtime context(键 teacher_business_context);若不存在则跳过。
        """
        try:
            runtime = getattr(state, "config", {}) or {}
            context = runtime.get("teacher_business_context") or {}
            if not context:
                return {"messages": []}
            injected = self._format_context(context)
            logger.debug("注入 TeacherBusinessContext: %s", context)
            # 以 system 风格辅助消息注入(不替代事实,模型仍须经 Tool 取数)
            from langchain_core.messages import SystemMessage

            return {"messages": [SystemMessage(content=injected)]}
        except Exception as exc:  # pragma: no cover - 注入失败不阻断主流程
            logger.warning("TeacherBusinessContext 注入失败(不影响执行): %s", exc)
            return {"messages": []}

    @staticmethod
    def _format_context(context: dict) -> str:
        """把业务上下文格式化为模型可读文本。"""
        lines = ["【当前页面业务上下文(辅助解析业务对象,业务数据仍以 Tool 结果为准)】"]
        if context.get("current_class_id"):
            lines.append(f"- 当前班级: {context.get('current_class_id')}" +
                         (f"({context.get('current_class_name')})" if context.get("current_class_name") else ""))
        if context.get("current_student_id"):
            lines.append(f"- 当前学生: {context.get('current_student_id')}")
        if context.get("current_homework_id"):
            lines.append(f"- 当前作业: {context.get('current_homework_id')}")
        if context.get("current_question_id"):
            lines.append(f"- 当前题目: {context.get('current_question_id')}")
        if context.get("current_subject"):
            lines.append(f"- 当前学科: {context.get('current_subject')}")
        if context.get("class_refs"):
            lines.append(f"- 可访问班级: {context.get('class_refs')}")
        return "\n".join(lines)
