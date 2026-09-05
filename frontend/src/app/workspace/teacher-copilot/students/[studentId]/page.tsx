"use client";
// 学生画像(对照 Figma 03):按路由 studentId 展示当前教师可见的真实数据。
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { WorkspaceHeader } from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import {
  getStudentHistory,
  getStudentProfile,
} from "@/core/teacher-copilot/api";
import {
  algorithmVersionLabel,
  difficultyLabel,
  errorTypeLabel,
  knowledgePointLabel,
  subjectLabel,
  trendLabel,
} from "@/core/teacher-copilot/display-labels";

const SUBJECT = process.env.NEXT_PUBLIC_TC_SUBJECT ?? "math";

export default function StudentProfilePage() {
  const { t } = useI18n();
  const { studentId } = useParams<{ studentId: string }>();
  const searchParams = useSearchParams();
  const classId = searchParams.get("class_id") ?? undefined;
  const [profile, setProfile] = useState<Awaited<
    ReturnType<typeof getStudentProfile>
  > | null>(null);
  const [history, setHistory] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    setProfile(null);
    void Promise.all([
      getStudentProfile(studentId, SUBJECT, classId),
      getStudentHistory(studentId, SUBJECT, classId),
    ])
      .then(([studentProfile, studentHistory]) => {
        setProfile(studentProfile);
        setHistory(studentHistory);
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [classId, studentId]);

  const overview = profile?.overview;
  const recurring = profile?.recurring_errors ?? [];
  const basic = profile?.basic;
  const trend = overview?.trend
    ? trendLabel(overview.trend, t.teacherCopilot)
    : "—";
  const displaySubject = subjectLabel(
    basic?.subject ?? SUBJECT,
    t.teacherCopilot,
  );

  return (
    <div className="min-h-full w-full">
      <WorkspaceHeader />
      <main className="space-y-6 p-4 sm:p-8">
        <header>
          <h1 className="text-2xl font-bold">
            {basic?.student_name ?? studentId} · 学生画像
          </h1>
          {basic && (
            <p className="text-muted-foreground">
              {basic.class_name ?? basic.class_id ?? "—"} · {displaySubject} ·{" "}
              {algorithmVersionLabel(basic.algorithm_version, t.teacherCopilot)}
            </p>
          )}
        </header>

        {loading && (
          <p className="text-muted-foreground text-sm">正在加载学生画像...</p>
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
                value={
                  overview?.avg_score_rate != null
                    ? `${Math.round(overview.avg_score_rate * 100)}%`
                    : "—"
                }
                sub="历史"
              />
              <Stat
                label="近期得分率"
                value={
                  overview?.recent_score_rate != null
                    ? `${Math.round(overview.recent_score_rate * 100)}%`
                    : "—"
                }
                sub="最近 14 天"
              />
              <Stat label="趋势" value={trend} sub="近期与前期对比" />
              <Stat
                label="累计作答"
                value={String(overview?.attempt_count ?? 0)}
                sub="有效结果"
              />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <section>
                <h2 className="mb-2 text-lg font-semibold">知识点掌握</h2>
                <p className="text-muted-foreground mb-2 text-xs">
                  {t.teacherCopilot.performanceWeighting}
                </p>
                {(profile.knowledge_points ?? []).length === 0 ? (
                  <p className="text-muted-foreground text-sm">
                    暂无知识点记录
                  </p>
                ) : (
                  profile.knowledge_points.map((kp) => (
                    <div
                      key={kp.knowledge_point_key}
                      className="mb-2 rounded border px-3 py-2 text-sm"
                    >
                      <span>
                        {knowledgePointLabel(
                          kp.knowledge_point_name,
                          t.teacherCopilot,
                        )}
                      </span>
                      <span className="text-muted-foreground ml-2">
                        {kp.mastery != null
                          ? `${Math.round(kp.mastery * 100)}%`
                          : "—"}
                        {kp.mastery != null &&
                        kp.mastery < 0.6 &&
                        kp.attempt_count >= 3
                          ? " · 长期薄弱"
                          : ""}
                      </span>
                    </div>
                  ))
                )}
              </section>
              <section>
                <h2 className="mb-2 text-lg font-semibold">重复错误</h2>
                <p className="text-muted-foreground mb-2 text-xs">最近 28 天</p>
                {recurring.length === 0 ? (
                  <p className="text-muted-foreground text-sm">暂无重复错误</p>
                ) : (
                  recurring.map((item) => (
                    <div
                      key={`${item.error_code}-${item.knowledge_point_key}`}
                      className="mb-2 rounded border px-3 py-2 text-sm"
                    >
                      {errorTypeLabel(item.error_name, t.teacherCopilot)} ×
                      {item.recent_occurrence_count}
                      <span className="text-muted-foreground ml-2">
                        关联{" "}
                        {knowledgePointLabel(
                          item.knowledge_point_name,
                          t.teacherCopilot,
                        )}
                      </span>
                    </div>
                  ))
                )}
              </section>
            </div>

            <section>
              <h2 className="mb-2 text-lg font-semibold">最近批改记录</h2>
              <p className="text-muted-foreground mb-2 text-xs">
                {t.teacherCopilot.currentGradingResult}
              </p>
              {history.length === 0 ? (
                <p className="text-muted-foreground text-sm">暂无历史记录</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {history.slice(0, 5).map((item) => (
                    <li
                      key={String(item.grading_result_id)}
                      className="rounded border px-3 py-2"
                    >
                      {difficultyLabel(
                        typeof item.difficulty === "string"
                          ? item.difficulty
                          : null,
                        t.teacherCopilot,
                      )}{" "}
                      · {historyRate(item.score)}%
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

function historyRate(value: unknown) {
  if (!value || typeof value !== "object" || !("rate" in value)) {
    return 0;
  }
  const rate = value.rate;
  return typeof rate === "number" ? Math.round(rate * 100) : 0;
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
