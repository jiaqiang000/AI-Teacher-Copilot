"""Teacher Copilot 统一错误契约。

错误码与参考文档 docs/05-tool-skill.md §11 及 contracts/teacher-agent-contracts.md 一致;
业务代码抛出 TeacherCopilotError 子类,由 API / Tool 层转换为统一 JSON 返回。
"""

from __future__ import annotations


class TcError(Exception):
    """Teacher Copilot 业务错误基类(带错误码与用户可见消息)。"""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code
        if code:
            self.code = code

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


class InvalidArgument(TcError):
    code = "INVALID_ARGUMENT"
    http_status = 400


class PermissionDenied(TcError):
    code = "PERMISSION_DENIED"
    http_status = 403


class TeacherNotFound(TcError):
    code = "TEACHER_NOT_FOUND"
    http_status = 404


class StudentNotFound(TcError):
    code = "STUDENT_NOT_FOUND"
    http_status = 404


class ClassNotFound(TcError):
    code = "CLASS_NOT_FOUND"
    http_status = 404


class HomeworkNotFound(TcError):
    code = "HOMEWORK_NOT_FOUND"
    http_status = 404


class QuestionNotFound(TcError):
    code = "QUESTION_NOT_FOUND"
    http_status = 404


class SubmissionNotFound(TcError):
    code = "SUBMISSION_NOT_FOUND"
    http_status = 404


class GradingInProgress(TcError):
    """提交已接受但批改进行中,拒绝重复提交(HTTP 409)。"""

    code = "SUBMISSION_GRADING_IN_PROGRESS"
    http_status = 409


class ProfileRebuildFailed(TcError):
    code = "PROFILE_REBUILD_FAILED"
    http_status = 500


class DataSourceError(TcError):
    code = "DATA_SOURCE_ERROR"
    http_status = 500


class GradingOutputInvalid(TcError):
    """批改输出未通过确定性契约校验(如 Taxonomy 非法、分数加总不一致)。"""

    code = "GRADING_OUTPUT_INVALID"
    http_status = 422
