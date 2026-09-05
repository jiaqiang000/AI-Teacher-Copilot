import { redirect } from "next/navigation";

// 兼容旧书签，独立引导页已合并到登录页。
export default function WelcomePage() {
  redirect("/login");
}
