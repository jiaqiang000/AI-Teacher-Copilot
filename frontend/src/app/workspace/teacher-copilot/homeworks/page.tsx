"use client";
// 作业管理页(对照 Figma 04/05):作业摘要和所属班级来自当前教师的真实数据。
import Link from "next/link";
import { useEffect, useState } from "react";

import { WorkspaceHeader } from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import { getTeacherHomeworks } from "@/core/teacher-copilot/api";
import {
  statusLabel,
  subjectLabel,
} from "@/core/teacher-copilot/display-labels";

export default function HomeworksPage() {
  const { t } = useI18n();
  const [homeworks, setHomeworks] = useState<
    Awaited<ReturnType<typeof getTeacherHomeworks>>
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getTeacherHomeworks({ limit: 100 })
      .then(setHomeworks)
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-full w-full">
      <WorkspaceHeader />
      <main className="space-y-6 p-4 sm:p-8">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">作业管理</h1>
            <p className="text-muted-foreground">
              查看作业状态、进入分析或继续编辑草稿
            </p>
          </div>
          <Link
            href="/workspace/teacher-copilot/homeworks/new/authoring"
            className="rounded bg-black px-4 py-2 text-sm text-white hover:bg-gray-800"
          >
            创建作业
          </Link>
        </header>

        {loading && (
          <p className="text-muted-foreground text-sm">正在加载作业...</p>
        )}
        {!loading && error && (
          <p className="text-sm text-red-600">加载失败: {error}</p>
        )}
        {!loading && !error && homeworks.length === 0 && (
          <section className="text-muted-foreground rounded-lg border p-6 text-sm">
            暂无作业，先创建一份作业吧。
          </section>
        )}
        {!loading && !error && homeworks.length > 0 && (
          <div className="space-y-3">
            {homeworks.map((homework) => (
              <article
                key={homework.homework_id}
                className="rounded-lg border p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="font-semibold">{homework.name}</h2>
                    <p className="text-muted-foreground mt-1 text-sm">
                      {homework.class_name} ·{" "}
                      {subjectLabel(homework.subject, t.teacherCopilot)} ·{" "}
                      {statusLabel(homework.status, t.teacherCopilot)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2 text-sm">
                    {homework.status === "DRAFT" ? (
                      <Link
                        href={`/workspace/teacher-copilot/homeworks/${homework.homework_id}/authoring`}
                        className="rounded border px-3 py-1 hover:bg-gray-50"
                      >
                        继续编辑
                      </Link>
                    ) : (
                      <Link
                        href={`/workspace/teacher-copilot/homeworks/${homework.homework_id}/analysis?class_id=${homework.class_id}`}
                        className="rounded border px-3 py-1 hover:bg-gray-50"
                      >
                        查看分析
                      </Link>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
