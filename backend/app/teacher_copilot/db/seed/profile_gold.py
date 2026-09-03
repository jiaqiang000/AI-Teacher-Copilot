"""金标准数据验证:ProfileAlgorithmV1 对参考文档 08 §3.2 案情的判定。

构造张三(stu_003)多道题的历史(跨 14/28 天,transposition 多次低分 +
28 天内 SIGN_ERROR ≥2 次)与李四(stu_011)单次一次错误,验证:
- 张三: knowledge_points[transposition].mastery <0.60 且 attempt_count>=3
         (weak_point=true), recurring_errors 含 SIGN_ERROR, trend 判定
- 李四: 单次错误不升级 weak_point / recurring_error(参考文档 08 金标准)

注意业务约束 UNIQUE(student_id, question_id):多道题各自一次提交。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta

from sqlalchemy import delete, select

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", stream=sys.stderr)


async def main() -> None:
    """CLI 入口:运行 profile_gold 数据生成脚本。"""
    from app.teacher_copilot.db.engine import create_all, dispose_db, get_session, init_db
    from app.teacher_copilot.db.models.grading import (
        GradingResult, GradingResultError, GradingResultKnowledgePoint, Submission,
    )
    from app.teacher_copilot.db.models.homework import Homework, Question
    from app.teacher_copilot.db.models.org import Teacher
    from app.teacher_copilot.db.seed.taxonomy import seed_taxonomy
    from app.teacher_copilot.services.profile_service import ProfileAlgorithmV1

    await init_db("sqlite+aiosqlite:///tc-data/profile_gold.db")
    await create_all()
    await seed_taxonomy()

    now = datetime.utcnow()
    async with get_session() as s:
        for m in (GradingResultError, GradingResultKnowledgePoint, GradingResult, Submission):
            await s.execute(delete(m))
        await s.commit()
        if not await s.scalar(select(Teacher).where(Teacher.teacher_id == "teacher_01")):
            s.add(Teacher(teacher_id="teacher_01", name="王老师"))
        hw = await s.scalar(select(Homework).where(Homework.homework_id == "hw_p"))
        if hw is None:
            s.add(Homework(homework_id="hw_p", name="移项专项作业", class_id="class_03",
                           teacher_id="teacher_01", subject="math", status="PUBLISHED"))
        for no in range(1, 6):
            qid = f"q_p{no}"
            if await s.scalar(select(Question).where(Question.question_id == qid)) is None:
                s.add(Question(question_id=qid, homework_id="hw_p", question_no=no,
                               subject="math", question_type="calculation", difficulty="easy",
                               content=f"解方程 {no}: 2x + {2*no} = {4*no}", max_score=10))
        await s.commit()

    async with get_session() as s:
        zs_days = [5, 10, 20, 35, 45]
        zs_rates = [0.3, 0.4, 0.5, 0.6, 0.7]
        for i, (days, rate) in enumerate(zip(zs_days, zs_rates), start=1):
            sub_id = f"sub_zs{i}"
            s.add(Submission(submission_id=sub_id, student_id="stu_003", question_id=f"q_p{i}",
                             homework_id="hw_p", image_url="x.jpg", status="SUCCEEDED",
                             current_stage="COMPLETED", submitted_at=now - timedelta(days=days)))
            gr = GradingResult(
                grading_result_id=f"gr_zs{i}", submission_id=sub_id,
                subject="math", question_type="calculation", difficulty="easy",
                score_earned=round(rate * 10, 1), score_max=10, score_rate=rate,
                feedback={}, math_detail=None, english_essay_detail=None, execution_meta={},
                created_at=now - timedelta(days=days),
            )
            s.add(gr)
            if i <= 4:
                s.add(GradingResultKnowledgePoint(
                    grading_result_id=f"gr_zs{i}",
                    knowledge_point_key="math.linear_equation.transposition",
                    raw_name="移项符号处理", performance="incorrect", evidence="移项后符号未变"))
                s.add(GradingResultError(
                    grading_result_id=f"gr_zs{i}", error_code="SIGN_ERROR",
                    raw_type="移项时未改变符号",
                    knowledge_point_key="math.linear_equation.transposition",
                    description="移项后没有改变符号", evidence="+4 移到右侧后仍写为 +4"))
        # 李四:1 道题 1 次(27 天前,一次错误)
        s.add(Submission(submission_id="sub_ls0", student_id="stu_011", question_id="q_p5",
                         homework_id="hw_p", image_url="x.jpg", status="SUCCEEDED",
                         current_stage="COMPLETED", submitted_at=now - timedelta(days=27)))
        gr_ls = GradingResult(
            grading_result_id="gr_ls0", submission_id="sub_ls0",
            subject="math", question_type="calculation", difficulty="easy",
            score_earned=8.0, score_max=10, score_rate=0.8,
            feedback={}, math_detail=None, english_essay_detail=None, execution_meta={},
            created_at=now - timedelta(days=27))
        s.add(gr_ls)
        s.add(GradingResultKnowledgePoint(
            grading_result_id="gr_ls0", knowledge_point_key="math.linear_equation.transposition",
            raw_name="移项", performance="incorrect", evidence="一次错误"))
        s.add(GradingResultError(
            grading_result_id="gr_ls0", error_code="SIGN_ERROR", raw_type="一次符号错误",
            knowledge_point_key="math.linear_equation.transposition",
            description="移项未变号", evidence="+4 变为+4"))
        await s.commit()

    async with ProfileAlgorithmV1() as algo:
        zs = await algo.compute_student("stu_003", "math", as_of=now)
        ls = await algo.compute_student("stu_011", "math", as_of=now)

    print("=== 张三(stu_003)====", flush=True)
    print("overview:", zs["overview"], flush=True)
    print("weak_points:", zs["weak_points"], flush=True)
    print("recurring_errors:", zs["recurring_errors"], flush=True)
    print("=== 李四(stu_011)====", flush=True)
    print("overview:", ls["overview"], flush=True)
    print("weak_points 数:", len(ls["weak_points"]), "recurring 数:", len(ls["recurring_errors"]), flush=True)

    await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
