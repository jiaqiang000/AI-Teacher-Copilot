// 未登录统一进入合并后的登录页；已登录仍由工作区按角色分流。
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export default async function RootPage() {
  // 服务端判断是否已登录(仅判 cookie 存在,角色分流交给 workspace 客户端完成)
  const hasSession = !!(await cookies()).get("access_token");
  if (!hasSession) {
    redirect("/login");
  }
  redirect("/workspace");
}
