// 003 T013:教师页面簇守卫(classes)—— 学生身份访问自动重定向学生首页。
import { requireTeacherPage } from "@/components/teacher-copilot/guard"

export default async function TeacherPageLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  await requireTeacherPage()
  return <>{children}</>
}
