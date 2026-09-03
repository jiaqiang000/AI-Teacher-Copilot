"use client"
// 业务角色 Hook(003 品牌与导航整合):登录用户是教师还是学生(AccountLink 事实源)。
// 用法:const { role, loading } = useTeacherRole()
// 说明:内存缓存(会话内避免重复请求);失败降级为 none(未映射/未登录),由调用方决策。
import { useCallback, useEffect, useState } from "react"

import { getAccountRole } from "./api"

export type BizRole = "teacher" | "student" | "none"

export function useTeacherRole() {
  const [role, setRole] = useState<BizRole | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getAccountRole()
      setRole(data.role)
    } catch {
      // 未登录/未映射/网络异常:统一按 none 处理,不阻塞页面(由调用方做跳转决策)
      setRole("none")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return { role, loading, refresh }
}
