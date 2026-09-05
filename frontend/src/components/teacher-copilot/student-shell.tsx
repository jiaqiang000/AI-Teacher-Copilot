"use client"
// 学生侧边栏外壳(003 US-C 独立学生外壳):品牌 logo + 学生入口,无教师管理入口。
import { GraduationCap, ListChecks, FileCheck2 } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import { WorkspaceNavMenu } from "@/components/workspace/workspace-nav-menu"
import { cn } from "@/lib/utils"

const STUDENT_ITEMS = [
  { href: "/workspace/teacher-copilot/student/homework", label: "我的作业", icon: ListChecks },
  { href: "/workspace/teacher-copilot/student/grading?homework_id=hw_004&question_id=q001", label: "批改结果", icon: FileCheck2 },
]

export function StudentShell({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()
  return (
    <Sidebar variant="sidebar" collapsible="icon" {...props}>
      <SidebarHeader className="py-0">
        <Link
          href="/workspace/teacher-copilot/student/homework"
          className="flex h-12 items-center gap-2 px-3 font-semibold tracking-tight"
        >
          <GraduationCap className="size-5" />
          <span>智能作业批改</span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarMenu>
          {STUDENT_ITEMS.map((item) => (
            <SidebarMenuItem key={item.label}>
              <SidebarMenuButton asChild tooltip={item.label} className={cn(pathname.startsWith(item.href.split("?")[0] ?? item.href) && "bg-muted")}>
                <Link href={item.href}>
                  <item.icon />
                  <span>{item.label}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarContent>
      <SidebarFooter>
        <WorkspaceNavMenu />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
