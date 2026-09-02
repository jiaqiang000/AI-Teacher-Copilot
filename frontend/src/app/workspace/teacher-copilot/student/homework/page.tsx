"use client"
// 学生作业页(对照 Figma 07:完成进度 + 每题作答/批改状态 + 截止时间)
// 真实数据:GET /homework/{id}/for-student(题目 + 我的提交状态)
import { useEffect, useState } from "react"
import Link from "next/link"
import { getStudentHomework } from "@/core/teacher-copilot/api"

const HW_ID = "hw_004"

const STATUS_META: Record<string, { label: string; cls: string }> = {
  SUCCEEDED: { label: "已批改", cls: "bg-green-50 text-green-700" },
  PENDING: { label: "批改中", cls: "bg-amber-50 text-amber-700" },
  RUNNING: { label: "批改中", cls: "bg-amber-50 text-amber-700" },
  FAILED: { label: "批改失败,可重交", cls: "bg-red-50 text-red-600" },
}

export default function StudentHomeworkPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof getStudentHomework>> | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    getStudentHomework(HW_ID)
      .then(setData)
      .catch((e) => setError((e as Error).message))
  }, [])

  const questions = data?.questions ?? []
  const submitted = questions.filter((q) => q.my_submission).length
  const total = questions.length
  const deadline = data?.homework.deadline ? new Date(data.homework.deadline) : null
  const expired = deadline ? deadline.getTime() < Date.now() : false

  return (
    <div className="p-8 space-y-6 max-w-3xl">
      <header>
        <h1 className="text-2xl font-bold">{data?.homework.name || "我的作业"}</h1>
        <p className="text-muted-foreground text-sm">
          学生端 · {total} 道题
          {deadline
            ? ` · 截止 ${deadline.toLocaleString("zh-CN")}${expired ? "(已截止,可查结果)" : ""}`
            : ""}
        </p>
      </header>

      <section className="rounded-lg border p-4">
        <h2 className="font-semibold mb-2">完成进度</h2>
        <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
          <div
            className="h-2 bg-gray-800 transition-all"
            style={{ width: total ? `${(submitted / total) * 100}%` : "0%" }}
          />
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          {submitted} / {total} 已提交
        </p>
      </section>

      <section className="space-y-3">
        {questions.map((q) => {
          const status = q.my_submission?.status
          const meta = (status && STATUS_META[status]) || { label: "待提交", cls: "bg-gray-50 text-gray-500" }
          const href = `/workspace/teacher-copilot/student/grading?homework_id=${HW_ID}&question_id=${q.question_id}`
          return (
            <div key={q.question_id} className="rounded-lg border p-4 flex justify-between items-center">
              <div>
                <div className="text-sm">
                  <span className="rounded bg-gray-100 px-2 py-0.5 mr-2">第 {q.question_no} 题</span>
                  <span className="text-muted-foreground">{q.content.slice(0, 40)}</span>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {q.my_submission ? (
                    <span className={`rounded px-1.5 py-0.5 ${meta.cls}`}>{meta.label}</span>
                  ) : (
                    <span className={`rounded px-1.5 py-0.5 ${meta.cls}`}>{meta.label}</span>
                  )}
                  {q.my_submission?.status === "SUCCEEDED" ? " · 完成" : ""}
                </div>
              </div>
              <Link href={href} className="rounded border px-3 py-1 text-sm hover:bg-gray-50">
                {q.my_submission ? "查看/重交结果" : "开始作答"}
              </Link>
            </div>
          )
        })}
      </section>

      {error && <p className="text-red-600 text-sm">加载失败: {error}</p>}
    </div>
  )
}
