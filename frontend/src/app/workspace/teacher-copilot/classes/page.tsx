"use client"
// 班级总览页(003 US-B:侧边栏"班级"入口落地页)。
// 轻量:LIST 显示预置班级卡(八三班/八四班/八五班),点击进入班级详情(对照 Figma 02)。
// 说明:演示数据为固定 3 班(V1 种子),不新增后端接口(宪法 V)。
import Link from "next/link"

const CLASSES = [
  { id: "class_03", name: "八三班", desc: "30 名学生 · 数学 · 整体稳定" },
  { id: "class_04", name: "八四班", desc: "32 名学生 · 数学 · 整体稳定" },
  { id: "class_05", name: "八五班", desc: "28 名学生 · 数学 · 本周作业待发布" },
]

export default function ClassesPage() {
  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-2xl font-bold">我的班级</h1>
        <p className="text-muted-foreground">点击班级查看学情画像与重点关注学生</p>
      </header>
      <div className="grid gap-4 md:grid-cols-3">
        {CLASSES.map((c) => (
          <Link
            key={c.id}
            href={`/workspace/teacher-copilot/classes/${c.id}`}
            className="rounded-xl border p-5 transition hover:shadow-sm"
          >
            <div className="text-lg font-semibold">{c.name}</div>
            <p className="text-muted-foreground mt-1 text-sm">{c.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
