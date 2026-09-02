"""种子数据汇总模块。"""

from app.teacher_copilot.db.seed.demo import seed_demo
from app.teacher_copilot.db.seed.question_bank import seed_question_bank
from app.teacher_copilot.db.seed.taxonomy import seed_taxonomy

__all__ = ["seed_demo", "seed_question_bank", "seed_taxonomy"]
