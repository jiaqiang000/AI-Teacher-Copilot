---
name: differentiated-practice
description: 根据班级和学生掌握情况,将学生划分为不同学习层次,并为各层匹配不同知识点、难度和题型的练习。
allowed-tools:
  - get_class_profile
  - list_class_students
  - get_student_profile
  - search_question_bank
---

# Task Goal

为学生分层并生成分层练习:学生分层结果、各层训练目标、知识点、难度、题目集合与分层依据。

# Required Tools

- get_class_profile:班级整体掌握情况与分布
- list_class_students:枚举参与分层的完整学生集合
- get_student_profile:读取具体学生的掌握情况
- search_question_bank:按知识点/难度/题型检索题库题

# Workflow

1. get_class_profile → 识别班级整体分布
2. list_class_students → 获取完整学生集合
3. 按需 get_student_profile → 读参与学生的具体掌握情况
4. 划分层次(默认三组):
   - 基础组:补基础知识点,难度 easy
   - 巩固组:当前核心知识点,难度 medium
   - 提升组:综合应用,难度 hard
5. 各组 search_question_bank(按知识点分别检索,不依赖一次查询平均分配)
6. 生成分层练习

# Evidence Rules

- 分层依据必须来自 ProfileAlgorithmV1 的画像事实(weak_points / mastery / trend)
- 题库结果必须是 QuestionBankItem,不得返回 Homework 已布置的 Question
- 多个知识点应分别检索

# Output Format

学生分层结果 / 各层训练目标 / 各层知识点 / 各层难度 / 各层题目集合 / 分层依据

# Fallback

题库无匹配题 → 降低知识点/难度要求并说明;学生无画像数据 → 该生信息不足,建议先诊断再分层。
