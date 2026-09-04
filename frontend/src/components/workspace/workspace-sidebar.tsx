"use client";

import { TeacherNav } from "@/components/teacher-copilot/teacher-nav";
import {
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarRail,
} from "@/components/ui/sidebar";

import { WorkspaceNavMenu } from "./workspace-nav-menu";
// 003:原生 DeerFlow 导航(New chat/Chats/Agents/Channels/Recent chats)在 UI 中隐藏,
// 组件文件保留(URL 直连原生能力仍可用)。

export function WorkspaceSidebar({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  return (
    <>
      <Sidebar variant="sidebar" collapsible="icon" {...props}>
        {/* 品牌 logo 已由 TeacherNav 顶部呈现,头部不再渲染 DeerFlow 原始 header */}
        <SidebarHeader className="py-0" />
        <SidebarContent>
          {/* 003 US-B:教师教学业务导航(品牌 logo + 工作台/班级/作业/Copilot 对话) */}
          <TeacherNav />
        </SidebarContent>
        <SidebarFooter>
          <WorkspaceNavMenu />
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>
    </>
  );
}
