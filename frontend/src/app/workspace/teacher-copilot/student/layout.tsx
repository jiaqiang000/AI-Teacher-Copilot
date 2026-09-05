// 学生页面守卫：教师身份访问学生作业或批改页时回到教师工作台。
import { requireStudentPage } from "@/components/teacher-copilot/guard"

export default async function StudentPageLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  await requireStudentPage()
  return <>{children}</>
}
