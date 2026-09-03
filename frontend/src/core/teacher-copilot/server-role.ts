// 服务端角色查询(003 US-C):服务端组件读取当前登录用户的业务角色(教师/学生)。
// 与 getServerSideUser 同模式:直连 Gateway 内部地址,带请求 cookie。
import { cookies } from "next/headers"

import { getGatewayConfig } from "@/core/auth/gateway-config"

export async function getServerSideRole(): Promise<"teacher" | "student" | "none"> {
  try {
    const cookieStore = await cookies()
    const sessionCookie = cookieStore.get("access_token")?.value
    if (!sessionCookie) return "none"
    const { internalGatewayUrl } = getGatewayConfig()
    const res = await fetch(`${internalGatewayUrl}/api/teacher-copilot/account/role`, {
      headers: { Cookie: `access_token=${sessionCookie}` },
      cache: "no-store",
    })
    if (!res.ok) return "none"
    const json = (await res.json()) as { data?: { role?: string } }
    const role = json.data?.role
    return role === "teacher" || role === "student" ? role : "none"
  } catch {
    // 网关不可达时按未映射处理,不阻塞工作区(教师默认可见)
    return "none"
  }
}
