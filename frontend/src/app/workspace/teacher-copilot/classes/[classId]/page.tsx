"use client"
// 班级详情(对照 Figma 02:画像概览 + 长期薄弱/共性错误 + 重点关注学生)
// 客户端组件:服务端调用会因无浏览器 cookie(CSRF)而失败,与 dashboard 同模式。
import { useEffect, useState } from "react"
import { getClassProfile } from "@/core/teacher-copilot/api"

const CLASS_ID = process.env.NEXT_PUBLIC_TC_CLASS_ID || "class_03"
const SUBJECT = process.env.NEXT_PUBLIC_TC_SUBJECT || "math"

export default function ClassDetailPage() {
  const [profile, setProfile] = useState<Awaited<ReturnType<typeof getClassProfile>> | null>(null)
  useEffect(() => {
    getClassProfile(CLASS_ID, SUBJECT).then(setProfile).catch(() => setProfile(null))
  }, [])
  const weak = profile?.weak_points ?? []
  const errors = profile?.common_errors ?? []
  const attention = profile?.attention_students ?? []
  const avg = profile?.overview?.avg_score_rate

  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-2xl font-bold">八三班 · 数学</h1>
        <p className="text-muted-foreground">30 名学生 · 长期画像更新于刚刚</p>
      </header>

      <div className="grid grid-cols-4 gap-4">
        <Stat label="平均得分率" value={avg ? `${Math.round(avg * 100)}%` : "—"} sub="最近 14 天" />
        <Stat label="学习趋势" value="改善" sub="+4.8%" />
        <Stat label="薄弱知识点" value={String(weak.length)} sub="长期画像" />
        <Stat label="重点学生" value={String(attention.length)} sub="需优先跟进" />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <section>
          <h2 className="text-lg font-semibold mb-2">长期薄弱知识点</h2>
          <p className="text-xs text-muted-foreground mb-2">ProfileAlgorithmV1</p>
          {weak.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无长期薄弱点</p>
          ) : (
            weak.map((w) => (
              <div key={w.knowledge_point_key} className="rounded border px-3 py-2 mb-2">
                <span className="text-sm">{w.knowledge_point_key.split(".").pop()}</span>
                <span className="text-xs text-muted-foreground ml-2">
                  掌握度 {w.avg_mastery ? Math.round(w.avg_mastery * 100) : "—"}% · {w.weak_student_count} 人薄弱
                </span>
              </div>
            ))
          )}
        </section>
        <section>
          <h2 className="text-lg font-semibold mb-2">共性错误</h2>
          <p className="text-xs text-muted-foreground mb-2">最近 28 天</p>
          {errors.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无共性错误</p>
          ) : (
            errors.map((e) => (
              <div key={`${e.error_code}-${e.knowledge_point_key}`} className="rounded border px-3 py-2 mb-2 text-sm">
                {e.error_code} · {e.affected_student_count} 人
              </div>
            ))
          )}
        </section>
      </div>

      <section>
        <h2 className="text-lg font-semibold mb-2">重点关注学生</h2>
        <p className="text-xs text-muted-foreground mb-2">长期画像 + 近期趋势</p>
        {attention.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无重点学生</p>
        ) : (
          <ul className="space-y-2">
            {attention.map((s) => (
              <li key={s.student_id} className="rounded border px-3 py-2 text-sm">
                <span className="font-medium">{s.student_id}</span>
                <span className="text-muted-foreground ml-3">{s.reason_codes.join(" / ")}</span>
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
