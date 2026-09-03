"use client"
// 智能作业批改 · 欢迎页(003 US-A,无 Figma 稿的自建极简品牌化外壳)
// 未登录首屏:产品名/一句介绍 + 教师演示/学生演示两入口卡 + 体验账号提示 + 登录按钮。
import Link from "next/link"

export default function WelcomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-6">
      <div className="w-full max-w-lg space-y-8 text-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight">智能作业批改</h1>
          <p className="text-muted-foreground mt-2">
            教师智能助手——让每一份作业都被看见
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Link
            href="/login"
            className="group rounded-xl border p-5 text-left transition hover:border-primary hover:shadow-sm"
          >
            <div className="text-lg font-semibold">教师演示</div>
            <p className="text-muted-foreground mt-1 text-sm">
              出题、发布、学情画像、作业分析、Copilot 问答
            </p>
            <p className="text-xs text-primary mt-3">teacher@demo.com</p>
          </Link>
          <Link
            href="/login"
            className="group rounded-xl border p-5 text-left transition hover:border-primary hover:shadow-sm"
          >
            <div className="text-lg font-semibold">学生演示</div>
            <p className="text-muted-foreground mt-1 text-sm">
              查看作业、上传作答、实时批改进度与结果
            </p>
            <p className="text-xs text-primary mt-3">student@demo.com</p>
          </Link>
        </div>

        <div className="space-y-1 text-sm text-muted-foreground">
          <p>体验账号:教师 teacher@demo.com / teacher123456</p>
          <p>学生 student@demo.com / student123456</p>
        </div>

        <Link
          href="/login"
          className="inline-block rounded-md bg-primary px-8 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          登录
        </Link>
      </div>
    </div>
  )
}
