"use client"
// 作业分析(对照 Figma 05:统计卡 + 成绩分布/低表现知识点 + 题目表现下钻)
// 客户端组件:服务端调用会因无浏览器 cookie(CSRF)而失败,与 dashboard 同模式。
import { useEffect, useState } from "react"
import { getHomeworkAnalysis } from "@/core/teacher-copilot/api"

const CLASS_ID = process.env.NEXT_PUBLIC_TC_CLASS_ID || "class_03"
const HW_ID = process.env.NEXT_PUBLIC_TC_HW_ID || "hw_004"

export default function AnalysisPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof getHomeworkAnalysis>> | null>(null)
  useEffect(() => {
    getHomeworkAnalysis(HW_ID, CLASS_ID).then(setData).catch(() => setData(null))
  }, [])
  const completion = data?.completion
  const perf = data?.performance
  const dist = perf?.score_distribution
  const kps = data?.knowledge_points ?? []
  const questions = data?.questions ?? []
  const attention = data?.attention_students ?? []

  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{HW_ID} · 作业分析</h1>
        <p className="text-muted-foreground text-sm">八三班 · 本周数学周末作业</p>
      </header>

      <div className="grid grid-cols-4 gap-4">
        <Stat label="完成率" value={completion?.completion_rate != null ? `${Math.round(completion.completion_rate * 100)}%` : "—"} sub={`${completion?.submitted_student_count ?? 0}/${completion?.assigned_student_count ?? 0}`} />
        <Stat label="完整批改" value={String(perf?.graded_student_count ?? 0)} sub="学生" />
        <Stat label="平均得分率" value={perf?.avg_score_rate != null ? `${Math.round(perf.avg_score_rate * 100)}%` : "—"} sub="fully graded" />
        <Stat label="最高错题" value={questions[0]?.question_no ? `第${questions[0].question_no}题` : "—"} sub={questions[0]?.error_rate != null ? `错误率 ${Math.round(questions[0].error_rate * 100)}%` : ""} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <section>
          <h2 className="text-lg font-semibold mb-2">成绩分布</h2>
          <p className="text-xs text-muted-foreground mb-2">按 fully graded students</p>
          {dist ? (
            <ul className="text-sm space-y-1">
              <li>&lt;60&nbsp;&nbsp;{dist.below_60} 人</li>
              <li>60-79&nbsp;&nbsp;{dist.from_60_to_79} 人</li>
              <li>80-89&nbsp;&nbsp;{dist.from_80_to_89} 人</li>
              <li>90-100&nbsp;&nbsp;{dist.from_90_to_100} 人</li>
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">暂无数据</p>
          )}
        </section>
        <section>
          <h2 className="text-lg font-semibold mb-2">本次低表现知识点</h2>
          <p className="text-xs text-muted-foreground mb-2">即时 Analysis ≠ 长期 weak point</p>
          {kps.length === 0 ? (
            <p className="text-sm text-muted-foreground">无</p>
          ) : (
            kps.slice(0, 3).map((kp) => (
              <div key={kp.knowledge_point_key} className="rounded border px-3 py-2 mb-2 text-sm">
                {kp.knowledge_point_key.split(".").pop()} · avg {kp.avg_performance != null ? Math.round(kp.avg_performance * 100) : "—"}%
              </div>
            ))
          )}
        </section>
      </div>

      <section>
        <h2 className="text-lg font-semibold mb-2">题目表现</h2>
        <p className="text-xs text-muted-foreground mb-2">点击可下钻 Question Analysis</p>
        {questions.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {questions.map((q) => (
              <li key={q.question_id} className="rounded border px-3 py-2 flex justify-between">
                <span>第{q.question_no}题</span>
                <span className="text-muted-foreground">
                  错误率 {q.error_rate != null ? `${Math.round(q.error_rate * 100)}%` : "—"}
                  {q.common_errors[0] ? ` · ${q.common_errors[0].error_code}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg border p-4">
      <div className="text-muted-foreground text-sm">{label}</div>
      <div className="text-2xl font-bold my-1">{value}</div>
      <div className="text-xs text-muted-foreground">{sub}</div>
    </div>
  )
}
