// Teacher Copilot 前端类型(与 backend contracts 对应)
// 数据契约参考 docs/02-grading-result-schema.md 与 docs/03 画像/分析结构

export type Subject = "math" | "english"

export interface TeacherClassSummary {
  class_id: string
  name: string
  student_count: number
}

export interface HomeworkSummary {
  homework_id: string
  name: string
  class_id: string
  class_name: string
  subject: Subject
  status: string
  deadline: string | null
  published_at: string | null
}

export interface Score {
  earned: number
  max: number
  rate: number
}

export interface Feedback {
  summary: string
  // 接口层已归一(缺失时补空数组),但历史数据与上游回归都可能给出不完整形状,
  // 标为可选以强制调用方处理"可能没有"的情况(008 T044)
  strengths?: string[]
  improvements?: string[]
}

export interface KnowledgePoint {
  key: string
  name?: string
  raw_name?: string
  performance?: string
  evidence?: string
}

export interface ErrorItem {
  code: string
  type?: string
  raw_type?: string
  knowledge_point_key?: string
  description?: string
  evidence?: string
}

export interface GradingResult {
  grading_result_id: string
  subject: Subject
  question_type: string
  difficulty: string | null
  score: Score
  feedback: Feedback
  diagnosis?: { knowledge_points: KnowledgePoint[]; errors: ErrorItem[] }
  math_detail?: {
    correct: boolean
    final_answer?: string
    steps: Array<{
      step_index: number
      description: string
      evidence_block_ids: number[]
      error_block_ids: number[]
      status: string
      earned_score: number
      max_score: number
      feedback: string
    }>
  } | null
  english_essay_detail?: {
    dimension_scores: Record<string, { score: number; max_score: number }>
    language_errors?: Array<{
      error_code: string
      original: string
      suggestion: string
    }>
    evidence?: Record<string, string[]>
  } | null
}

export interface StudentProfile {
  basic: {
    student_id: string
    student_name?: string
    class_id?: string
    class_name?: string
    subject: Subject
    algorithm_version: string
  }
  overview: {
    attempt_count: number
    avg_score_rate: number | null
    recent_score_rate: number | null
    trend: string | null
  }
  knowledge_points: Array<{
    knowledge_point_key: string
    knowledge_point_name: string
    attempt_count: number
    mastery: number | null
    recent_performance: number | null
    trend: string | null
    last_practiced_at: string | null
    common_error_codes: string[]
  }>
  weak_points: Array<{
    knowledge_point_key: string
    knowledge_point_name: string
    mastery: number
    trend: string | null
    evidence_count: number
  }>
  recurring_errors: Array<{
    error_code: string
    error_name: string
    knowledge_point_key: string
    knowledge_point_name: string
    occurrence_count: number
    recent_occurrence_count: number
    last_occurred_at: string | null
  }>
  difficulty_performance: Record<
    string,
    {
      attempt_count: number
      avg_score_rate: number | null
      recent_score_rate: number | null
    }
  > | null
}

export interface HomeworkAnalysis {
  homework_id: string
  class_id: string
  completion: {
    assigned_student_count: number
    submitted_student_count: number
    completion_rate: number | null
  }
  performance: {
    graded_student_count: number
    avg_score_rate: number | null
    score_distribution: {
      below_60: number
      from_60_to_79: number
      from_80_to_89: number
      from_90_to_100: number
    } | null
  }
  knowledge_points: Array<{
    knowledge_point_key: string
    knowledge_point_name: string
    participating_student_count: number
    avg_performance: number | null
    low_performance_student_count: number
  }>
  questions: Array<{
    question_id: string
    question_no: number
    attempt_count: number
    avg_score_rate: number | null
    error_student_count: number
    error_rate: number | null
    common_errors: Array<{
      error_code: string
      error_name: string
      knowledge_point_key: string
      knowledge_point_name: string
      occurrence_count: number
      affected_student_count: number
    }>
  }>
  attention_students: Array<{
    student_id: string
    homework_score_rate: number | null
    reason_codes: string[]
    related_question_ids: string[]
  }>
}
