// Teacher Copilot API 客户端(调用 backend gateway 业务 API)
// 路径:BASE_URL 由环境变量 TC_API_BASE 或 NEXT_PUBLIC_GATEWAY 配置,默认 /api/teacher-copilot

import type { GradingResult, HomeworkAnalysis, StudentProfile } from "./types"

const BASE = (process.env.NEXT_PUBLIC_TC_API_BASE || "http://127.0.0.1:8100").replace(/\/$/, "") + "/api/teacher-copilot"
const TEACHER_ID = process.env.NEXT_PUBLIC_TC_TEACHER_ID || "teacher_01"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Teacher-Id": TEACHER_ID,
      ...(init?.headers || {}),
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail?.message || `请求失败 ${res.status}`)
  }
  const json = await res.json()
  return (json.data ?? json) as T
}

// ---- 作业与题目 (US1) ----
export async function getHomework(homeworkId: string) {
  return request<{
    homework_id: string
    name: string
    subject: string
    status: string
    deadline: string | null
    questions: Array<{
      question_id: string
      question_no: number
      question_type: string
      difficulty: string | null
      content: string
      max_score: number
    }>
  }>(`/homework/${homeworkId}`)
}

export async function createHomework(body: {
  name: string
  class_id: string
  subject: string
  deadline?: string | null
}) {
  return request<{ homework_id: string; status: string }>(`/homework/`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export async function addQuestion(
  homeworkId: string,
  body: {
    subject: string
    question_type: string
    content: string
    max_score: number
    difficulty?: string | null
  },
) {
  return request<{ question_id: string; question_no: number; difficulty: string | null }>(
    `/homework/${homeworkId}/questions`,
    { method: "POST", body: JSON.stringify(body) },
  )
}

export async function publishHomework(homeworkId: string) {
  return request<{ homework_id: string; status: string }>(`/homework/${homeworkId}/publish`, {
    method: "POST",
    body: JSON.stringify({}),
  })
}

// ---- 提交与批改 (US2) ----
export async function submitAnswer(body: {
  question_id: string
  homework_id: string
  image_url: string
}) {
  return request<{
    submission_id: string
    status: string
    current_stage: string
    created: boolean
  }>(`/submissions/`, { method: "POST", body: JSON.stringify(body) })
}

export async function getSubmission(submissionId: string) {
  return request<{
    submission_id: string
    status: string
    current_stage: string
    error_code: string | null
    error_message: string | null
    image_url: string
  }>(`/submissions/${submissionId}`)
}

export async function getGradingResult(submissionId: string) {
  return request<GradingResult>(`/submissions/${submissionId}/grading-result`)
}

// ---- 分析 (US3) ----
export async function getHomeworkAnalysis(homeworkId: string, classId: string) {
  return request<HomeworkAnalysis>(
    `/analysis/homework/${homeworkId}?class_id=${classId}`,
  )
}

export async function getQuestionAnalysis(
  questionId: string, homeworkId: string, classId: string,
) {
  return request<object>(
    `/analysis/question/${questionId}?homework_id=${homeworkId}&class_id=${classId}`,
  )
}

// ---- 画像 (US4) ----
export async function getStudentProfile(studentId: string, subject: string) {
  return request<StudentProfile>(
    `/profile/student/${studentId}?subject=${subject}`,
  )
}

export async function getStudentHistory(studentId: string, subject: string) {
  return request<Array<Record<string, unknown>>>(
    `/profile/student/${studentId}/history?subject=${subject}`,
  )
}

export async function getClassProfile(classId: string, subject: string) {
  return request<{
    basic: { class_id: string; subject: string; algorithm_version: string }
    overview: {
      student_count: number
      active_student_count: number
      avg_score_rate: number | null
      recent_score_rate: number | null
      trend: string | null
    }
    weak_points: Array<{ knowledge_point_key: string; avg_mastery: number; weak_student_count: number; trend: string | null }>
    common_errors: Array<{ error_code: string; knowledge_point_key: string; occurrence_count: number; affected_student_count: number }>
    attention_students: Array<{ student_id: string; weak_point_count: number; recent_score_rate: number | null; trend: string | null; reason_codes: string[] }>
  }>(`/profile/class/${classId}?subject=${subject}`)
}
