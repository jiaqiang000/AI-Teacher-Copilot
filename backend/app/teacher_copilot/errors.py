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
        """转为 API/前端统一错误结构。"""
        return {"code": self.code, "message": self.message}


class InvalidArgument(TcError):
    """参数非法(HTTP 400),如缺少必填字段、文件类型/大小超限。"""
    code = "INVALID_ARGUMENT"
    http_status = 400


class PermissionDenied(TcError):
    """无业务权限(HTTP 403),如非本班教师访问班级数据。"""
    code = "PERMISSION_DENIED"
    http_status = 403


class TeacherNotFound(TcError):
    """教师不存在(HTTP 404)。"""
    code = "TEACHER_NOT_FOUND"
    http_status = 404


class StudentNotFound(TcError):
    """学生不存在(HTTP 404)。"""
    code = "STUDENT_NOT_FOUND"
    http_status = 404


class ClassNotFound(TcError):
    """班级不存在(HTTP 404)。"""
    code = "CLASS_NOT_FOUND"
    http_status = 404


class HomeworkNotFound(TcError):
    """作业不存在(HTTP 404)。"""
    code = "HOMEWORK_NOT_FOUND"
    http_status = 404


class QuestionNotFound(TcError):
    """题目不存在(HTTP 404)。"""
    code = "QUESTION_NOT_FOUND"
    http_status = 404


class SubmissionNotFound(TcError):
    """提交不存在(HTTP 404)。"""
    code = "SUBMISSION_NOT_FOUND"
    http_status = 404


class GradingInProgress(TcError):
    """提交已接受但批改进行中,拒绝重复提交(HTTP 409)。"""

    code = "SUBMISSION_GRADING_IN_PROGRESS"
    http_status = 409


class ProfileRebuildFailed(TcError):
    """画像重建失败(HTTP 500),如画像数据源不可用。"""
    code = "PROFILE_REBUILD_FAILED"
    http_status = 500


class DataSourceError(TcError):
    """外部/数据源错误(HTTP 500),如数据库或外部 API 异常。"""
    code = "DATA_SOURCE_ERROR"
    http_status = 500


class GradingOutputInvalid(TcError):
    """批改输出未通过确定性契约校验(如 Taxonomy 非法、分数加总不一致)。"""

    code = "GRADING_OUTPUT_INVALID"
    http_status = 422
