"use client"
// 学生批改页(对照 Figma 08:题目/答案卡 + 五步进度 + 批改结果)
// 真实流程:选图上传(OSS)→ POST /submissions → 轮询进度 → 批改结果
import { useCallback, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import {
  getGradingResult,
  getStudentHomework,
  getSubmission,
  submitAnswer,
  uploadImage,
} from "@/core/teacher-copilot/api"
import type { GradingResult } from "@/core/teacher-copilot/types"

const STAGES = [
  { key: "UPLOAD", label: "图片上传完成" },
  { key: "OCR", label: "OCR 识别完成" },
  { key: "PARSING", label: "作答解析完成" },
  { key: "GRADING", label: "正在批改" },
  { key: "ASSEMBLING", label: "正在生成批改结果" },
]

export default function StudentGradingPage() {
  const params = useSearchParams()
  const homeworkId = params.get("homework_id") || "hw_004"
  const questionId = params.get("question_id") || ""

  const [question, setQuestion] = useState<
    Awaited<ReturnType<typeof getStudentHomework>>["questions"][number] | null
  >(null)
  const [submissionId, setSubmissionId] = useState<string | null>(null)
  const [status, setStatus] = useState<string>("")
  const [stage, setStage] = useState<string>("")
  const [result, setResult] = useState<GradingResult | null>(null)
  const [uploadedUrl, setUploadedUrl] = useState<string>("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  const refreshResult = useCallback(async (sid: string) => {
    try {
      const r = await getGradingResult(sid)
      setResult(r)
    } catch {
      /* 结果尚未生成时忽略 */
    }
  }, [])

  // 载入作业题目 + 已有提交
  const loadView = useCallback(async () => {
    try {
      const data = await getStudentHomework(homeworkId)
      const q =
        data.questions.find((it) => it.question_id === questionId) || data.questions[0]
      setQuestion(q ?? null)
      if (q?.my_submission) {
        setSubmissionId(q.my_submission.submission_id)
        setStatus(q.my_submission.status)
        setStage(q.my_submission.current_stage)
        if (q.my_submission.status === "SUCCEEDED") {
          await refreshResult(q.my_submission.submission_id)
        }
      }
    } catch (e) {
      setError((e as Error).message)
    }
  }, [homeworkId, questionId, refreshResult])

  useEffect(() => {
    void loadView()
  }, [loadView])

  // 提交后轮询进度(复盘恢复;V1 契约亦支持 SSE events 流)
  useEffect(() => {
    if (!submissionId || status === "SUCCEEDED" || status === "FAILED") return
    const timer = setInterval(async () => {
      try {
        const sub = await getSubmission(submissionId)
        setStatus(sub.status)
        setStage(sub.current_stage)
        if (sub.status === "SUCCEEDED") await refreshResult(submissionId)
      } catch {
        /* 轮询失败下一轮重试 */
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [submissionId, status, refreshResult])

  async function handleUpload(file: File) {
    setBusy(true)
    setError("")
    try {
      const url = await uploadImage(file)
      setUploadedUrl(url)
      const res = await submitAnswer({
        question_id: questionId,
        homework_id: homeworkId,
        image_url: url,
      })
      setSubmissionId(res.submission_id)
      setStatus(res.status)
      setStage(res.current_stage)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const stageIndex = status === "SUCCEEDED" ? STAGES.length : STAGES.findIndex((s) => s.key === stage)

  return (
    <div className="p-8 space-y-5 max-w-3xl">
      <header>
        <h1 className="text-2xl font-bold">
          第 {question?.question_no ?? "-"} 题
          {question?.difficulty ? ` · ${question.difficulty}` : ""}
        </h1>
        <p className="text-muted-foreground text-sm">
          上传一张图片 = 一道题 · 由 AI Teacher 批改
        </p>
      </header>

      <section className="rounded-lg border p-4">
        <h2 className="text-sm font-semibold mb-1">题目</h2>
        <p className="text-sm whitespace-pre-wrap">{question?.content || "加载中..."}</p>
      </section>

      <section className="rounded-lg border p-4">
        <h2 className="text-sm font-semibold mb-2">你的答案</h2>
        {!uploadedUrl && !submissionId && (
          <label className="block rounded border border-dashed p-4 text-center text-sm text-muted-foreground cursor-pointer hover:bg-gray-50">
            {busy ? "上传中..." : "选择手写作答图片上传(jpg/png, ≤10MB)"}
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void handleUpload(f)
              }}
            />
          </label>
        )}
        {(uploadedUrl || submissionId) && (
          <p className="text-sm text-muted-foreground">
            {uploadedUrl
              ? "✚ 作答图片已上传并提交批改"
              : `✚ 已提交(${submissionId})`}
          </p>
        )}
      </section>

      {submissionId && (
        <section className="rounded-lg border p-4">
          <div className="flex justify-between items-center">
            <h2 className="font-semibold">AI Teacher · 正在批改</h2>
            <span className="text-xs text-muted-foreground">
              status: {status} · stage: {stage}
            </span>
          </div>
          <ul className="mt-3 space-y-1 text-sm">
            {STAGES.map((s, i) => (
              <li key={s.key} className="flex items-center gap-2">
                <span className="w-4">
                  {i < stageIndex ? "✓" : i === stageIndex ? "●" : "○"}
                </span>
                {s.label}
              </li>
            ))}
          </ul>
          {status === "FAILED" && (
            <p className="text-red-600 text-sm mt-2">批改失败,请上传重试。</p>
          )}
        </section>
      )}

      <section className="rounded-lg border p-4">
        <h2 className="font-semibold mb-2">批改结果{result ? "" : "(完成后展示)"}</h2>
        {result ? (
          <ResultView result={result} />
        ) : (
          <p className="text-sm text-muted-foreground">
            批改完成后展示结果(数学步骤分与错误定位)
          </p>
        )}
      </section>

      {error && <p className="text-red-600 text-sm">{error}</p>}
    </div>
  )
}

function ResultView({ result }: { result: GradingResult }) {
  return (
    <div>
      <div className="text-3xl font-bold">
        {result.score.earned} / {result.score.max}
        <span className="text-sm text-muted-foreground ml-2">
          ({Math.round(result.score.rate * 100)}%)
        </span>
      </div>
      <p className="mt-2 text-sm">{result.feedback.summary}</p>
      {result.math_detail && (
        <ul className="mt-3 space-y-1 text-sm">
          {result.math_detail.steps.map((s) => (
            <li key={s.step_index} className="flex justify-between border-b py-1">
              <span>{s.description}</span>
              <span className="text-muted-foreground">
                {s.status} · {s.earned_score}/{s.max_score}
              </span>
            </li>
          ))}
        </ul>
      )}
      {result.english_essay_detail && (
        <ul className="mt-3 space-y-1 text-sm">
          {Object.entries(result.english_essay_detail.dimension_scores).map(([k, v]) => (
            <li key={k} className="flex justify-between border-b py-1">
              <span>{k}</span>
              <span>
                {v.score}/{v.max_score}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
