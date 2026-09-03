// 教师页面守卫(003 T013):学生身份访问教师页面簇 → 重定向学生首页。
// 服务端组件调用;未映射/教师正常放行(未映射时教师导航可见,避免误锁用户)。
import { redirect } from "next/navigation"

import { getServerSideRole } from "@/core/teacher-copilot/server-role"

export async function requireTeacherPage() {
  const role = await getServerSideRole()
  if (role === "student") {
    redirect("/workspace/teacher-copilot/student/homework")
  }
}
