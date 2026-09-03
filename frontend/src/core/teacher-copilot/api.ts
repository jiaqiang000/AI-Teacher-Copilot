// Teacher Copilot API 客户端(调用 backend gateway 业务 API)
// 路径:BASE_URL 由环境变量 TC_API_BASE 或 NEXT_PUBLIC_GATEWAY 配置,默认 /api/teacher-copilot

import type { GradingResult, HomeworkAnalysis, StudentProfile } from "./types"
import { fetch as apiFetch } from "@/core/api/fetcher"

// 同源相对路径:浏览器经 next.config rewrites(/api/teacher-copilot → Gateway)访问,
// 自动携带登录 cookie;避免直连后端端口(跨域/无认证)问题。
const BASE = "/api/teacher-copilot"
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
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

// ---- 图片上传与 OCR(US1 三来源:题目图 → OCR 回填) ----
export async function uploadImage(file: File): Promise<string> {
  const form = new FormData()
  form.append("file", file)
  const res = await apiFetch(`${BASE}/uploads`, { method: "POST", body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail?.message || `上传失败 ${res.status}`)
  }
  const json = await res.json()
  return json.data?.url
}

export async function recognizeQuestionImage(imageUrl: string) {
  return request<{ text: string; blocks: number }>(`/ocr`, {
    method: "POST",
    body: JSON.stringify({ image_url: imageUrl }),
  })
}

export async function searchQuestionBank(
  homeworkId: string,
  params: { subject: string; difficulty?: string | null; knowledge_point?: string | null },
) {
  const qs = new URLSearchParams({ subject: params.subject })
  if (params.difficulty) qs.set("difficulty", params.difficulty)
  if (params.knowledge_point) qs.set("knowledge_point", params.knowledge_point)
  return request<Array<{
    question_bank_item_id: string
    content: string
    difficulty: string | null
    question_type: string
    grade: string | null
  }>>(`/homework/${homeworkId}/question-bank?${qs.toString()}`)
}

// ---- 学生侧(US2:我的作业详情,含我的提交状态) ----
export async function getStudentHomework(homeworkId: string) {
  return request<{
    homework: {
      homework_id: string
      name: string
      subject: string
      status: string
      deadline: string | null
      published_at: string | null
    }
    questions: Array<{
      question_id: string
      question_no: number
      question_type: string
      content: string
      max_score: number
      difficulty: string | null
      my_submission: {
        submission_id: string
        status: string
        current_stage: string
        score: null
      } | null
    }>
  }>(`/homework/${homeworkId}/for-student`)
}

// ---- 业务角色(003:角色分流事实源) ----
export async function getAccountRole(): Promise<{ role: "teacher" | "student" | "none" }> {
  return request<{ role: "teacher" | "student" | "none" }>(`/account/role`)
}
