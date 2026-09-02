// 学生画像(对照 Figma 03:指标卡 + 知识点掌握 + 重复错误 + 最近批改记录)
import { getStudentProfile, getStudentHistory } from "@/core/teacher-copilot/api"

const SUBJECT = process.env.NEXT_PUBLIC_TC_SUBJECT || "math"
const STUDENT_ID = process.env.NEXT_PUBLIC_TC_STUDENT_ID || "stu_003"

export default async function StudentProfilePage() {
  let profile
  try {
    profile = await getStudentProfile(STUDENT_ID, SUBJECT)
  } catch {
    profile = null
  }
  let history: Array<Record<string, unknown>> = []
  try {
    history = await getStudentHistory(STUDENT_ID, SUBJECT)
  } catch {
    history = []
  }
  const overview = profile?.overview
  const weak = profile?.weak_points ?? []
  const recurring = profile?.recurring_errors ?? []

  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-2xl font-bold">张三 · 学生画像</h1>
        <p className="text-muted-foreground">八三班 · 数学 · profile_v1</p>
      </header>

      <div className="grid grid-cols-4 gap-4">
        <Stat label="平均得分率" value={overview?.avg_score_rate ? `${Math.round(overview.avg_score_rate * 100)}%` : "—"} sub="历史" />
        <Stat label="近期得分率" value={overview?.recent_score_rate != null ? `${Math.round(overview.recent_score_rate * 100)}%` : "—"} sub="最近 14 天" />
        <Stat label="趋势" value={overview?.trend || "—"} sub={overview?.trend === "declining" ? "declining" : "稳定"} />
        <Stat label="累计作答" value={String(overview?.attempt_count ?? 0)} sub="有效结果" />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <section>
          <h2 className="text-lg font-semibold mb-2">知识点掌握</h2>
          <p className="text-xs text-muted-foreground mb-2">基于 performance 加权</p>
          {(profile?.knowledge_points ?? []).map((kp) => (
            <div key={kp.knowledge_point_key} className="rounded border px-3 py-2 mb-2 text-sm">
              <span>{kp.knowledge_point_key.split(".").pop()}</span>
              <span className="text-muted-foreground ml-2">
                {kp.mastery != null ? `${Math.round(kp.mastery * 100)}%` : "—"}
                {kp.mastery != null && kp.mastery < 0.6 && kp.attempt_count >= 3 ? " · 长期薄弱" : ""}
              </span>
            </div>
          ))}
        </section>
        <section>
          <h2 className="text-lg font-semibold mb-2">重复错误</h2>
          <p className="text-xs text-muted-foreground mb-2">最近 28 天</p>
          {recurring.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无重复错误</p>
          ) : (
            recurring.map((e) => (
              <div key={`${e.error_code}-${e.knowledge_point_key}`} className="rounded border px-3 py-2 mb-2 text-sm">
                {e.error_code} ×{e.recent_occurrence_count}
                <span className="text-muted-foreground ml-2">关联 {e.knowledge_point_key.split(".").pop()}</span>
              </div>
            ))
          )}
        </section>
      </div>

      <section>
        <h2 className="text-lg font-semibold mb-2">最近批改记录</h2>
        <p className="text-xs text-muted-foreground mb-2">只展示当前有效 GradingResult</p>
        {history.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无历史记录</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {history.slice(0, 5).map((h) => (
              <li key={String(h.grading_result_id)} className="rounded border px-3 py-2">
                {String(h.difficulty || "-")} · {Math.round(Number((h.score as { rate: number })?.rate || 0) * 100)}%
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
