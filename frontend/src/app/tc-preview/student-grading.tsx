"use client"
// 学生批改页(对照 Figma 08:题目/答案卡 + 五步进度 + 批改结果)
// 进度步骤:图片上传 → OCR → 解析 → 批改 → 生成结果(复用 ChainOfThought 思路)
import { useCallback, useEffect, useState } from "react"
import { getGradingResult, getSubmission, submitAnswer } from "@/core/teacher-copilot/api"
import type { GradingResult } from "@/core/teacher-copilot/types"

const STAGES = [
  { key: "UPLOAD", label: "图片上传完成" },
  { key: "OCR", label: "OCR 识别完成" },
  { key: "PARSING", label: "作答解析完成" },
  { key: "GRADING", label: "正在批改" },
  { key: "ASSEMBLING", label: "正在生成批改结果" },
]

// 演示:直接提供已上传答案的 submission(真实接入由上传 → POST /submissions → SSE)
const DEMO_SUBMISSION = "sub_smoke1"

export default function StudentGradingPage() {
  const [status, setStatus] = useState<string>("RUNNING")
  const [stage, setStage] = useState<string>("GRADING")
  const [result, setResult] = useState<GradingResult | null>(null)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    try {
      const sub = await getSubmission(DEMO_SUBMISSION)
      setStatus(sub.status)
      setStage(sub.current_stage)
      if (sub.status === "SUCCEEDED") {
        const r = await getGradingResult(DEMO_SUBMISSION)
        setResult(r)
      }
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    load()
    // 模拟进度推进:真实场景由 SSE 事件驱动(见 core/grading/hooks)
    const timer = setInterval(async () => {
      await load()
    }, 3000)
    return () => clearInterval(timer)
  }, [load])

  const stageIndex = STAGES.findIndex((s) => s.key === stage)

  return (
    <div className="p-8 space-y-5 max-w-3xl">
      <header>
        <h1 className="text-2xl font-bold">第 3 题 · 函数图像综合</h1>
        <p className="text-muted-foreground text-sm">上传一张图片 = 一道题 · 当前 Submission</p>
      </header>

      <section className="rounded-lg border p-4">
        <h2 className="text-sm font-semibold mb-1">题目</h2>
        <p className="text-sm">根据函数图像判断区间变化,并说明理由。</p>
      </section>

      <section className="rounded-lg border p-4">
        <h2 className="text-sm font-semibold mb-1">你的答案</h2>
        <p className="text-sm text-muted-foreground">answer_003.jpg · 上传完成</p>
      </section>

      {/* 进度(对照 Figma 08) */}
      <section className="rounded-lg border p-4">
        <div className="flex justify-between items-center">
          <h2 className="font-semibold">AI Teacher · 正在批改</h2>
          <span className="text-xs text-muted-foreground">status: {status} · current_stage: {stage}</span>
        </div>
        <ul className="mt-3 space-y-1 text-sm">
          {STAGES.map((s, i) => (
            <li key={s.key} className="flex items-center gap-2">
              <span className="w-4">{i < stageIndex ? "✓" : i === stageIndex ? "●" : "○"}</span>
              {s.label}
            </li>
          ))}
        </ul>
      </section>

      {/* 批改结果区:SUCCEEDED 后展示 GradingResultMessage(参考业务文档:完成后才展示) */}
      <section className="rounded-lg border p-4">
        <h2 className="font-semibold mb-2">批改结果{result ? "" : "预览"}</h2>
        {result ? (
          <ResultView result={result} />
        ) : (
          <p className="text-sm text-muted-foreground">批改完成后展示结果(数学步骤分与错误定位)</p>
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
        <span className="text-sm text-muted-foreground ml-2">({Math.round(result.score.rate * 100)}%)</span>
      </div>
      <p className="mt-2 text-sm">{result.feedback.summary}</p>
      {result.math_detail && (
        <ul className="mt-3 space-y-1 text-sm">
          {result.math_detail.steps.map((s) => (
            <li key={s.step_index} className="flex justify-between border-b py-1">
              <span>{s.description}</span>
              <span className="text-muted-foreground">{s.status} · {s.earned_score}/{s.max_score}</span>
            </li>
          ))}
        </ul>
      )}
      {result.english_essay_detail && (
        <ul className="mt-3 space-y-1 text-sm">
          {Object.entries(result.english_essay_detail.dimension_scores).map(([k, v]) => (
            <li key={k} className="flex justify-between border-b py-1">
              <span>{k}</span>
              <span>{v.score}/{v.max_score}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
