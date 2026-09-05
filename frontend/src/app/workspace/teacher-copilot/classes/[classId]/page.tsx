"use client";
// 班级详情(对照 Figma 02):按路由 classId 展示当前教师可见的持久化画像。
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { WorkspaceHeader } from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import { getClassProfile } from "@/core/teacher-copilot/api";
import {
  algorithmVersionLabel,
  errorTypeLabel,
  knowledgePointLabel,
  reasonLabels,
  subjectLabel,
  trendLabel,
} from "@/core/teacher-copilot/display-labels";

const SUBJECT = process.env.NEXT_PUBLIC_TC_SUBJECT ?? "math";

export default function ClassDetailPage() {
  const { t } = useI18n();
  const { classId } = useParams<{ classId: string }>();
  const [profile, setProfile] = useState<Awaited<
    ReturnType<typeof getClassProfile>
  > | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    setProfile(null);
    getClassProfile(classId, SUBJECT)
      .then(setProfile)
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [classId]);

  const weak = profile?.weak_points ?? [];
  const errors = profile?.common_errors ?? [];
  const attention = profile?.attention_students ?? [];
  const avg = profile?.overview?.avg_score_rate;
  const overview = profile?.overview;
  const className = profile?.basic?.class_name ?? classId;
  const trend = overview?.trend
    ? trendLabel(overview.trend, t.teacherCopilot)
    : "—";
  const displaySubject = subjectLabel(
    profile?.basic?.subject ?? SUBJECT,
    t.teacherCopilot,
  );

  return (
    <div className="min-h-full w-full">
      <WorkspaceHeader />
      <main className="space-y-6 p-4 sm:p-8">
        <header>
          <h1 className="text-2xl font-bold">
            {className} · {displaySubject}
          </h1>
          {profile && (
            <p className="text-muted-foreground">
              {overview?.student_count ?? 0} 名学生 · 长期画像更新于刚刚
            </p>
          )}
        </header>

        {loading && (
          <p className="text-muted-foreground text-sm">正在加载班级画像...</p>
        )}
        {!loading && error && (
          <section className="rounded-lg border border-red-200 p-4 text-sm text-red-600">
            加载失败: {error}
          </section>
        )}
        {!loading && !error && profile && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Stat
                label="平均得分率"
                value={avg != null ? `${Math.round(avg * 100)}%` : "—"}
                sub="历史有效结果"
              />
              <Stat
                label="学习趋势"
                value={trend}
                sub={
                  overview?.recent_score_rate != null
                    ? `近期 ${Math.round(overview.recent_score_rate * 100)}%`
                    : "近期暂无数据"
                }
              />
              <Stat
                label="薄弱知识点"
                value={String(weak.length)}
                sub="长期画像"
              />
              <Stat
                label="重点学生"
                value={String(attention.length)}
                sub="需优先跟进"
              />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <section>
                <h2 className="mb-2 text-lg font-semibold">长期薄弱知识点</h2>
                <p className="text-muted-foreground mb-2 text-xs">
                  {algorithmVersionLabel(
                    profile.basic.algorithm_version,
                    t.teacherCopilot,
                  )}
                </p>
                {weak.length === 0 ? (
                  <p className="text-muted-foreground text-sm">
                    暂无长期薄弱点
                  </p>
                ) : (
                  weak.map((w) => (
                    <div
                      key={w.knowledge_point_key}
                      className="mb-2 rounded border px-3 py-2"
                    >
                      <span className="text-sm">
                        {knowledgePointLabel(
                          w.knowledge_point_name,
                          t.teacherCopilot,
                        )}
                      </span>
                      <span className="text-muted-foreground ml-2 text-xs">
                        掌握度{" "}
                        {w.avg_mastery != null
                          ? Math.round(w.avg_mastery * 100)
                          : "—"}
                        % · {w.weak_student_count} 人薄弱
                      </span>
                    </div>
                  ))
                )}
              </section>
              <section>
                <h2 className="mb-2 text-lg font-semibold">共性错误</h2>
                <p className="text-muted-foreground mb-2 text-xs">最近 28 天</p>
                {errors.length === 0 ? (
                  <p className="text-muted-foreground text-sm">暂无共性错误</p>
                ) : (
                  errors.map((e) => (
                    <div
                      key={`${e.error_code}-${e.knowledge_point_key}`}
                      className="mb-2 rounded border px-3 py-2 text-sm"
                    >
                      {errorTypeLabel(e.error_name, t.teacherCopilot)} ·{" "}
                      {e.affected_student_count} 人 ·{" "}
                      {knowledgePointLabel(
                        e.knowledge_point_name,
                        t.teacherCopilot,
                      )}
                    </div>
                  ))
                )}
              </section>
            </div>

            <section>
              <h2 className="mb-2 text-lg font-semibold">重点关注学生</h2>
              <p className="text-muted-foreground mb-2 text-xs">
                长期画像 + 近期趋势
              </p>
              {attention.length === 0 ? (
                <p className="text-muted-foreground text-sm">暂无重点学生</p>
              ) : (
                <ul className="space-y-2">
                  {attention.map((student) => (
                    <li
                      key={student.student_id}
                      className="rounded border px-3 py-2 text-sm"
                    >
                      <Link
                        className="font-medium underline-offset-2 hover:underline"
                        href={`/workspace/teacher-copilot/students/${student.student_id}?class_id=${classId}`}
                      >
                        {student.student_id}
                      </Link>
                      <span className="text-muted-foreground ml-3">
                        {reasonLabels(
                          student.reason_codes,
                          t.teacherCopilot,
                        ).join(" / ")}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-lg border p-4">
      <div className="text-muted-foreground text-sm">{label}</div>
      <div className="my-1 text-2xl font-bold">{value}</div>
      <div className="text-muted-foreground text-xs">{sub}</div>
    </div>
  );
}
