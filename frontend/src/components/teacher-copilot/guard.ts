// 教师页面守卫(003 T013):学生身份访问教师页面簇 → 重定向学生首页。
// 服务端组件调用;未映射/教师正常放行(未映射时教师导航可见,避免误锁用户)。
import { redirect } from "next/navigation"

import { getServerSideRole } from "@/core/teacher-copilot/server-role"

export async function requireTeacherPage() {
  const role = await getServerSideRole()
  if (role === "student") {
    // denied=1:学生首页据此弹出"无权限"轻提示(2 秒自动消失,见 student/homework/page.tsx)
    redirect("/workspace/teacher-copilot/student/homework?denied=1")
  }
}

export async function requireStudentPage() {
  const role = await getServerSideRole()
  if (role === "teacher") {
    // denied=student:教师首页据此弹出学生页越权提示(2 秒自动消失)。
    redirect("/workspace/teacher-copilot/dashboard?denied=student")
  }
}
