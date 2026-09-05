// Teacher Copilot Agent 页面守卫:学生访问新会话和已有会话都回到学生首页。
import type { ReactNode } from "react";

import { requireTeacherPage } from "@/components/teacher-copilot/guard";

export default async function AgentLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ agent_name: string }>;
}) {
  const { agent_name: agentName } = await params;
  if (agentName === "teacher-copilot") {
    await requireTeacherPage();
  }
  return <>{children}</>;
}
