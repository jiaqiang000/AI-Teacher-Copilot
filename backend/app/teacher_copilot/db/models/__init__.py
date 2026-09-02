"""数据库模型汇总模块。

导入全部模型,确保 Base.metadata 注册所有表(供 create_all 使用)。
"""

from app.teacher_copilot.db.models import grading, homework, org, taxonomy

__all__ = ["grading", "homework", "org", "taxonomy"]
