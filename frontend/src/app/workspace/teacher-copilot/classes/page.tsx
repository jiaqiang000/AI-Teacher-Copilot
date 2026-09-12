"use client";
// 班级总览(09 · Class Overview,对照 Figma):班级列表 + 右上角学科切换。
// 学科是聚合视图的查询上下文(URL 查询参数,缺省数学),卡片显示所选学科;
// 卡片另取一次该班画像,用于判断"该学科下是否有数据"并给出空状态(008 FR-009、SC-006)。
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  SubjectEmptyState,
  SubjectSwitcher,
  useSubjectParam,
  withSubject,
} from "@/components/teacher-copilot/subject-context";
import { WorkspaceHeader } from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import { getClassProfile, getTeacherClasses } from "@/core/teacher-copilot/api";
import { subjectLabel } from "@/core/teacher-copilot/display-labels";
import type { Subject } from "@/core/teacher-copilot/types";

type ClassSummary = Awaited<ReturnType<typeof getTeacherClasses>>[number];
type ClassProfile = Awaited<ReturnType<typeof getClassProfile>>;

export default function ClassesPage() {
  const { t } = useI18n();
  // 学科取自 URL 查询参数(缺省数学),切换后刷新与分享链接均保持
  const subject = useSubjectParam();
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [profiles, setProfiles] = useState<Record<string, ClassProfile>>({});
  // 画像请求失败的班级(值为失败原因)。必须与"该学科暂无数据"分开存:
  // 否则一次请求失败会被显示成"这个班在这个学科没有数据",用假状态掩盖真问题
  const [profileErrors, setProfileErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    setProfiles({});
    setProfileErrors({});
    getTeacherClasses()
      .then(async (classList) => {
        setClasses(classList);
        // 逐班取画像只为判断该学科下有无数据;成功与失败分别落账,不混为一谈
        const nextProfiles: Record<string, ClassProfile> = {};
        const nextErrors: Record<string, string> = {};
        await Promise.all(
          classList.map(async (item) => {
            try {
              nextProfiles[item.class_id] = await getClassProfile(item.class_id, subject);
            } catch (e) {
              nextErrors[item.class_id] = (e as Error).message;
            }
          }),
        );
        setProfiles(nextProfiles);
        setProfileErrors(nextErrors);
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [subject]);

  const hasData = (classId: string) =>
    (profiles[classId]?.overview.active_student_count ?? 0) > 0;
  // 多对象页面:每个班级卡片各自判断;全部班级都无数据时另给一处整体提示,
  // 但保留卡片(班级列表与学科无关,仍需可进入)。
  // 加载失败的班级不计入"无数据",免得整页提示被一次请求失败触发
  const noClassHasData =
    classes.length > 0 &&
    classes.every(
      (item) => !hasData(item.class_id) && !profileErrors[item.class_id],
    );

  return (
    <div className="min-h-full w-full">
      <WorkspaceHeader />
      <main className="space-y-6 p-4 sm:p-8">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">我的班级</h1>
            <p className="text-muted-foreground">
              点击班级查看学情画像与重点关注学生
            </p>
          </div>
          {/* 学科切换:即 Figma 中该页右上角的学科标签 */}
          <SubjectSwitcher />
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
        {!loading && !error && noClassHasData && <SubjectEmptyState />}
        {!loading && !error && classes.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {classes.map((classSummary) => (
              <ClassCard
                key={classSummary.class_id}
                classSummary={classSummary}
                subject={subject}
                hasData={hasData(classSummary.class_id)}
                loadError={profileErrors[classSummary.class_id]}
                labels={t.teacherCopilot}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function ClassCard({
  classSummary,
  subject,
  hasData,
  loadError,
  labels,
}: {
  classSummary: ClassSummary;
  subject: Subject;
  hasData: boolean;
  loadError?: string;
  labels: ReturnType<typeof useI18n>["t"]["teacherCopilot"];
}) {
  return (
    <Link
      href={withSubject(
        `/workspace/teacher-copilot/classes/${classSummary.class_id}`,
        subject,
      )}
      className="rounded-xl border p-5 transition hover:shadow-sm"
    >
      <div className="text-lg font-semibold">{classSummary.name}</div>
      {/* 学科展示跟随所选学科(对照 Figma 卡片"30 名学生 · 数学") */}
      <p className="text-muted-foreground mt-1 text-sm">
        {classSummary.student_count} 名学生 · {subjectLabel(subject, labels)}
      </p>
      {/* 三态互斥:加载失败 > 有数据 > 该学科暂无数据;失败不得显示成"暂无数据" */}
      {loadError ? (
        <p className="mt-1 text-sm text-red-600" title={loadError}>
          画像加载失败
        </p>
      ) : hasData ? null : (
        <p className="text-muted-foreground mt-1 text-sm">该学科暂无数据</p>
      )}
    </Link>
  );
}
