"use client";
// 班级总览页(对照 Figma 02):班级列表来自当前教师的持久化数据。
import Link from "next/link";
import { useEffect, useState } from "react";

import { WorkspaceHeader } from "@/components/workspace/workspace-container";
import { getTeacherClasses } from "@/core/teacher-copilot/api";

type ClassSummary = Awaited<ReturnType<typeof getTeacherClasses>>[number];

export default function ClassesPage() {
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getTeacherClasses()
      .then(setClasses)
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-full w-full">
      <WorkspaceHeader />
      <main className="space-y-6 p-4 sm:p-8">
        <header>
          <h1 className="text-2xl font-bold">我的班级</h1>
          <p className="text-muted-foreground">
            点击班级查看学情画像与重点关注学生
          </p>
        </header>
        {loading && (
          <p className="text-muted-foreground text-sm">正在加载班级...</p>
        )}
        {!loading && error && (
          <p className="text-sm text-red-600">加载失败: {error}</p>
        )}
        {!loading && !error && classes.length === 0 && (
          <p className="text-muted-foreground text-sm">暂无可查看的班级</p>
        )}
        {!loading && !error && classes.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {classes.map((classSummary) => (
              <Link
                key={classSummary.class_id}
                href={`/workspace/teacher-copilot/classes/${classSummary.class_id}`}
                className="rounded-xl border p-5 transition hover:shadow-sm"
              >
                <div className="text-lg font-semibold">{classSummary.name}</div>
                <p className="text-muted-foreground mt-1 text-sm">
                  {classSummary.student_count} 名学生 · 查看学情画像
                </p>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
