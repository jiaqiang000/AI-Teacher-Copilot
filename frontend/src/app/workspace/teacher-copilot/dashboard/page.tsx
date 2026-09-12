"use client";
// 教师工作台(对照 Figma 01):摘要卡片和入口均来自当前教师的真实对象。
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import {
  SubjectEmptyState,
  SubjectSwitcher,
  useSubjectParam,
  withSubject,
} from "@/components/teacher-copilot/subject-context";
import { WorkspaceHeader } from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import {
  getClassProfile,
  getHomeworkAnalysis,
  getTeacherClasses,
  getTeacherHomeworks,
} from "@/core/teacher-copilot/api";
import {
  knowledgePointLabel,
  statusLabel,
  subjectLabel,
  trendLabel,
  type TeacherCopilotLabels,
} from "@/core/teacher-copilot/display-labels";
import type { Subject } from "@/core/teacher-copilot/types";

export default function DashboardPage() {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  // 学科改为视图上下文(URL 查询参数,缺省数学),不再写死 math(008 FR-009)
  const subject = useSubjectParam();
  const deniedToastShown = useRef(false);
  const [classes, setClasses] = useState<
    Awaited<ReturnType<typeof getTeacherClasses>>
  >([]);
  const [profiles, setProfiles] = useState<
    Record<string, Awaited<ReturnType<typeof getClassProfile>>>
  >({});
  const [homeworks, setHomeworks] = useState<
    Awaited<ReturnType<typeof getTeacherHomeworks>>
  >([]);
  const [hwAnalyses, setHwAnalyses] = useState<
    Record<string, Awaited<ReturnType<typeof getHomeworkAnalysis>> | null>
  >({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (searchParams.get("denied") === "student" && !deniedToastShown.current) {
      deniedToastShown.current = true;
      toast.warning("无权限", {
        description: "这是学生功能页面,请使用学生账号访问。",
        duration: 2000,
      });
    }
  }, [searchParams]);

  useEffect(() => {
    void Promise.all([
      getTeacherClasses(),
      getTeacherHomeworks({ subject, limit: 20 }),
    ])
      .then(async ([classList, homeworkList]) => {
        setClasses(classList);
        setHomeworks(homeworkList);
        const profileEntries = await Promise.all(
          classList.map(async (classSummary) => {
            try {
              return [
                classSummary.class_id,
                await getClassProfile(classSummary.class_id, subject),
              ] as const;
            } catch {
              return null;
            }
          }),
        );
        setProfiles(
          Object.fromEntries(
            profileEntries.filter(
              (entry): entry is NonNullable<typeof entry> => entry !== null,
            ),
          ),
        );
        // 工作台只展示前五份作业,分别复用既有作业分析接口,避免把第一份数据误套到其他卡片。
        const recentHomeworks = homeworkList.slice(0, 5);
        const analysisEntries = await Promise.all(
          recentHomeworks.map(async (homework) => {
            try {
              return [
                homework.homework_id,
                await getHomeworkAnalysis(
                  homework.homework_id,
                  homework.class_id,
                ),
              ] as const;
            } catch {
              return [homework.homework_id, null] as const;
            }
          }),
        );
        setHwAnalyses(Object.fromEntries(analysisEntries));
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [subject]);

  const attentionCount = Object.values(profiles).reduce(
    (sum, profile) => sum + profile.attention_students.length,
    0,
  );
  const publishedCount = homeworks.filter(
    (homework) => homework.status === "PUBLISHED",
  ).length;
  const firstProfile = classes[0] ? profiles[classes[0].class_id] : undefined;
  // 多对象页面的空状态:按班级卡片各自判断;全部班级都无数据时另给一处整体提示
  // (班级列表本身与学科无关,保留卡片以便继续进入某个班级)
  const classesWithData = classes.filter(
    (item) => (profiles[item.class_id]?.overview.active_student_count ?? 0) > 0,
  ).length;
  const noClassHasData = classes.length > 0 && classesWithData === 0;

  return (
    <div className="min-h-full w-full">
      <WorkspaceHeader />
      <main className="space-y-8 p-4 sm:p-8">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">教师工作台</h1>
            <p className="text-muted-foreground">
              今天先处理最值得关注的班级与作业
            </p>
          </div>
          {/* 学科切换:工作台同属聚合视图,与其他三个页面一并纳入切换范围 */}
          <SubjectSwitcher />
        </header>

        {/* 体验指引(US5:登录方式/建议步骤/角色切换) */}
        <details className="bg-muted/30 space-y-1 rounded-lg border p-4 text-sm">
          <summary className="cursor-pointer font-medium">
            体验指引(点击展开)
          </summary>
          <p className="text-muted-foreground">
            <b>教师账号</b> teacher@demo.com / teacher123456 · <b>学生账号</b>{" "}
            student@demo.com / student123456
          </p>
          <p className="text-muted-foreground">
            建议步骤:① 左侧“Copilot 对话”→ 聊天页问“八三班《单元练习》完成率”→ ②
            学生账号看作业与批改结果 → ③ 教师出题(手动/题库/题目图 OCR)并发布 →
            ④ 学生上传作答(需配置 OSS)→ 查看新批改结果。
          </p>
          <p className="text-muted-foreground">
            角色切换:退出登录后使用另一账号重新登录。
          </p>
        </details>

        {loading && (
          <p className="text-muted-foreground text-sm">正在加载工作台数据...</p>
        )}
        {!loading && error && (
          <p className="text-sm text-red-600">数据加载失败: {error}</p>
        )}

        {!loading && !error && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="班级"
                value={String(classes.length)}
                sub="当前授课"
              />
              <StatCard
                label="已发布作业"
                value={String(publishedCount)}
                sub="当前授课"
              />
              <StatCard
                label="重点学生"
                value={String(attentionCount)}
                sub="需要关注"
              />
              <StatCard
                label="最新平均得分"
                value={
                  firstProfile?.overview.avg_score_rate != null
                    ? `${Math.round(firstProfile.overview.avg_score_rate * 100)}%`
                    : "—"
                }
                sub="首个班级画像"
              />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <section>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold">我的班级</h2>
                  <Link
                    className="text-sm underline-offset-2 hover:underline"
                    href={withSubject(
                      "/workspace/teacher-copilot/classes",
                      subject,
                    )}
                  >
                    查看全部
                  </Link>
                </div>
                {classes.length === 0 ? (
                  <p className="text-muted-foreground text-sm">暂无班级</p>
                ) : (
                  <>
                    {noClassHasData && <SubjectEmptyState />}
                    {classes.map((classSummary) => (
                      <ClassCard
                        key={classSummary.class_id}
                        classId={classSummary.class_id}
                        name={classSummary.name}
                        count={`${classSummary.student_count} 名学生`}
                        subject={subject}
                        hasData={
                          (profiles[classSummary.class_id]?.overview
                            .active_student_count ?? 0) > 0
                        }
                        profile={profiles[classSummary.class_id]}
                        labels={t.teacherCopilot}
                      />
                    ))}
                  </>
                )}
              </section>
              <section>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold">最近作业</h2>
                  <Link
                    className="text-sm underline-offset-2 hover:underline"
                    href="/workspace/teacher-copilot/homeworks"
                  >
                    管理作业
                  </Link>
                </div>
                {homeworks.length === 0 ? (
                  <p className="text-muted-foreground text-sm">暂无作业</p>
                ) : (
                  homeworks
                    .slice(0, 5)
                    .map((homework) => (
                      <HomeworkCard
                        key={homework.homework_id}
                        homework={homework}
                        completion={
                          hwAnalyses[homework.homework_id]?.completion
                            ?.completion_rate ?? null
                        }
                        labels={t.teacherCopilot}
                      />
                    ))
                )}
              </section>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function StatCard({
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

function ClassCard({
  classId,
  name,
  count,
  subject,
  hasData,
  profile,
  labels,
}: {
  classId: string;
  name: string;
  count: string;
  subject: Subject;
  hasData: boolean;
  profile?: Awaited<ReturnType<typeof getClassProfile>>;
  labels: TeacherCopilotLabels;
}) {
  const trend = profile?.overview.trend;
  const weak = profile?.weak_points[0]
    ? knowledgePointLabel(profile.weak_points[0].knowledge_point_name, labels)
    : null;
  return (
    <Link
      href={withSubject(`/workspace/teacher-copilot/classes/${classId}`, subject)}
      className="mb-2 block rounded-lg border p-4 transition hover:shadow-sm"
    >
      <div className="font-medium">{name}</div>
      <div className="text-muted-foreground text-xs">
        {count} · {subjectLabel(subject, labels)}
      </div>
      {/* 该班在所选学科下无数据时,在本卡片内提示,而不是留白 */}
      <div className={hasData ? "mt-1 text-sm" : "text-muted-foreground mt-1 text-sm"}>
        {hasData ? (
          <>
            {trend ? trendLabel(trend, labels) : labels.unknownTrend}
            {profile?.overview.avg_score_rate != null
              ? ` · 平均 ${Math.round(profile.overview.avg_score_rate * 100)}%`
              : ""}
            {weak ? ` · ${weak}` : ""}
          </>
        ) : (
          "该学科暂无数据"
        )}
      </div>
    </Link>
  );
}

function HomeworkCard({
  homework,
  completion,
  labels,
}: {
  homework: Awaited<ReturnType<typeof getTeacherHomeworks>>[number];
  completion: number | null;
  labels: TeacherCopilotLabels;
}) {
  return (
    <Link
      href={`/workspace/teacher-copilot/homeworks/${homework.homework_id}/analysis?class_id=${homework.class_id}`}
      className="mb-2 block rounded-lg border p-4 transition hover:shadow-sm"
    >
      <div className="font-medium">{homework.name}</div>
      <div className="text-muted-foreground text-xs">
        {completion != null
          ? `完成 ${Math.round(completion * 100)}%`
          : "暂无数据"}
        {` · ${homework.class_name} · ${statusLabel(homework.status, labels)}`}
      </div>
    </Link>
  );
}
