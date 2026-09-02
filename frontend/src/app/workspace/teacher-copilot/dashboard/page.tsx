// 教师工作台(对照 Figma 01:统计卡 + 我的班级 + 最近作业)
import { getClassProfile, getHomeworkAnalysis } from "@/core/teacher-copilot/api"

// 演示数据默认值(后端 seed:class_03 八三班 / hw_004)
const CLASS_ID = process.env.NEXT_PUBLIC_TC_CLASS_ID || "class_03"
const SUBJECT = process.env.NEXT_PUBLIC_TC_SUBJECT || "math"

export default async function DashboardPage() {
  // 工作台摘要:班级画像 + 最近作业分析(聚合,不新增算法)
  let profile
  try {
    profile = await getClassProfile(CLASS_ID, SUBJECT)
  } catch {
    profile = null
  }
  let hwAnalysis
  try {
    hwAnalysis = await getHomeworkAnalysis("hw_004", CLASS_ID)
  } catch {
    hwAnalysis = null
  }

  const recentRate = profile?.overview?.avg_score_rate
  const attentionCount = profile?.attention_students?.length ?? 0
  const weakPoints = profile?.weak_points?.map((w) => w.knowledge_point_key.split(".").pop()) || []
  const completionRate = hwAnalysis?.completion?.completion_rate

  return (
    <div className="p-8 space-y-8">
      <header>
        <h1 className="text-2xl font-bold">教师工作台</h1>
        <p className="text-muted-foreground">今天先处理最值得关注的班级与作业</p>
      </header>

      {/* 统计卡 */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="班级" value="3" sub="当前授课" />
        <StatCard label="待批改作业" value="2" sub="今天截止" />
        <StatCard label="重点学生" value={String(attentionCount)} sub="需要关注" />
        <StatCard label="本周平均得分" value={recentRate ? `${Math.round(recentRate * 100)}%` : "—"} sub="较上周 +3.2%" />
      </div>

      {/* 我的班级 + 最近作业 */}
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
          <HomeworkCard name="hw_003 · 单元练习" completion={0.0} />
          <HomeworkCard name="hw_002 · 方程巩固" completion={0.0} />
        </section>
      </div>
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
