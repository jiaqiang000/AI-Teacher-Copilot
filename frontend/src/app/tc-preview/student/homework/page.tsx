"use client"
// 学生作业列表(对照 Figma 07:完成进度 + 每题作答/批改状态 + 截止时间)
import { useEffect, useState } from "react"
import { getHomework } from "@/core/teacher-copilot/api"

const HW_ID = "hw_004"

export default function StudentHomeworkPage() {
  const [homework, setHomework] = useState<Awaited<ReturnType<typeof getHomework>> | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    getHomework(HW_ID).then(setHomework).catch((e) => setError((e as Error).message))
  }, [])

  const total = homework?.questions.length ?? 3
  const done = 2 // 演示:已批改 2 题

  return (
    <div className="p-8 space-y-6 max-w-3xl">
      <header>
        <h1 className="text-2xl font-bold">{homework?.name || "八年级数学周末作业"}</h1>
        <p className="text-muted-foreground text-sm">学生端 · 3 道题{homework?.deadline ? ` · 截止 ${new Date(homework.deadline).toLocaleString("zh-CN")}` : ""}</p>
      </header>

      <section className="rounded-lg border p-4">
        <h2 className="font-semibold mb-2">完成进度</h2>
        <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
          <div className="h-2 bg-gray-800" style={{ width: `${(done / total) * 100}%` }} />
        </div>
        <p className="text-sm text-muted-foreground mt-1">{done} / {total} 已提交</p>
      </section>

      <section className="space-y-3">
        {[1, 2, 3].map((no) => (
          <QuestionCard key={no} no={no} done={no <= done} />
        ))}
      </section>
    </div>
  )
}

function QuestionCard({ no, done }: { no: number; done: boolean }) {
  return (
    <div className="rounded-lg border p-4 flex justify-between items-center">
      <div>
        <div className="text-sm">
          <span className="rounded bg-gray-100 px-2 py-0.5 mr-2">第 {no} 题</span>
        </div>
        <div className="text-xs text-muted-foreground mt-1">
          {done ? "已批改 · 8/10" : "待提交"}
        </div>
      </div>
      <button className="rounded border px-3 py-1 text-sm">
        {done ? "查看结果" : "开始作答"}
      </button>
    </div>
  )
}
