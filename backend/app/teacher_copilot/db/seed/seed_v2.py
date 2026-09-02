"""部署种子:丰富演示数据(30 学生/4 周作业/批改历史,V2 T008)。

功能:在 demo(基础教师/班级/学生/hw_004)基础上追加:
- 作业 hw_001/hw_002/hw_003(数学,与 hw_004 构成 4 周,本周=hw_003/hw_004)
- 每作业 3-4 道数学题(与 hw_004 类似,含题库来源题)
- 30 名学生跨 4 周的提交与批改结果(确定性随机,seed=42):
  分数/知识点 performance/错误(SIGN_ERROR/ARITHMETIC/GRAPH_READING 等),
  分布凑够:张三(sta_003)短期低分+重复错误,李四(stu_011)单次错误等
  供画像/分析/Agent(含周度复盘多智能体)真实演示。

幂等:已存在 hw_001 则整体跳过;重复运行安全。
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.grading import (
    GradingResult, GradingResultError, GradingResultKnowledgePoint, Submission,
)
from app.teacher_copilot.db.models.homework import Homework, Question

RNG = random.Random(42)

# 4 周作业(第二天数=距最近实际时间的偏移;AS_OF 用 2026-09-02 附近)
HOMEWORKS = [
    ("hw_001", "方程基础练习", 35),
    ("hw_002", "方程巩固", 21),
    ("hw_003", "单元练习", 7),   # 本周
    ("hw_004", "八年级数学周末作业", 0),  # 本周,demo 已建
]

# 每作业题目(复用题库语义)
QUESTIONS = {
    "hw_001": [(1, "calculation", "easy", "解方程 x + 5 = 12", 10),
               (2, "calculation", "easy", "解方程 3x - 4 = 11", 10),
               (3, "solution", "medium", "解方程 2(x-3)=x+5 并写过程", 10)],
    "hw_002": [(1, "calculation", "medium", "解方程 5x - 2 = 13", 10),
               (2, "solution", "medium", "解含括号的一元一次方程", 10),
               (3, "solution", "hard", "一元一次方程综合应用", 15)],
    "hw_003": [(1, "calculation", "easy", "解方程 2x + 3 = 9", 10),
               (2, "solution", "medium", "合并同类项后求解方程", 10),
               (3, "solution", "hard", "函数图像综合信息读取", 15),
               (4, "calculation", "medium", "读取函数图像上的点坐标", 10)],
}

# 学生表现画像:差异化均值(张三低,李四中,其余随机)
KFPERF = ("transposition", "combine_like_terms", "graph")
PERF_VALUES = ("correct", "partial", "incorrect")
ERR_CODES = ("SIGN_ERROR", "ARITHMETIC_ERROR", "MISSING_STEP", "GRAPH_READING_ERROR")


async def seed_rich_data() -> None:
    """写入丰富演示数据(幂等)。"""
    now = datetime.utcnow()
    async with get_session() as s:
        if await s.scalar(select(Homework).where(Homework.homework_id == "hw_001")):
            print("seed_rich_data: hw_001 已存在,跳过")
            return

        # 1) 作业+题目(除 hw_004 已由 demo 建)
        for hw_id, hw_name, days_ago in HOMEWORKS:
            if hw_id == "hw_004":
                continue
            s.add(Homework(
                homework_id=hw_id, name=hw_name, class_id="class_03",
                teacher_id="teacher_01", subject="math", status="PUBLISHED",
                published_at=now - timedelta(days=days_ago),
            ))
            for no, qtype, diff, content, max_score in QUESTIONS[hw_id]:
                s.add(Question(
                    question_id=f"q_{hw_id}_{no}", homework_id=hw_id, question_no=no,
                    subject="math", question_type=qtype, difficulty=diff,
                    content=content, max_score=max_score,
                ))

        # 2) 批改历史:每学生×每作业×每题的提交+结果(部分缺交)
        question_ids = {hw_id: [q for q in QUESTIONS[hw_id]] for hw_id in QUESTIONS}
        # 补 hw_004 题目清单(来自 demo: q001/q002/q003)
        question_ids["hw_004"] = [
            (1, "calculation", "easy", "解方程 2x + 4 = 8", 10),
            (2, "solution", "medium", "解含括号的一元一次方程", 10),
            (3, "solution", "hard", "函数图像综合信息读取", 10),
        ]
        for hw_id, days_ago in [(h[0], h[2]) for h in HOMEWORKS]:
            qs = question_ids[hw_id]
            for stu_no in range(1, 31):
                stu_id = f"stu_{stu_no:03d}"
                # 弱化:张三/少数学生表现差,李四单次错误
                base_rate = 0.9
                if stu_id == "stu_003":
                    base_rate = 0.45
                elif stu_id == "stu_011":
                    base_rate = 0.8
                # 缺交概率 10%
                if RNG.random() < 0.10:
                    continue
                for (no, qtype, diff, content, max_score) in qs:
                    # 答题时间 = 作业发布后 1-2 天
                    # 幂等:同(学生,题目)已有提交则跳过(兼容旧库/重复运行)
                    qid = (f"q_{hw_id}_{no}" if hw_id != "hw_004" else f"q{no:03d}")
                    if await s.scalar(
                        select(Submission).where(
                            Submission.student_id == stu_id,
                            Submission.question_id == qid,
                        )
                    ):
                        continue
                    sub_time = now - timedelta(days=days_ago - 1 - RNG.randint(0, 1))
                    sub_id = f"sub_{hw_id}_{stu_no}_{no}"
                    s.add(Submission(
                        submission_id=sub_id, student_id=stu_id,
                        question_id=qid,
                        homework_id=hw_id, image_url="https://macro-oss1069.oss-cn-beijing.aliyuncs.com/sample_05_img_480_pert_5.1.png",
                        status="SUCCEEDED", current_stage="COMPLETED",
                        submitted_at=sub_time,
                    ))
                    # 得分:base_rate ± 抖动
                    rate = max(0.0, min(1.0, base_rate + RNG.uniform(-0.18, 0.12)))
                    earned = round(rate * max_score, 1)
                    gr_id = f"gr_{sub_id}"
                    s.add(GradingResult(
                        grading_result_id=gr_id, submission_id=sub_id,
                        subject="math", question_type=qtype, difficulty=diff,
                        score_earned=earned, score_max=float(max_score),
                        score_rate=round(earned / max_score, 4),
                        feedback={}, math_detail=None, english_essay_detail=None,
                        execution_meta={}, created_at=sub_time,
                    ))
                    # 诊断:低分学生带知识点/错误(张三/SIGN_ERROR 重复)
                    kp_key = f"math.linear_equation.{KFPERF[RNG.randint(0, 2)]}"
                    if rate < 0.6 or stu_id == "stu_003":
                        perf = "incorrect" if rate < 0.5 else "partial"
                        s.add(GradingResultKnowledgePoint(
                            grading_result_id=gr_id, knowledge_point_key=kp_key,
                            raw_name="移项/合并符号处理", performance=perf,
                            evidence="过程存在计算或符号错误"))
                        err_code = "SIGN_ERROR" if (stu_id == "stu_003" or RNG.random() < 0.5) \
                            else ERR_CODES[RNG.randint(0, len(ERR_CODES) - 1)]
                        s.add(GradingResultError(
                            grading_result_id=gr_id, error_code=err_code,
                            raw_type="符号/计算错误", knowledge_point_key=kp_key,
                            description="步骤错误", evidence="过程文本"))
        await s.commit()
        print("seed_rich_data: 丰富数据已写入(4 周作业/30 学生批改历史)")


if __name__ == "__main__":
    import asyncio

    from app.teacher_copilot.config.settings import get_config
    from app.teacher_copilot.db.engine import dispose_db, init_db

    async def _main():
        await init_db(get_config().database_url)
        await seed_rich_data()
        await dispose_db()

    asyncio.run(_main())
