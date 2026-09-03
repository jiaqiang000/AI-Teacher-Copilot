// 智能作业批改 · 根路径(003 US-A:未登录→欢迎页;已登录→统一入口按角色分流)
import { redirect } from "next/navigation"
import { cookies } from "next/headers"

import WelcomePage from "./welcome/page"

export default async function RootPage() {
  // 服务端判断是否已登录(仅判 cookie 存在,角色分流交给 workspace 客户端完成)
  const hasSession = !!(await cookies()).get("access_token")
  if (!hasSession) {
    return <WelcomePage />
  }
  redirect("/workspace")
}
