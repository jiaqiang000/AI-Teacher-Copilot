"use client"
// 教师侧边栏业务导航(003 US-B):品牌 logo + 工作台/班级/作业/Copilot 对话。
// 复用 shadcn Sidebar 容器;原生 DeerFlow 导航项由 workspace-sidebar.tsx 不再渲染。
import {
  LayoutDashboard,
  Users,
  FileText,
  MessageSquareText,
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"

import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "/workspace/teacher-copilot/dashboard", label: "教师工作台", icon: LayoutDashboard },
  { href: "/workspace/teacher-copilot/classes", label: "班级", icon: Users },
  // 作业入口按澄清:链到工作台(工作台含最近作业/分析入口),保持轻量
  { href: "/workspace/teacher-copilot/dashboard", label: "作业", icon: FileText },
  // 原生 DeerFlow agent 聊天页(完整流式工具/执行过程 UI,宪法 III 复用优先)
  { href: "/workspace/agents/teacher-copilot/chats/new", label: "Copilot 对话", icon: MessageSquareText },
]

export function TeacherNav() {
  const { state } = useSidebar()
  const pathname = usePathname()

  return (
    <div className="flex flex-col gap-1">
      {/* 品牌文字 logo(003 澄清:无 Figma 稿,极简文字品牌) */}
      <Link
        href="/workspace/teacher-copilot/dashboard"
        className="flex h-12 items-center gap-2 px-3 font-semibold tracking-tight"
      >
        <span className="text-base">智能作业批改</span>
      </Link>
      <SidebarMenu>
        {NAV_ITEMS.map((item) => {
          const active =
            pathname === item.href ||
            (item.href.endsWith("/dashboard") && pathname.startsWith("/workspace/teacher-copilot") && !pathname.includes("/chat"))
          return (
            <SidebarMenuItem key={item.label}>
              <SidebarMenuButton
                asChild
                tooltip={item.label}
                className={cn(active && "bg-muted")}
              >
                <Link href={item.href}>
                  <item.icon />
                  <span>{state === "collapsed" ? "" : item.label}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )
        })}
      </SidebarMenu>

    </div>
  )
}
