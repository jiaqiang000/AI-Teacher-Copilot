"use client"
// 教师工作台(对照 Figma 01)- 客户端拉取(带登录态 cookie,经同源代理到 Gateway)
import { useEffect, useState } from "react"

import { getClassProfile, getHomeworkAnalysis } from "@/core/teacher-copilot/api"

const CLASS_ID = "class_03"
const SUBJECT = "math"

export default function DashboardPage() {
  const [profile, setProfile] = useState<Awaited<ReturnType<typeof getClassProfile>> | null>(null)
  const [hwAnalysis, setHwAnalysis] = useState<Awaited<ReturnType<typeof getHomeworkAnalysis>> | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    void Promise.all([
      getClassProfile(CLASS_ID, SUBJECT).catch((e) => { setError((e as Error).message); return null }),
      getHomeworkAnalysis("hw_004", CLASS_ID).catch((e) => { setError((e as Error).message); return null }),
    ])
      .then(([p, a]) => { setProfile(p); setHwAnalysis(a) })
      .catch((e) => { setError((e as Error).message) })
  }, [])

  const recentRate = profile?.overview?.avg_score_rate
  const attentionCount = profile?.attention_students?.length ?? 0
  const weakPoints = profile?.weak_points?.map((w) => w.knowledge_point_key.split(".").pop()) ?? []
  const completionRate = hwAnalysis?.completion?.completion_rate ?? null

  return (
    <div className="p-8 space-y-8">
      <header>
        <h1 className="text-2xl font-bold">教师工作台</h1>
        <p className="text-muted-foreground">今天先处理最值得关注的班级与作业</p>
      </header>

      {/* 体验指引(US5:登录方式/建议步骤/角色切换) */}
      <details className="rounded-lg border p-4 bg-muted/30 text-sm space-y-1">
        <summary className="font-medium cursor-pointer">体验指引(点击展开)</summary>
        <p className="text-muted-foreground">
          <b>教师账号</b> teacher@demo.com / teacher123456 · <b>学生账号</b> student@demo.com / student123456
        </p>
        <p className="text-muted-foreground">
          建议步骤:① 左侧“Copilot 对话”→ 聊天页问“八三班《单元练习》完成率”→ ② 学生账号看作业与批改结果 →
          ③ 教师出题(手动/题库/题目图 OCR)并发布 → ④ 学生上传作答(需配置 OSS)→ 查看新批改结果。
        </p>
        <p className="text-muted-foreground">
          角色切换:退出登录后使用另一账号重新登录。
        </p>
      </details>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="班级" value="3" sub="当前授课" />
        <StatCard label="待批改作业" value="2" sub="今天截止" />
        <StatCard label="重点学生" value={String(attentionCount)} sub="需要关注" />
        <StatCard label="本周平均得分" value={recentRate ? `${Math.round(recentRate * 100)}%` : "—"} sub="较上周 +3.2%" />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <section>
          <h2 className="text-lg font-semibold mb-3">我的班级</h2>
          <ClassCard name="八三班" count="30 名学生" topic={weakPoints.length ? `移项、函数图像需重点关注` : "整体稳定"} />
          <ClassCard name="八四班" count="32 名学生" topic="整体稳定" />
          <ClassCard name="八五班" count="28 名学生" topic="本周作业待发布" />
        </section>
        <section>
          <h2 className="text-lg font-semibold mb-3">最近作业</h2>
          <HomeworkCard name="hw_004 · 周末作业" completion={completionRate} />
          <HomeworkCard name="hw_003 · 单元练习" completion={null} />
          <HomeworkCard name="hw_002 · 方程巩固" completion={null} />
        </section>
      </div>

      {error && <p className="text-red-600 text-sm">数据加载失败: {error}</p>}
    </div>
  )
}

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg border p-4">
      <div className="text-muted-foreground text-sm">{label}</div>
      <div className="text-2xl font-bold my-1">{value}</div>
      <div className="text-xs text-muted-foreground">{sub}</div>
    </div>
  )
}

function ClassCard({ name, count, topic }: { name: string; count: string; topic: string }) {
  return (
    <div className="rounded-lg border p-4 mb-2">
      <div className="font-medium">{name}</div>
      <div className="text-xs text-muted-foreground">{count} · 数学</div>
      <div className="text-sm mt-1">{topic}</div>
    </div>
  )
}

function HomeworkCard({ name, completion }: { name: string; completion: number | null }) {
  return (
    <div className="rounded-lg border p-4 mb-2">
      <div className="font-medium">{name}</div>
      <div className="text-xs text-muted-foreground">
        {completion != null ? `完成 ${Math.round(completion * 100)}%` : "暂无数据"}
      </div>
    </div>
  )
}
