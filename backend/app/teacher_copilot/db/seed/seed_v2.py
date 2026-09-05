"""写入持久化演示事实:八三班基线 + 八四/八五班差异化数据。

seed_rich_data 负责八三班的既有 4 周评测世界；seed_diverse_data 负责八四班和八五班
各自 6 周的作业、题目、提交、批改结果和诊断事实。两个入口都对已存在记录幂等处理，
执行后数据会保留在 TC_DATABASE_URL 指向的真实业务数据库中。
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.grading import (
    GradingResult,
    GradingResultError,
    GradingResultKnowledgePoint,
    Submission,
)
from app.teacher_copilot.db.models.homework import Homework, Question
from app.teacher_copilot.db.models.org import ClassRoom

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

# 新增班级使用独立 ID 和事实生成参数,不与 class_03 的评测世界混用。
DIVERSE_CLASS_SPECS = (
    {
        "class_id": "class_04",
        "code": "c04",
        "student_offset": 100,
        "student_count": 32,
        "weekly_rates": (0.58, 0.62, 0.66, 0.72, 0.84, 0.90),
        "completion_rates": (0.58, 0.63, 0.68, 0.72, 0.76, 0.78),
        "knowledge_points": (
            "math.linear_equation.combine_like_terms",
            "math.linear_equation.arithmetic",
            "math.linear_equation.application",
        ),
        "error_codes": ("ARITHMETIC_ERROR", "MISSING_STEP"),
    },
    {
        "class_id": "class_05",
        "code": "c05",
        "student_offset": 200,
        "student_count": 28,
        "weekly_rates": (0.72, 0.65, 0.58, 0.50, 0.42, 0.34),
        "completion_rates": (0.88, 0.78, 0.70, 0.62, 0.55, 0.48),
        "knowledge_points": (
            "math.function.graph",
            "math.application.word_problem",
            "math.function.coordinate",
        ),
        "error_codes": ("GRAPH_READING_ERROR", "SIGN_ERROR"),
    },
)

DIVERSE_WEEK_DAYS = (42, 34, 26, 18, 10, 2)

DIVERSE_QUESTION_TEMPLATES = {
    "class_04": (
        (1, "calculation", "easy", "合并同类项后求解方程", 10),
        (2, "solution", "medium", "说明运算步骤并检验方程", 10),
        (3, "solution", "hard", "一元一次方程综合应用", 15),
    ),
    "class_05": (
        (1, "solution", "medium", "读取函数图像并判断变化趋势", 10),
        (2, "solution", "hard", "根据图像信息解决综合问题", 15),
        (3, "calculation", "medium", "列式解决实际应用问题", 10),
    ),
}


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


async def seed_diverse_data() -> None:
    """为八四班/八五班写入可重复且有明显差异的多周事实。"""
    now = datetime.utcnow()
    async with get_session() as session:
        for spec in DIVERSE_CLASS_SPECS:
            class_row = await session.scalar(
                select(ClassRoom).where(ClassRoom.class_id == spec["class_id"])
            )
            if class_row is None:
                raise RuntimeError(f"演示班级 {spec['class_id']} 不存在,请先执行 seed_demo")

            templates = DIVERSE_QUESTION_TEMPLATES[spec["class_id"]]
            diagnostic_threshold = (
                0.62 if spec["class_id"] == "class_04" else 0.78
            )
            for week, days_ago in enumerate(DIVERSE_WEEK_DAYS, start=1):
                homework_id = f"hw_{spec['code']}_w{week:02d}"
                homework = await session.scalar(
                    select(Homework).where(Homework.homework_id == homework_id)
                )
                if homework is None:
                    homework = Homework(
                        homework_id=homework_id,
                        name=f"{class_row.name}第{week}周数学练习",
                        class_id=spec["class_id"],
                        teacher_id="teacher_01",
                        subject="math",
                        status="PUBLISHED",
                        published_at=now - timedelta(days=days_ago),
                    )
                    session.add(homework)

                for question_no, qtype, difficulty, content, max_score in templates:
                    question_id = (
                        f"q_{spec['code']}_w{week:02d}_{question_no}"
                    )
                    question = await session.scalar(
                        select(Question).where(Question.question_id == question_id)
                    )
                    if question is None:
                        session.add(Question(
                            question_id=question_id,
                            homework_id=homework_id,
                            question_no=question_no,
                            subject="math",
                            question_type=qtype,
                            difficulty=difficulty,
                            content=content,
                            max_score=max_score,
                        ))

                completion_target = spec["completion_rates"][week - 1]
                for student_index in range(1, spec["student_count"] + 1):
                    participation = (
                        student_index * 37 + week * 17 + len(spec["code"]) * 11
                    ) % 100
                    if participation >= int(completion_target * 100):
                        continue

                    student_id = f"stu_{spec['student_offset'] + student_index:03d}"
                    for question_no, qtype, difficulty, _, max_score in templates:
                        question_id = (
                            f"q_{spec['code']}_w{week:02d}_{question_no}"
                        )
                        existing = await session.scalar(
                            select(Submission).where(
                                Submission.student_id == student_id,
                                Submission.question_id == question_id,
                            )
                        )
                        if existing is not None:
                            continue

                        tier = student_index % 10
                        tier_offset = 0.12 if tier in (1, 2) else (
                            -0.12 if tier in (0, 8, 9) else 0.0
                        )
                        wiggle = (
                            (student_index * 11 + week * 7 + question_no * 5) % 7 - 3
                        ) / 100
                        question_offset = (0.02, 0.0, -0.03)[(question_no - 1) % 3]
                        rate = max(
                            0.15,
                            min(
                                0.98,
                                spec["weekly_rates"][week - 1]
                                + tier_offset
                                + wiggle
                                + question_offset,
                            ),
                        )
                        submitted_at = now - timedelta(days=days_ago - 1)
                        submission_id = (
                            f"sub_{spec['code']}_w{week:02d}_"
                            f"s{student_index:02d}_q{question_no}"
                        )
                        session.add(Submission(
                            submission_id=submission_id,
                            student_id=student_id,
                            question_id=question_id,
                            homework_id=homework_id,
                            image_url=(
                                "https://macro-oss1069.oss-cn-beijing.aliyuncs.com/"
                                "sample_05_img_480_pert_5.1.png"
                            ),
                            status="SUCCEEDED",
                            current_stage="COMPLETED",
                            submitted_at=submitted_at,
                        ))
                        score_earned = round(rate * max_score, 1)
                        grading_id = f"gr_{submission_id}"
                        session.add(GradingResult(
                            grading_result_id=grading_id,
                            submission_id=submission_id,
                            subject="math",
                            question_type=qtype,
                            difficulty=difficulty,
                            score_earned=score_earned,
                            score_max=float(max_score),
                            score_rate=round(score_earned / max_score, 4),
                            feedback={},
                            math_detail=None,
                            english_essay_detail=None,
                            execution_meta={"source": "diverse_demo_seed"},
                            created_at=submitted_at,
                        ))

                        if rate < diagnostic_threshold or (
                            spec["class_id"] == "class_05"
                            and student_index % 5 == 0
                            and question_no == 1
                        ):
                            performance = (
                                "incorrect" if rate < 0.55 else "partial"
                            )
                            kp_key = spec["knowledge_points"][
                                (student_index + week + question_no)
                                % len(spec["knowledge_points"])
                            ]
                            session.add(GradingResultKnowledgePoint(
                                grading_result_id=grading_id,
                                knowledge_point_key=kp_key,
                                raw_name="班级专项训练知识点",
                                performance=performance,
                                evidence="演示数据中的步骤表现",
                            ))
                            error_code = spec["error_codes"][
                                (student_index + week + question_no)
                                % len(spec["error_codes"])
                            ]
                            session.add(GradingResultError(
                                grading_result_id=grading_id,
                                error_code=error_code,
                                raw_type="演示数据错误类型",
                                knowledge_point_key=kp_key,
                                description="演示数据中的典型错误",
                                evidence="演示批改过程",
                            ))

        await session.commit()
        print("seed_diverse_data: 八四班/八五班差异化数据已写入(每班 6 周)", flush=True)


if __name__ == "__main__":
    import asyncio

    from app.teacher_copilot.config.settings import get_config
    from app.teacher_copilot.db.engine import dispose_db, init_db

    async def _main():
        await init_db(get_config().database_url)
        await seed_rich_data()
        await seed_diverse_data()
        await dispose_db()

    asyncio.run(_main())
