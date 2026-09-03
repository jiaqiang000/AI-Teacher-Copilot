"use client"
// 工作区统一入口(003 US-C 角色分流):教师→教师工作台;学生→学生作业页;未映射→登录页。
import { useEffect } from "react"
import { redirect } from "next/navigation"

import { useTeacherRole } from "@/core/teacher-copilot/role"

export default function WorkspacePage() {
  const { role } = useTeacherRole()

  useEffect(() => {
    if (role === "teacher") redirect("/workspace/teacher-copilot/dashboard")
    else if (role === "student") redirect("/workspace/teacher-copilot/student/homework")
    else if (role === "none") redirect("/login")
  }, [role])

  return <p className="p-8 text-sm text-muted-foreground">正在进入工作区…</p>
}
